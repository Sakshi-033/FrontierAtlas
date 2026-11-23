import asyncio
import json
import os
import random
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import aiohttp
from dotenv import load_dotenv

load_dotenv()


class PayloadTooLarge(Exception):
    pass


class ProviderError(Exception):
    pass


class TextChunker:
    def __init__(self, max_chars=8000, overlap=400):
        self.max_chars = max_chars
        self.overlap = overlap

    def split(self, text):
        text = text.strip()
        chunks = []
        start = 0

        while start < len(text):
            end = min(start + self.max_chars, len(text))

            if end < len(text):
                boundary = text.rfind("\n", start, end)
                if boundary <= start:
                    boundary = text.rfind(" ", start, end)
                if boundary > start:
                    end = boundary

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            if end >= len(text):
                break

            start = max(end - self.overlap, start + 1)

        return chunks


class LLMOrchestrator:

    PROVIDERS = [
        {
            "name": "Gemini Flash",
            "key": "GEMINI_API_KEY",
            "url": (
                "https://generativelanguage.googleapis.com/"
                "v1beta/models/gemini-3.8-flash:generateContent"
            ),
            "type": "gemini",
        },
        {
            "name": "Groq Llama",
            "key": "GROQ_API_KEY",
            "url": "https://api.groq.com/openai/v1/chat/completions",
            "model": "openai/gpt-oss-120b",
            "type": "openai",
        },
        {
            "name": "DeepSeek",
            "key": "DEEPSEEK_API_KEY",
            "url": "https://api.deepseek.com/chat/completions",
            "model": "deepseek-chat",
            "type": "openai",
        },
    ]

    def __init__(self, max_retries=2, max_chars=8000,
                 overlap=400, timeout=35):
        self.max_retries = max_retries
        self.chunker = TextChunker(max_chars, overlap)
        self.timeout = aiohttp.ClientTimeout(
            total=timeout, connect=10, sock_read=25
        )
        self.chunks_processed = 0
        self.split_count = 0

    def available_providers(self):
        return [
            provider for provider in self.PROVIDERS
            if os.getenv(provider["key"])
        ]

    @staticmethod
    def build_prompt(text):
        return f"""
Extract factual entities from the source.

Return ONLY valid JSON:
{{
  "records": [
    {{
      "entity_name": "Name",
      "entity_type": "STARTUP, PRODUCT, RESEARCH_PAPER, JOB, or NEWS",
      "description": "Supported description",
      "source_url": null
    }}
  ]
}}

Never invent facts, URLs, dates or metrics.
Use null when information is unavailable.
Return an empty records array if nothing reliable is found.

SOURCE:
{text}
"""

    @staticmethod
    def parse_json(content):
        content = content.strip()
        content = re.sub(
            r"^```(?:json)?\s*|\s*```$",
            "",
            content,
            flags=re.IGNORECASE
        )

        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start == -1 or end == -1:
                raise ProviderError("Invalid JSON response")
            result = json.loads(content[start:end + 1])

        if not isinstance(result, dict):
            raise ProviderError("Expected JSON object")

        if not isinstance(result.get("records"), list):
            raise ProviderError("Missing records array")

        return result

    @staticmethod
    def retry_delay(response, attempt):
        retry_after = response.headers.get("Retry-After")

        if retry_after:
            try:
                return min(max(float(retry_after), 0), 30)
            except ValueError:
                try:
                    retry_date = parsedate_to_datetime(retry_after)
                    if retry_date.tzinfo is None:
                        retry_date = retry_date.replace(
                            tzinfo=timezone.utc
                        )
                    seconds = (
                        retry_date - datetime.now(timezone.utc)
                    ).total_seconds()
                    return min(max(seconds, 0), 30)
                except (TypeError, ValueError):
                    pass

        return min(2 ** attempt + random.random(), 30)

    async def call_provider(self, session, provider, text):
        api_key = os.getenv(provider["key"])
        prompt = self.build_prompt(text)

        if provider["type"] == "gemini":
            headers = {
                "x-goog-api-key": api_key,
                "Content-Type": "application/json"
            }
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.1
                }
            }
        else:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": provider["model"],
                "messages": [
                    {
                        "role": "system",
                        "content": "Extract facts only. Never invent data."
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            }

        for attempt in range(self.max_retries):
            try:
                print(f"Sending request to {provider['name']}...")

                async with session.post(
                    provider["url"],
                    headers=headers,
                    json=payload
                ) as response:

                    if response.status == 413:
                        raise PayloadTooLarge("HTTP 413: payload too large")

                    if response.status == 429 or response.status >= 500:
                        if attempt == self.max_retries - 1:
                            raise ProviderError(
                                f"HTTP {response.status}"
                            )

                        delay = self.retry_delay(response, attempt)
                        print(
                            f"HTTP {response.status}; "
                            f"retrying in {delay:.1f}s"
                        )
                        await asyncio.sleep(delay)
                        continue

                    if response.status >= 400:
                        error = await response.text()
                        raise ProviderError(
                            f"HTTP {response.status}: {error[:250]}"
                        )

                    data = await response.json()

                    if provider["type"] == "gemini":
                        content = (
                            data["candidates"][0]["content"]
                            ["parts"][0]["text"]
                        )
                    else:
                        content = data["choices"][0]["message"]["content"]

                    return self.parse_json(content)

            except PayloadTooLarge:
                raise
            except ProviderError:
                raise
            except asyncio.TimeoutError:
                raise ProviderError(
                    f"{provider['name']} timed out"
                )
            except aiohttp.ClientError as error:
                if attempt == self.max_retries - 1:
                    raise ProviderError(str(error)) from error
                await asyncio.sleep(2 ** attempt + random.random())

        raise ProviderError("Retries exhausted")

    async def extract_chunk(
        self, session, text, providers, depth=0
    ):
        errors = []

        for provider in providers:
            try:
                print(f"Trying {provider['name']}...")
                result = await self.call_provider(
                    session, provider, text
                )
                print(f"Success: {provider['name']}")
                self.chunks_processed += 1
                return result["records"]

            except PayloadTooLarge:
                if len(text) < 500 or depth >= 8:
                    errors.append("Payload too large after splitting")
                    continue

                self.split_count += 1
                print("HTTP 413: splitting payload into smaller chunks")

                smaller_chunker = TextChunker(
                    max_chars=max(250, len(text) // 2),
                    overlap=min(100, len(text) // 20)
                )

                pieces = smaller_chunker.split(text)

                if len(pieces) < 2:
                    errors.append("Unable to split oversized payload")
                    continue

                combined = []
                for piece in pieces:
                    combined.extend(
                        await self.extract_chunk(
                            session, piece, providers, depth + 1
                        )
                    )
                return combined

            except Exception as error:
                errors.append(f"{provider['name']}: {error}")
                print(f"Provider unavailable: {error}")

        raise ProviderError(
            "All providers failed: " + " | ".join(errors)
        )

    async def extract(self, text):
        self.chunks_processed = 0
        self.split_count = 0

        providers = self.available_providers()

        if not providers:
            raise RuntimeError("No LLM API keys configured")

        chunks = self.chunker.split(text)
        records = []

        if not chunks:
            return {
                "records": [],
                "entities": [],
                "chunks_processed": 0,
                "splits": 0
            }

        print("Available:", [p["name"] for p in providers])
        print("Initial chunks:", len(chunks))

        async with aiohttp.ClientSession(
            timeout=self.timeout
        ) as session:

            for index, chunk in enumerate(chunks, 1):
                print(f"Processing {index}/{len(chunks)}")

                extracted = await self.extract_chunk(
                    session, chunk, providers
                )
                records.extend(extracted)

        return {
            "records": records,
            "entities": records,
            "chunks_processed": self.chunks_processed,
            "splits": self.split_count
        }
