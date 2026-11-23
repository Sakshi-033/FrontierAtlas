
import asyncio
import aiohttp
import json
import os
import re

from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("GITHUB_TOKEN")
INPUT_FILE = Path("data/research_papers.json")

CONCURRENCY = 5
MAX_RETRIES = 4

def get_repo_path(github_url):

    if not github_url:
        return None

    match = re.search(
        r"github\.com/([^/\s]+)/([^/?#]+)",
        github_url
    )

    if not match:
        return None

    owner, repo = match.groups()
    repo = repo.removesuffix(".git").rstrip(".,;:)")

    return f"{owner}/{repo}"

async def fetch_stars(session, repo, semaphore):

    url = f"https://api.github.com/repos/{repo}"

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "FrontierAtlas/1.0"
    }

    async with semaphore:

        for attempt in range(MAX_RETRIES):

            try:

                async with session.get(
                    url,
                    headers=headers
                ) as response:

                    if response.status == 200:
                        data = await response.json()
                        return data.get("stargazers_count")

                    if response.status == 404:
                        return None

                    if response.status in (403, 429):

                        wait = int(
                            response.headers.get(
                                "Retry-After", 2 ** (attempt + 1)
                            )
                        )

                        await asyncio.sleep(wait)
                        continue

                    response.raise_for_status()

            except (
                aiohttp.ClientError,
                asyncio.TimeoutError
            ) as error:

                print(f"Error for {repo}: {error}")
                await asyncio.sleep(2 ** attempt)

        return None

async def main():

    if not TOKEN:
        print("GitHub token not found.")
        return

    if not INPUT_FILE.exists():
        print("Research paper file not found.")
        return

    with INPUT_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:
        papers = json.load(file)

    print("Research papers loaded:", len(papers))

    repositories = {}

    for index, paper in enumerate(papers):

        github_url = paper.get("github_url")
        repo = get_repo_path(github_url)

        if repo:
            repositories[repo] = index

    print("Unique GitHub repositories:", len(repositories))

    semaphore = asyncio.Semaphore(CONCURRENCY)
    timeout = aiohttp.ClientTimeout(total=60)

    updated = 0
    missing = 0

    async with aiohttp.ClientSession(
        timeout=timeout
    ) as session:

        for repo, index in repositories.items():

            stars = await fetch_stars(
                session,
                repo,
                semaphore
            )

            if stars is not None:

                papers[index]["github_stars"] = stars
                updated += 1

            else:
                missing += 1

            if (updated + missing) % 10 == 0:

                with INPUT_FILE.open(
                    "w",
                    encoding="utf-8"
                ) as file:

                    json.dump(
                        papers,
                        file,
                        indent=2,
                        ensure_ascii=False
                    )

                print(
                    f"Processed {updated + missing}/"
                    f"{len(repositories)} repositories"
                )

    with INPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            papers,
            file,
            indent=2,
            ensure_ascii=False
        )

    print("\n========== GITHUB METRICS REPORT ==========")
    print("Total papers:", len(papers))
    print("Unique repositories:", len(repositories))
    print("Successfully retrieved stars:", updated)
    print("Unavailable metrics:", missing)
    print("===========================================")

if __name__ == "__main__":
    asyncio.run(main())