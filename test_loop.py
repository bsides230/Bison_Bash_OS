import asyncio
import time
from playwright.async_api import async_playwright
import requests

async def main():
    print("Setting state to Betting_Open")
    r1 = requests.post("http://localhost:8001/api/bisondash/state/update", json={"state": "Betting_Open"})
    print(r1.status_code, r1.json())
    time.sleep(1)

    print("Setting state to Closed_Intros")
    r2 = requests.post("http://localhost:8001/api/bisondash/state/update", json={"state": "Closed_Intros"})
    print(r2.status_code, r2.json())
    time.sleep(1)

    print("Setting state to Race_Sprint")
    r3 = requests.post("http://localhost:8001/api/bisondash/state/update", json={"state": "Race_Sprint"})
    print(r3.status_code, r3.json())

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        page.on("console", lambda msg: print(f"Browser console: {msg.text}"))

        print("Opening projector")
        await page.goto("http://localhost:8001/projector")
        await page.wait_for_timeout(5000)

        await page.screenshot(path="/home/jules/verification/screenshots/test_sprint4.png")

        await context.close()
        await browser.close()

asyncio.run(main())
