
import asyncio
import random
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import aiohttp


class AsyncHTTPClient:
    """
    Reusable asynchronous HTTP client.

    Features:
    - Bounded concurrency
    - Custom request headers
    - Automatic retries
    - Exponential backoff with jitter
    - Retry-After support
    - HTTP 429 and 5xx handling
    - Request timeouts
    """

    def __init__(
        self,
        concurrency=20,
        max_retries=5,
        timeout=60,
        default_headers=None
    ):
        self.semaphore = asyncio.Semaphore(concurrency)
        self.max_retries = max_retries
        self.timeout = aiohttp.ClientTimeout(total=timeout)

        self.headers = {
            "User-Agent": "FrontierAtlas/1.0",
            "Accept": "*/*"
        }

        if default_headers:
            self.headers.update(default_headers)

        self.session = None

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(
            limit=0,
            limit_per_host=20
        )

        self.session = aiohttp.ClientSession(
            timeout=self.timeout,
            connector=connector,
            headers=self.headers
        )

        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()

    def get_retry_delay(self, response, attempt):
        """Calculate retry delay, respecting Retry-After."""

        retry_after = response.headers.get("Retry-After")

        if retry_after:
            try:
                return min(float(retry_after), 60)

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

                    return min(max(seconds, 0), 60)

                except (TypeError, ValueError):
                    pass

        return min(2 ** attempt + random.random(), 60)

    async def fetch(
        self,
        url,
        response_type="json",
        params=None,
        headers=None
    ):
        """Fetch JSON, text, or bytes from a URL."""

        if self.session is None:
            raise RuntimeError(
                "Use AsyncHTTPClient inside an async with block."
            )

        if response_type not in ("json", "text", "bytes"):
            raise ValueError("Unsupported response type.")

        async with self.semaphore:

            for attempt in range(self.max_retries):

                try:
                    async with self.session.get(
                        url,
                        params=params,
                        headers=headers
                    ) as response:

                        if (
                            response.status == 429
                            or response.status >= 500
                        ):

                            if attempt == self.max_retries - 1:
                                response.raise_for_status()

                            delay = self.get_retry_delay(
                                response,
                                attempt
                            )

                            print(
                                f"HTTP {response.status}. "
                                f"Retrying in {delay:.1f}s: {url}"
                            )

                            await asyncio.sleep(delay)
                            continue

                        response.raise_for_status()

                        if response_type == "json":
                            return await response.json(
                                content_type=None
                            )

                        if response_type == "text":
                            return await response.text()

                        return await response.read()

                except (
                    aiohttp.ClientError,
                    asyncio.TimeoutError
                ) as error:

                    if attempt == self.max_retries - 1:
                        raise

                    delay = min(
                        2 ** attempt + random.random(),
                        60
                    )

                    print(
                        f"Request failed: {error}. "
                        f"Retrying in {delay:.1f}s."
                    )

                    await asyncio.sleep(delay)

        raise RuntimeError(f"Request failed: {url}")

    async def fetch_many_json(self, urls):
        """Fetch multiple JSON endpoints concurrently."""

        tasks = [
            self.fetch(url, response_type="json")
            for url in urls
        ]

        results = await asyncio.gather(
            *tasks,
            return_exceptions=True
        )

        return dict(zip(urls, results))
