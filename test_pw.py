import asyncio
import json
from playwright.async_api import async_playwright

url = 'https://www.reddit.com/r/TwentiesIndia/comments/1dl5862/the_fear_of_unknown/'

async def main():
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        # Using a mobile user agent
        page = await browser.new_page(
            user_agent='Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36',
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"}
        )
        
        gql_responses = []

        async def handle_response(response):
            if 'gql.reddit.com' in response.url:
                try:
                    data = await response.json()
                    gql_responses.append(data)
                except Exception as e:
                    pass

        page.on("response", handle_response)
        
        await page.goto(url, wait_until='networkidle')
        # scroll a bit
        await page.mouse.wheel(0, 500)
        await page.wait_for_timeout(5000)
        
        with open("gql_data.json", "w") as f:
            json.dump(gql_responses, f, indent=2)
            
        await browser.close()

asyncio.run(main())
