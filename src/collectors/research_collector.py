
import asyncio
import json
import os
import re
import time

import feedparser

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from src.utils.http_client import AsyncHTTPClient


# ==========================================
# CONFIGURATION
# ==========================================

load_dotenv()

ARXIV_URL = "https://export.arxiv.org/api/query"
GITHUB_API = "https://api.github.com/repos"

OUTPUT_FILE = Path("data/research_papers.json")

MAX_RESULTS = 1500
CONCURRENCY = 20
GITHUB_CONCURRENCY = 3


# ==========================================
# EXISTING DATA
# ==========================================

def load_existing():
    """Load existing papers so previous metrics are not lost."""

    if not OUTPUT_FILE.exists():
        return []

    with OUTPUT_FILE.open("r", encoding="utf-8") as file:
        records = json.load(file)

    if not isinstance(records, list):
        raise ValueError(
            "Research paper file must contain a JSON list."
        )

    return records


def save_records(records):
    """Save records atomically."""

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


# ==========================================
# GITHUB REPOSITORY EXTRACTION
# ==========================================

def extract_github_url(text):
    """Extract and normalize a GitHub repository URL."""

    pattern = (
        r"https?://github\.com/"
        r"([A-Za-z0-9_.-]+)/"
        r"([A-Za-z0-9_.-]+)"
    )

    match = re.search(
        pattern,
        text or "",
        re.IGNORECASE
    )

    if not match:
        return None

    owner = match.group(1)
    repo = match.group(2).rstrip(".,;:!?)")

    repo = repo.removesuffix(".git")

    if not owner or not repo:
        return None

    if owner.lower() in {
        "features",
        "topics",
        "collections",
        "orgs"
    }:
        return None

    return f"https://github.com/{owner}/{repo}"


def repository_key(github_url):
    """Create a consistent owner/repository identifier."""

    if not github_url:
        return None

    parsed = urlparse(github_url)

    parts = parsed.path.strip("/").split("/")

    if len(parts) < 2:
        return None

    owner = parts[0]
    repo = parts[1].removesuffix(".git")

    if not owner or not repo:
        return None

    return f"{owner.lower()}/{repo.lower()}"


# ==========================================
# FETCH ARXIV PAPERS
# ==========================================

async def fetch_arxiv_papers(client):
    """Fetch recent AI research papers from arXiv."""

    params = {
        "search_query": "cat:cs.AI",
        "start": 0,
        "max_results": MAX_RESULTS,
        "sortBy": "submittedDate",
        "sortOrder": "descending"
    }

    xml_data = await client.fetch(
        ARXIV_URL,
        response_type="text",
        params=params
    )

    feed = feedparser.parse(xml_data)

    if feed.bozo and not feed.entries:
        raise ValueError("Invalid arXiv feed response.")

    return feed.entries


# ==========================================
# FETCH CURRENT GITHUB STARS
# ==========================================

async def fetch_github_stars(
    client,
    github_url,
    semaphore,
    token
):
    """Retrieve current GitHub stars for a repository."""

    key = repository_key(github_url)

    if not key:
        return None

    api_url = f"{GITHUB_API}/{key}"

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "FrontierAtlas/1.0"
    }

    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with semaphore:

        try:
            data = await client.fetch(
                api_url,
                response_type="json",
                headers=headers
            )

            stars = data.get("stargazers_count")

            if isinstance(stars, int) and stars >= 0:
                return stars

            return None

        except Exception as error:
            print(
                f"GitHub metrics unavailable for {key}: {error}"
            )
            return None


# ==========================================
# PROCESS ARXIV ENTRIES
# ==========================================

def process_paper(entry):
    """Convert an arXiv entry into a research paper record."""

    title = entry.get("title", "")
    title = title.replace("\n", " ").strip()

    if not title:
        return None

    authors = [
        author.get("name")
        for author in entry.get("authors", [])
        if author.get("name")
    ]

    if not authors:
        authors = ["Unknown"]

    paper_url = entry.get("id")

    if not paper_url:
        return None

    published = entry.get("published")

    if not published:
        return None

    published_date = datetime.fromisoformat(
        published.replace("Z", "+00:00")
    )

    if published_date.tzinfo is None:
        published_date = published_date.replace(
            tzinfo=timezone.utc
        )

    comments = entry.get("arxiv_comment", "")
    summary = entry.get("summary", "")

    github_url = extract_github_url(
        comments + " " + summary
    )

    if not github_url:

        for link in entry.get("links", []):

            href = link.get("href", "")

            if "github.com/" in href:
                github_url = extract_github_url(href)

                if github_url:
                    break

    return {
        "title": title,
        "authors": authors,
        "paper_url": paper_url,
        "github_url": github_url,
        "github_stars": None,
        "published_date": published_date
    }


# ==========================================
# MAIN COLLECTOR
# ==========================================

async def main():

    print("Starting research paper collection...")

    existing = load_existing()

    print("Previously collected papers:", len(existing))

    # Preserve previously retrieved star counts.
    old_stars = {}

    for record in existing:

        if not isinstance(record, dict):
            continue

        key = repository_key(record.get("github_url"))
        stars = record.get("github_stars")

        if key and isinstance(stars, int) and stars >= 0:
            old_stars[key] = stars

    github_token = os.getenv("GITHUB_TOKEN")

    if not github_token:
        print(
            "WARNING: GITHUB_TOKEN not found. "
            "GitHub API requests will be unauthenticated."
        )

    github_semaphore = asyncio.Semaphore(
        GITHUB_CONCURRENCY
    )

    async with AsyncHTTPClient(
        concurrency=CONCURRENCY,
        max_retries=4,
        timeout=180
    ) as client:

        print("\nFetching papers from arXiv...")

        entries = await fetch_arxiv_papers(client)

        print("Papers received from arXiv:", len(entries))

        # Deduplicate papers by arXiv URL.
        papers_by_url = {}

        for entry in entries:

            try:
                paper = process_paper(entry)

                if paper:
                    papers_by_url[paper["paper_url"]] = paper

            except Exception as error:
                print("Paper parsing error:", error)

        papers = list(papers_by_url.values())

        # Find unique GitHub repositories.
        unique_repositories = {}

        for paper in papers:

            key = repository_key(paper["github_url"])

            if key and key not in unique_repositories:
                unique_repositories[key] = paper["github_url"]

        print("Unique papers:", len(papers))
        print(
            "Unique GitHub repositories:",
            len(unique_repositories)
        )

        # Fetch stars only once per unique repository.
        tasks = {
            key: fetch_github_stars(
                client,
                github_url,
                github_semaphore,
                github_token
            )
            for key, github_url in unique_repositories.items()
        }

        results = await asyncio.gather(
            *tasks.values(),
            return_exceptions=True
        )

    # ==========================================
    # PRESERVE AND UPDATE STAR METRICS
    # ==========================================

    updated_metrics = 0
    preserved_metrics = 0

    star_results = {}

    for key, result in zip(tasks.keys(), results):

        if isinstance(result, Exception):
            result = None

        if result is not None:
            star_results[key] = result
            updated_metrics += 1

        elif key in old_stars:
            star_results[key] = old_stars[key]
            preserved_metrics += 1

    for paper in papers:

        key = repository_key(paper["github_url"])

        if key:
            paper["github_stars"] = star_results.get(key)

    # Convert dates into JSON-compatible strings.
    records = [
        {
            **paper,
            "published_date": paper["published_date"].isoformat()
        }
        for paper in papers
    ]

    save_records(records)

    # ==========================================
    # REPORT
    # ==========================================

    papers_with_github = sum(
        paper["github_url"] is not None
        for paper in papers
    )

    papers_with_stars = sum(
        paper["github_stars"] is not None
        for paper in papers
    )

    print("\n========== RESEARCH PAPER REPORT ==========")
    print("Papers received:", len(entries))
    print("Unique papers:", len(records))
    print("Unique GitHub repositories:", len(unique_repositories))
    print("Papers with GitHub links:", papers_with_github)
    print(
        "Papers with current or preserved star metrics:",
        papers_with_stars
    )
    print("New GitHub metrics retrieved:", updated_metrics)
    print("Old metrics preserved:", preserved_metrics)
    print("Saved to:", OUTPUT_FILE)
    print("===========================================")

    if len(records) >= 1000:
        print("SUCCESS: Research paper target achieved!")
    else:
        print("WARNING: Research paper target not reached.")

    if papers_with_stars < 1000:
        print(
            "NOTE: The 1,000-paper count is achieved, "
            "but 1,000 GitHub star metrics are not yet available."
        )


if __name__ == "__main__":
    asyncio.run(main())
