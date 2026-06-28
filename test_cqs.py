import asyncio
import os
import re
import aiohttp
from dotenv import load_dotenv

load_dotenv("env")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
USER_AGENT = 'Mozilla/5.0 (compatible; DiscordBot/1.0)'

async def get_reddit_token():
    auth = aiohttp.BasicAuth(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET)
    data = {'grant_type': 'client_credentials'}
    headers = {'User-Agent': USER_AGENT}
    async with aiohttp.ClientSession() as session:
        async with session.post('https://www.reddit.com/api/v1/access_token', auth=auth, data=data, headers=headers) as resp:
            if resp.status == 200:
                js = await resp.json()
                return js.get('access_token')
    return None

async def test_cqs(cqs_url):
    token = await get_reddit_token()
    headers = {'Authorization': f'Bearer {token}', 'User-Agent': USER_AGENT}
    print(f"Resolving: {cqs_url}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(cqs_url, headers=headers, allow_redirects=True) as resp:
                final_url = str(resp.url)
    except Exception as e:
        print("Resolve error:", e)
        return
    print(f"Final: {final_url}")
    post_id = final_url.split("/comments/")[1].split("/")[0].split("?")[0]
    print(f"Post ID: {post_id}")
    json_url = f"https://oauth.reddit.com/comments/{post_id}?limit=50&depth=5"
    print(f"JSON URL: {json_url}")
    async with aiohttp.ClientSession() as session:
        async with session.get(json_url, headers=headers) as resp:
            print("Status:", resp.status)
            data = await resp.json()
            if resp.status != 200:
                print(data)
                return
    import json
    print(json.dumps(data)[:500])
    
# Run via python3 environment that has aiohttp, or we can use sys.path
