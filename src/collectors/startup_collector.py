
import asyncio
import json
import re

from datetime import datetime, timezone
from pathlib import Path

from src.schemas import Startup
from src.utils.http_client import AsyncHTTPClient


API_URL = "https://yc-oss.github.io/api/tags/ai.json"
OUTPUT_FILE = Path("data/startups.json")

CONCURRENCY = 20


def normalize_name(name):
    """Normalize company names for deduplication."""
    return re.sub(r"\s+", " ", name.strip().lower())


def process_startup(raw):
    """Validate and convert a directory entry into Startup schema."""

    if not isinstance(raw, dict):
        return None

    name = raw.get("name")
    source_url = raw.get("url")

    if not isinstance(name, str) or not name.strip():
        return None

    if not isinstance(source_url, str):
        return None

    if not source_url.startswith(("http://", "https://")):
        return None

    employee_count = raw.get("team_size")

    if employee_count is not None:
        try:
            employee_count = int(employee_count)

            if employee_count < 0:
                employee_count = None

        except (ValueError, TypeError):
            employee_count = None

    try:
        return Startup(
            source={
                "name": "Y Combinator",
                "url": source_url
            },
            content={
                "entityName": name.strip(),
                "data": {
                    "employeeCount": employee_count
                }
            },
            collectedAt=datetime.now(timezone.utc)
        )

    except Exception as error:
        print(f"Invalid startup skipped: {error}")
        return None


async def process_records(raw_records):
    """Process records with bounded concurrency."""

    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def process_one(raw):
        async with semaphore:
            return await asyncio.to_thread(process_startup, raw)

    tasks = [
        process_one(raw)
        for raw in raw_records
    ]

    return await asyncio.gather(*tasks)


def save_records(records):
    """Save records atomically."""

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temporary_file = OUTPUT_FILE.with_suffix(".tmp")

    with temporary_file.open("w", encoding="utf-8") as file:
        json.dump(
            [
                record.model_dump(mode="json")
                for record in records
            ],
            file,
            indent=2,
            ensure_ascii=False
        )

    temporary_file.replace(OUTPUT_FILE)


async def main():

    print("Starting startup collection...")
    print("Source: Y Combinator AI directory")

    async with AsyncHTTPClient(
        concurrency=CONCURRENCY,
        max_retries=5,
        timeout=60
    ) as client:

        raw_records = await client.fetch(
            API_URL,
            response_type="json"
        )

    if not isinstance(raw_records, list):
        raise ValueError(
            "Unexpected API response. Expected a JSON list."
        )

    print(f"Records received: {len(raw_records)}")

    processed = await process_records(raw_records)

    unique_records = {}

    for startup in processed:

        if startup is None:
            continue

        key = normalize_name(
            startup.content.entityName
        )

        if key not in unique_records:
            unique_records[key] = startup

    records = list(unique_records.values())

    save_records(records)

    invalid_records = processed.count(None)

    print("\n========== STARTUP COLLECTION REPORT ==========")
    print(f"Source: Y Combinator")
    print(f"Total received: {len(raw_records)}")
    print(f"Unique startups: {len(records)}")
    print(f"Invalid records: {invalid_records}")
    print(f"Processing concurrency: {CONCURRENCY}")
    print(f"Saved to: {OUTPUT_FILE}")
    print("================================================")

    if len(records) >= 1000:
        print("SUCCESS: Startup collection target achieved!")
    else:
        print("WARNING: Minimum target of 1000 not reached.")


if __name__ == "__main__":
    asyncio.run(main())
