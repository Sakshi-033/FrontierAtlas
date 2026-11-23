
import os
import asyncio
import aiohttp

from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("GITHUB_TOKEN")


async def main():

    if not TOKEN:
        print("ERROR: GitHub token not found.")
        print("Check your .env file.")
        return

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    async with aiohttp.ClientSession() as session:

        async with session.get(
            "https://api.github.com/rate_limit",
            headers=headers
        ) as response:

            print("HTTP status:", response.status)

            if response.status == 200:

                data = await response.json()
                core = data["resources"]["core"]

                print("Authentication successful!")
                print("API requests remaining:", core["remaining"])
                print("Hourly limit:", core["limit"])

            else:
                print("Authentication failed.")
                print("Response:", await response.text())


if __name__ == "__main__":
    asyncio.run(main())
