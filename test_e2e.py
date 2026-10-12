# -*- coding: utf-8 -*-
"""E2E 测试：桌面+移动端布局 / 播放 / 进度记忆 / 倍速 / 搜索 / 时长显示"""
import asyncio
import re
import sys

from playwright.async_api import async_playwright

from config import settings

BASE = f"http://127.0.0.1:{settings.PORT}"
PASS, FAIL = [], []


def ok(name, cond, extra=""):
    (PASS if cond else FAIL).append(name + (f" [{extra}]" if extra and not cond else ""))
    print(("PASS " if cond else "FAIL ") + name + (f"  ({extra})" if extra else ""))


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        errors = []

        # ============ 桌面 ============
        pg = await browser.new_page(viewport={"width": 1440, "height": 900})
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.goto(BASE, wait_until="networkidle")

        ok("桌面-列表加载", await pg.locator(".track").count() >= 30,
           str(await pg.locator(".track").count()))
        ok("桌面-分组标题", await pg.locator(".group-title").count() >= 2)
        ok("桌面-交通灯", await pg.locator(".light").count() == 3)
        ok("桌面-时长列", await pg.locator(".track .t-total").count() >= 30)

        # 布局：侧栏在左，内容在右
        sb = await pg.locator(".sidebar").bounding_box()
        ct = await pg.locator(".content").bounding_box()
        ok("桌面-双栏布局", sb and ct and sb["x"] < ct["x"] and sb["width"] > 200,
           f"sidebar x={sb and sb['x']} w={sb and sb['width']}")

        # 点击第一首歌播放
        await pg.locator(".track").first.click()
        await pg.wait_for_timeout(2500)
        playing = await pg.evaluate("() => !document.getElementById('au').paused")
        ok("桌面-点击播放", playing)
        dur = await pg.evaluate("() => document.getElementById('au').duration")
        ok("桌面-时长解析", dur and dur > 600, f"dur={dur}")
        title = await pg.locator("#nowTitle").inner_text()
        ok("桌面-标题更新", len(title) > 3, title[:30])

        # 播放几秒后设进度记忆
        await pg.evaluate("() => { const a=document.getElementById('au'); a.currentTime = 300; }")
        await pg.wait_for_timeout(1500)
        cur = await pg.evaluate("() => document.getElementById('au').currentTime")
        ok("桌面-进度跳转", cur > 290, f"cur={cur}")

        # 倍速
        await pg.locator("#btnRate").click()
        await pg.wait_for_timeout(300)
        ok("桌面-倍速弹层", await pg.locator(".pop").count() == 1)
        await pg.locator(".pbtn").filter(has_text=re.compile(r"^2$")).click()
        await pg.wait_for_timeout(200)
        rate = await pg.evaluate("() => document.getElementById('au').playbackRate")
        ok("桌面-倍速2.0", abs(rate - 2.0) < 0.01, f"rate={rate}")
        btn_txt = await pg.locator("#btnRate").inner_text()
        ok("桌面-倍速按钮显示", "2.0" in btn_txt, btn_txt)
        # 微调
        await pg.locator(".pop #rPlus").click()
        await pg.wait_for_timeout(200)
        rate2 = await pg.evaluate("() => document.getElementById('au').playbackRate")
        ok("桌面-倍速微调2.1", abs(rate2 - 2.1) < 0.01, f"rate={rate2}")
        # 关闭弹层：点击外部
        await pg.mouse.click(10, 400)
        await pg.wait_for_timeout(200)
        ok("桌面-弹层外点关闭", await pg.locator(".pop").count() == 0)

        # 刷新页面 -> 恢复
        await pg.reload(wait_until="networkidle")
        await pg.wait_for_timeout(2500)
        restored_cur = await pg.evaluate("() => document.getElementById('au').currentTime")
        restored_id = await pg.evaluate("() => localStorage.getItem('ka.cur')")
        ok("桌面-刷新恢复曲目", restored_id is not None, str(restored_id)[:30])
        ok("桌面-刷新恢复进度", restored_cur > 290, f"cur={restored_cur}")
        paused = await pg.evaluate("() => document.getElementById('au').paused")
        ok("桌面-刷新不自动播放", paused)

        # 搜索
        await pg.locator("#q").fill("LangGraph")
        await pg.wait_for_timeout(400)
        n = await pg.locator(".track").count()
        ok("桌面-搜索过滤", 2 <= n <= 6, f"n={n}")
        await pg.locator("#qclr").click()
        await pg.wait_for_timeout(300)
        ok("桌面-清除搜索", await pg.locator(".track").count() >= 30)

        # 上一首/下一首
        await pg.locator("#btnNext").click()
        await pg.wait_for_timeout(800)
        t2 = await pg.locator("#nowTitle").inner_text()
        ok("桌面-下一首", t2 != title, f"{title[:15]} -> {t2[:15]}")
        await pg.locator("#btnPrev").click()
        await pg.wait_for_timeout(800)
        t3 = await pg.locator("#nowTitle").inner_text()
        ok("桌面-上一首", t3 == title)

        # 播放模式切换
        modes = []
        for _ in range(4):
            await pg.locator("#btnMode").click()
            await pg.wait_for_timeout(100)
            modes.append(await pg.locator("#btnMode").inner_text())
        ok("桌面-模式循环切换", len(set(modes)) == 4, str(modes))

        await pg.close()

        # ============ 移动端 ============
        pm = await browser.new_page(viewport={"width": 390, "height": 844},
                                    user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
                                    has_touch=True)
        pm.on("pageerror", lambda e: errors.append("M:" + str(e)))
        await pm.goto(BASE, wait_until="networkidle")
        await pm.wait_for_timeout(1200)

        ok("移动-列表加载", await pm.locator(".track").count() >= 30)
        sbm = await pm.locator(".sidebar").bounding_box()
        ctm = await pm.locator(".content").bounding_box()
        ok("移动-播放器在上", sbm and ctm and sbm["y"] > ctm["y"],
           f"content y={ctm and ctm['y']} sidebar y={sbm and sbm['y']}")
        ok("移动-内容不超宽", ctm and ctm["width"] <= 390, f"w={ctm and ctm['width']}")
        hscroll = await pm.evaluate("() => document.documentElement.scrollWidth > window.innerWidth + 2")
        ok("移动-无横向滚动", not hscroll)

        # 播放
        await pm.locator(".track").first.click()
        await pm.wait_for_timeout(2500)
        playing_m = await pm.evaluate("() => !document.getElementById('au').paused")
        ok("移动-点击播放", playing_m)

        # 倍速
        await pm.locator("#btnRate").click()
        await pm.wait_for_timeout(300)
        popb = await pm.locator(".pop").bounding_box()
        ok("移动-倍速弹层视口内", popb and popb["x"] >= 0 and popb["x"] + popb["width"] <= 390,
           f"{popb}")
        await pm.locator(".pbtn").filter(has_text=re.compile(r"^1\.5$")).click()
        await pm.wait_for_timeout(200)
        rate_m = await pm.evaluate("() => document.getElementById('au').playbackRate")
        ok("移动-倍速1.5", abs(rate_m - 1.5) < 0.01, f"rate={rate_m}")

        await pm.close()
        await browser.close()

        print("\n========== 结果 ==========")
        print(f"PASS: {len(PASS)}  FAIL: {len(FAIL)}")
        if errors:
            print("JS错误:", errors)
        if FAIL:
            print("失败项:", FAIL)
            sys.exit(1)
        print("全部通过 ✅")


asyncio.run(main())
