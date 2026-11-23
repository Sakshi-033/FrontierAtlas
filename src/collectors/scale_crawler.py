import asyncio
import argparse
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from src.utils.http_client import AsyncHTTPClient

DATA = Path("data")
URL_FIELDS = {
    "url", "website", "source_url", "link",
    "paper_url", "product_url", "company_url"
}

CHALLENGE_MARKERS = [
    "just a moment",
    "cf-browser-verification",
    "challenge-platform",
    "checking your browser",
    "attention required",
    "cloudflare"
]


def extract_urls(value):
    """Find URLs in nested JSON records."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in URL_FIELDS and isinstance(item, str):
                if item.startswith(("http://", "https://")):
                    yield item
            yield from extract_urls(item)

    elif isinstance(value, list):
        for item in value:
            yield from extract_urls(item)


def load_urls():
    """Load and deduplicate URLs from existing datasets."""
    urls = set()

    for filename in [
        "startups.json",
        "products.json",
        "research_papers.json",
        "news.json",
        "jobs.json"
    ]:
        path = DATA / filename

        if not path.exists():
            continue

        try:
            with open(path, encoding="utf-8") as file:
                records = json.load(file)

            found = set(extract_urls(records))
            urls.update(found)
            print(f"{filename}: {len(found)} URLs found")

        except Exception as error:
            print(f"Could not read {filename}: {error}")

    return sorted(urls)


def classify_html(html, status):
    """Identify normal, JavaScript-dependent and blocked pages."""
    lower = html[:100000].lower()

    if status in (403, 429, 503):
        if any(marker in lower for marker in CHALLENGE_MARKERS):
            return "CLOUDFLARE_OR_ANTI_BOT"
        return "ACCESS_BLOCKED"

    if any(marker in lower for marker in CHALLENGE_MARKERS):
        return "CLOUDFLARE_OR_ANTI_BOT"

    soup = BeautifulSoup(html, "html.parser")

    for element in soup(["script", "style", "noscript"]):
        element.decompose()

    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))

    if len(text) < 150:
        return "POSSIBLE_JAVASCRIPT_RENDERING"

    return "SUCCESS"


async def crawl_one(client, url):
    result = {
        "url": url,
        "crawled_at": datetime.now(timezone.utc).isoformat()
    }

    try:
        html = await client.fetch(url, response_type="text")
        result["status"] = 200
        result["classification"] = classify_html(html, 200)

        soup = BeautifulSoup(html, "html.parser")
        result["title"] = (
            soup.title.get_text(strip=True)
            if soup.title else ""
        )

        result["text_length"] = len(
            soup.get_text(" ", strip=True)
        )

        result["requires_browser_fallback"] = (
            result["classification"] in (
                "POSSIBLE_JAVASCRIPT_RENDERING",
                "CLOUDFLARE_OR_ANTI_BOT"
            )
        )

    except Exception as error:
        status = getattr(error, "status", None)

        result["status"] = status
        result["error"] = str(error)

        if status in (403, 429, 503):
            result["classification"] = "ACCESS_BLOCKED"
        else:
            result["classification"] = "REQUEST_FAILED"

        result["requires_browser_fallback"] = status in (403, 503)

    return result


async def main(limit, concurrency):
    urls = load_urls()[:limit]

    print(f"\nUnique URLs selected: {len(urls)}")
    print(f"Concurrency: {concurrency}")
    print("Starting asynchronous crawl...\n")

    results = []

    async with AsyncHTTPClient(
        concurrency=concurrency,
        max_retries=3,
        timeout=20
    ) as client:

        tasks = [
            asyncio.create_task(crawl_one(client, url))
            for url in urls
        ]

        for completed in asyncio.as_completed(tasks):
            result = await completed
            results.append(result)

            print(
                result["classification"],
                result["url"][:90]
            )

    DATA.mkdir(exist_ok=True)

    output = DATA / "crawl_results.json"
    report = DATA / "crawl_report.json"

    with open(output, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=2, ensure_ascii=False)

    counts = {}

    for result in results:
        category = result["classification"]
        counts[category] = counts.get(category, 0) + 1

    summary = {
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "urls_selected": len(urls),
        "results_count": len(results),
        "concurrency": concurrency,
        "classification_counts": counts,
        "browser_fallback_urls": [
            item["url"] for item in results
            if item.get("requires_browser_fallback")
        ],
        "output_file": str(output)
    }

    with open(report, "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    print("\n========== PHASE V REPORT ==========")
    print(json.dumps(summary, indent=2))
    print("\nSaved:", output)
    print("Saved:", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--concurrency", type=int, default=10)
    args = parser.parse_args()

    asyncio.run(main(args.limit, args.concurrency))
