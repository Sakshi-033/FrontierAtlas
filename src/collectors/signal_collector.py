import asyncio
import json
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiohttp
import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as date_parser


NEWS_SOURCES = {
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "Ars Technica AI": "https://arstechnica.com/ai/feed/",
    "MIT Technology Review": "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
    "OpenAI News": "https://openai.com/news/rss.xml",
}

JOB_SOURCES = {
    "Anthropic": ("greenhouse", "anthropic"),
    "Scale AI": ("greenhouse", "scaleai"),
    "OpenAI": ("ashby", "openai"),
    "Perplexity": ("ashby", "perplexity"),
    "Cohere": ("ashby", "cohere"),
}

DATA_DIR = Path("data")


def parse_date(value):
    if not value:
        return None
    try:
        result = date_parser.parse(str(value))
        if result.tzinfo is None:
            result = result.replace(tzinfo=timezone.utc)
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def recent(value):
    if not value:
        return False
    now = datetime.now(timezone.utc)
    return now - timedelta(hours=24) <= value <= now + timedelta(minutes=5)


def clean_html(value):
    return BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)


def record_id(url):
    return hashlib.sha256(url.encode()).hexdigest()


def save_json(path, records):
    DATA_DIR.mkdir(exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    temp.replace(path)


async def get(session, url):
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.read()


async def collect_news(session, name, url):
    print(f"[NEWS] {name}", flush=True)
    try:
        raw = await get(session, url)
        feed = feedparser.parse(raw)
        records = []

        for entry in feed.entries:
            link = entry.get("link", "").strip()
            title = entry.get("title", "").strip()
            date = parse_date(
                entry.get("published") or entry.get("updated")
            )

            if not link or not title or not recent(date):
                continue

            records.append({
                "id": record_id(link),
                "source": name,
                "title": title,
                "url": link,
                "published_at": date.isoformat(),
                "summary": clean_html(entry.get("summary", "")),
                "full_text": None,
                "content_status": "SUMMARY_ONLY",
                "record_type": "NEWS",
            })

        print(f"[NEWS] {name}: {len(records)} recent", flush=True)
        return records

    except Exception as error:
        print(f"[NEWS ERROR] {name}: {error}", flush=True)
        return []


async def enrich_article(session, record):
    try:
        raw = await get(session, record["url"])
        soup = BeautifulSoup(raw, "html.parser")
        article = soup.find("article")

        if article:
            for tag in article(["script", "style", "nav", "footer"]):
                tag.decompose()
            text = article.get_text(" ", strip=True)
        else:
            text = " ".join(
                p.get_text(" ", strip=True)
                for p in soup.find_all("p")
            )

        if text:
            record["full_text"] = text
            record["content_status"] = "FULL_TEXT"

    except Exception as error:
        record["content_status"] = "FULL_TEXT_FAILED"
        record["content_error"] = str(error)[:200]

    return record


async def collect_greenhouse(session, company, slug):
    url = (
        f"https://boards-api.greenhouse.io/v1/boards/"
        f"{slug}/jobs?content=true"
    )
    data = json.loads(await get(session, url))
    records = []

    for job in data.get("jobs", []):
        link = job.get("absolute_url")
        title = job.get("title")

        # first_published is preferred for the 24-hour rule.
        date = parse_date(
            job.get("first_published")
            or job.get("created_at")
        )

        if not link or not title or not recent(date):
            continue

        location = (job.get("location") or {}).get("name", "")

        records.append({
            "id": record_id(link),
            "company": company,
            "title": title,
            "url": link,
            "date": date.isoformat(),
            "description": clean_html(job.get("content", "")),
            "location": location,
            "is_remote": "remote" in location.lower(),
            "role_family": title,
            "record_type": "JOB",
            "source": "Greenhouse",
            "date_field": "first_published_or_created_at",
        })

    return records


async def collect_ashby(session, company, slug):
    url = (
        "https://api.ashbyhq.com/posting-api/job-board/"
        f"{slug}?includeCompensation=true"
    )
    data = json.loads(await get(session, url))
    records = []

    for job in data.get("jobs", []):
        link = job.get("jobUrl") or job.get("applyUrl")
        title = job.get("title")

        date = parse_date(
            job.get("publishedAt")
            or job.get("publishedDate")
        )

        if not link or not title or not recent(date):
            continue

        location = job.get("location", "")

        if isinstance(location, dict):
            location = location.get("location", "")

        description = (
            job.get("descriptionHtml")
            or job.get("descriptionPlain")
            or job.get("description")
            or ""
        )

        records.append({
            "id": record_id(link),
            "company": company,
            "title": title,
            "url": link,
            "date": date.isoformat(),
            "description": clean_html(description),
            "location": location,
            "is_remote": bool(job.get("isRemote")),
            "role_family": job.get("department") or title,
            "record_type": "JOB",
            "source": "Ashby",
            "date_field": "publishedAt",
        })

    return records


async def collect_jobs(session, company, config):
    provider, slug = config
    print(f"[JOBS] {company} ({provider})", flush=True)

    try:
        if provider == "greenhouse":
            records = await collect_greenhouse(
                session, company, slug
            )
        else:
            records = await collect_ashby(
                session, company, slug
            )

        print(f"[JOBS] {company}: {len(records)} recent", flush=True)
        return records

    except Exception as error:
        print(f"[JOB ERROR] {company}: {error}", flush=True)
        return []


async def main():
    timeout = aiohttp.ClientTimeout(total=45)
    connector = aiohttp.TCPConnector(limit=15)

    async with aiohttp.ClientSession(
        timeout=timeout,
        connector=connector,
        headers={"User-Agent": "FrontierAtlas/1.0"}
    ) as session:

        news_results, job_results = await asyncio.gather(
            asyncio.gather(*[
                collect_news(session, name, url)
                for name, url in NEWS_SOURCES.items()
            ]),
            asyncio.gather(*[
                collect_jobs(session, name, config)
                for name, config in JOB_SOURCES.items()
            ])
        )

        news = [
            item for group in news_results for item in group
        ]
        jobs = [
            item for group in job_results for item in group
        ]

        news = list({
            item["id"]: item for item in news
        }.values())

        news = await asyncio.gather(*[
            enrich_article(session, item) for item in news
        ])

    news = [
        item for item in news
        if recent(parse_date(item["published_at"]))
    ]
    jobs = [
        item for item in jobs
        if recent(parse_date(item["date"]))
    ]

    save_json(DATA_DIR / "news.json", news)
    save_json(DATA_DIR / "jobs.json", jobs)

    print("\n========== PHASE II REPORT ==========")
    print("News sources configured:", len(NEWS_SOURCES))
    print("Job boards configured:", len(JOB_SOURCES))
    print("Recent news:", len(news))
    print("Full-text news:", sum(
        item["content_status"] == "FULL_TEXT"
        for item in news
    ))
    print("Recent jobs:", len(jobs))
    print("Job source breakdown:")

    for company in JOB_SOURCES:
        count = sum(
            item["company"] == company for item in jobs
        )
        print(f"  {company}: {count}")

    print("Saved: data/news.json")
    print("Saved: data/jobs.json")
    print("=====================================")


if __name__ == "__main__":
    asyncio.run(main())
