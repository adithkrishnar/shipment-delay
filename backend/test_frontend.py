import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        logs = []
        page.on("console", lambda msg: logs.append(f"{msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: logs.append(f"PAGE_ERROR: {err}"))
        
        await page.goto("http://127.0.0.1:5173/login")
        await page.fill("input[type=\"email\"]", "admin@example.com")
        await page.fill("input[type=\"password\"]", "admin123")
        await page.click("button[type=\"submit\"]")
        
        await page.wait_for_timeout(2000)
        await page.goto("http://127.0.0.1:5173/models")
        await page.wait_for_timeout(3000)
        
        print("--- LOGS ---")
        print("\n".join(logs))
        await browser.close()

asyncio.run(main())
