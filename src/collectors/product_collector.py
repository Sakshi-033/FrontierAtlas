
import asyncio
import json
import re

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from src.schemas import Product
from src.utils.http_client import AsyncHTTPClient


HARPD_URL = (
    "https://raw.githubusercontent.com/"
    "harpd-dev/harpd-ai-datasets/main/"
    "data/products/products.json"
)

OUTPUT_FILE = Path("data/products.json")

CONCURRENCY = 20


def normalize_name(name):
    """Normalize product names for deduplication."""
    return re.sub(r"\s+", " ", name.strip().lower())


def valid_url(url):
    """Check whether a URL has a valid HTTP or HTTPS structure."""

    if not isinstance(url, str):
        return False

    parsed = urlparse(url.strip())

    return (
        parsed.scheme in ("http", "https")
        and bool(parsed.netloc)
    )


def load_existing():
    """Load previously collected products safely."""

    if not OUTPUT_FILE.exists():
        return []

    with OUTPUT_FILE.open("r", encoding="utf-8") as file:
        records = json.load(file)

    if not isinstance(records, list):
        raise ValueError(
            "Existing product file must contain a JSON list."
        )

    return records


def process_product(raw):
    """Convert a raw product into the validated Product schema."""

    if not isinstance(raw, dict):
        return None

    name = raw.get("name")
    website = raw.get("website")

    if not isinstance(name, str) or not name.strip():
        return None

    name = name.strip()

    if not valid_url(website):
        return None

    startup_name = (
        raw.get("startupName")
        or raw.get("company")
        or raw.get("company_name")
    )

    if isinstance(startup_name, str):
        startup_name = startup_name.strip() or None
    else:
        startup_name = None

    product = Product(
        source={
            "name": "Harpd AI Product Dataset",
            "url": HARPD_URL
        },
        content={
            "productName": name,
            "startupName": startup_name,
            "productUrl": website.strip(),
            "pricingModel": None
        },
        collectedAt=datetime.now(timezone.utc)
    )

    return product.model_dump(mode="json")


async def fetch_products(client):
    """Download the product catalogue using the shared HTTP client."""

    return await client.fetch(
        HARPD_URL,
        response_type="json"
    )


async def process_products(incoming):
    """Process incoming records with bounded concurrency."""

    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def process_one(raw):
        async with semaphore:
            try:
                return await asyncio.to_thread(
                    process_product,
                    raw
                )
            except Exception as error:
                print(f"Skipped invalid product: {error}")
                return None

    tasks = [
        process_one(raw)
        for raw in incoming
    ]

    return await asyncio.gather(*tasks)


def save_records(records):
    """Save atomically to protect the existing dataset."""

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temp_file = OUTPUT_FILE.with_suffix(".tmp")

    with temp_file.open("w", encoding="utf-8") as file:
        json.dump(
            records,
            file,
            indent=2,
            ensure_ascii=False
        )

    temp_file.replace(OUTPUT_FILE)


async def main():

    existing = load_existing()

    print("Existing products:", len(existing))
    print("Downloading Harpd product catalogue...")

    try:
        async with AsyncHTTPClient(
            concurrency=CONCURRENCY,
            max_retries=5,
            timeout=120
        ) as client:

            dataset = await fetch_products(client)

    except Exception as error:
        print("\nDataset download failed:", error)
        print("Existing products have been preserved.")
        return

    if isinstance(dataset, list):
        incoming = dataset

    elif isinstance(dataset, dict):
        incoming = dataset.get("products", [])

    else:
        print("Unexpected dataset format.")
        return

    if not isinstance(incoming, list):
        print("Unexpected products format.")
        return

    print("Incoming source records:", len(incoming))

    unique_products = {}

    # Preserve existing records.
    for record in existing:

        if not isinstance(record, dict):
            continue

        content = record.get("content", {})
        name = content.get("productName", "")

        if isinstance(name, str) and name.strip():

            unique_products.setdefault(
                normalize_name(name),
                record
            )

    # Process incoming products.
    processed = await process_products(incoming)

    added = 0
    invalid = processed.count(None)

    for product in processed:

        if product is None:
            continue

        name = product["content"]["productName"]
        key = normalize_name(name)

        if key in unique_products:
            continue

        unique_products[key] = product
        added += 1

    final_records = list(unique_products.values())

    save_records(final_records)

    print("\n========== PRODUCT REPORT ==========")
    print("Previously collected:", len(existing))
    print("Incoming records:", len(incoming))
    print("New unique products:", added)
    print("Final unique products:", len(final_records))
    print("Invalid records:", invalid)
    print("Processing concurrency:", CONCURRENCY)
    print("Saved to:", OUTPUT_FILE)
    print("====================================")

    if len(final_records) >= 1000:
        print("SUCCESS: Product target achieved!")
    else:
        print("WARNING: Product target not reached.")


if __name__ == "__main__":
    asyncio.run(main())
