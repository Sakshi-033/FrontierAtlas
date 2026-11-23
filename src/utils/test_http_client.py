
import asyncio
import os

from dotenv import load_dotenv
from src.utils.http_client import AsyncHTTPClient


async def main():
    load_dotenv()

    token = os.getenv("GITHUB_TOKEN")

    if not token:
        print("ERROR: GITHUB_TOKEN not found in .env")
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    async with AsyncHTTPClient(
        concurrency=5,
        max_retries=3
    ) as client:

        print("Testing authenticated GitHub API...")

        result = await client.fetch(
            "https://api.github.com/rate_limit",
            response_type="json",
            headers=headers
        )

        print("\nGitHub API: SUCCESS")
        print(
            "Remaining requests:",
            result["resources"]["core"]["remaining"]
        )

        print("\nTesting HTTPBin...")

        httpbin = await client.fetch(
            "https://httpbin.org/json",
            response_type="json"
        )

        print("HTTPBin: SUCCESS")
        print("Response type:", type(httpbin).__name__)


if __name__ == "__main__":
    asyncio.run(main())
