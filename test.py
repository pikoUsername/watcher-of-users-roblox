import os

from aiohttp import ClientSession


async def main():
    from dotenv import load_dotenv
    load_dotenv()

    cookies = {".ROBLOSECURITY": os.environ["ROBLOX_TOKEN"]}
    async with ClientSession(cookies=cookies) as session:
        home = await session.get("https://www.roblox.com/home")
        text = home.text()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
