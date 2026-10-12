# -*- coding: utf-8 -*-
"""截图工具：桌面 + 移动端，输出到 CACHE_DIR。"""
import asyncio

from playwright.async_api import async_playwright

from config import settings

BASE = f"http://127.0.0.1:{settings.PORT}"


async def main():
    out = settings.CACHE_DIR
    out.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        # 桌面
        pg = await browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        await pg.goto(BASE, wait_until="networkidle")
        await pg.wait_for_timeout(800)
        await pg.locator(".track").nth(5).click()
        await pg.wait_for_timeout(2500)
        await pg.screenshot(path=str(out / "shot-desktop.png"))
        # 桌面-倍速弹层
        await pg.locator("#btnRate").click()
        await pg.wait_for_timeout(400)
        await pg.screenshot(path=str(out / "shot-desktop-rate.png"))
        await pg.close()
        # 移动端
        pm = await browser.new_page(viewport={"width": 390, "height": 844},
                                    user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
                                    has_touch=True, device_scale_factor=2)
        await pm.goto(BASE, wait_until="networkidle")
        await pm.wait_for_timeout(800)
        await pm.locator(".track").first.click()
        await pm.wait_for_timeout(2500)
        await pm.screenshot(path=str(out / "shot-mobile.png"))
        await pm.close()
        await browser.close()
        print(f"done -> {out}")


asyncio.run(main())
