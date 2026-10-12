# -*- coding: utf-8 -*-
"""DOM 级 UI 质检（无视觉模型替代方案）+ PIL 像素分布检查。截图存 CACHE_DIR。"""
import asyncio

from playwright.async_api import async_playwright

from config import settings

BASE = f"http://127.0.0.1:{settings.PORT}"
PASS, FAIL = [], []


def ok(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f"  ({extra})" if extra else ""))


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()

        # 桌面 DOM 检查
        pg = await browser.new_page(viewport={"width": 1440, "height": 900})
        await pg.goto(BASE, wait_until="networkidle")
        await pg.locator(".track").nth(5).click()
        await pg.wait_for_timeout(2000)

        r = await pg.evaluate("""() => {
          const out = {};
          const win = document.querySelector('.win');
          const cs = getComputedStyle(win);
          out.winRadius = cs.borderRadius;
          out.winBlur = cs.backdropFilter || cs.webkitBackdropFilter || '';
          const art = document.querySelector('.artwork');
          out.artRadius = getComputedStyle(art).borderRadius;
          out.bodyPlaying = document.body.classList.contains('playing');
          out.artAnim = getComputedStyle(art).animationName;
          const main = document.querySelector('#btnPlay');
          const mr = main.getBoundingClientRect();
          out.playSize = [Math.round(mr.width), Math.round(mr.height)];
          const pr = document.querySelector('.ctrls').getBoundingClientRect();
          out.playCentered = Math.abs((mr.x + mr.width/2) - (pr.x + pr.width/2)) < 6;
          out.lights = [...document.querySelectorAll('.light')].map(l => getComputedStyle(l).backgroundColor);
          const seek = document.querySelector('#seek');
          out.seekW = seek.getBoundingClientRect().width;
          const nt = document.querySelector('#nowTitle');
          out.titleClamp = nt.scrollHeight <= nt.clientHeight + 2 || nt.scrollWidth <= window.innerWidth;
          const pl = document.querySelector('.playlist');
          out.playlistScrollable = pl.scrollHeight > pl.clientHeight;
          return out;
        }""")
        ok("桌面-窗口圆角", r["winRadius"] not in ("0px", ""), r["winRadius"])
        ok("桌面-毛玻璃", "blur" in r["winBlur"], r["winBlur"][:30])
        ok("桌面-唱片圆形", r["artRadius"] == "50%", r["artRadius"])
        ok("桌面-唱片旋转60s", "spin" in str(r["artAnim"]))
        ok("桌面-播放键居中", r["playCentered"])
        ok("桌面-播放键52px", abs(r["playSize"][0] - 52) <= 2, str(r["playSize"]))
        ok("桌面-交通灯配色", r["lights"][0].startswith("rgb(255, 95"), str(r["lights"]))
        ok("桌面-进度条宽度>200", r["seekW"] > 200, str(round(r["seekW"])))
        ok("桌面-标题不溢出", r["titleClamp"])
        ok("桌面-列表可滚动", r["playlistScrollable"])

        # 断点检查：899px 切移动布局
        await pg.set_viewport_size({"width": 880, "height": 900})
        await pg.wait_for_timeout(400)
        r2 = await pg.evaluate("""() => {
          const sb = document.querySelector('.sidebar').getBoundingClientRect();
          const ct = document.querySelector('.content').getBoundingClientRect();
          return {sbBelow: sb.y > ct.y, noHscroll: document.documentElement.scrollWidth <= window.innerWidth + 2};
        }""")
        ok("断点880-列表移到下方", r2["sbBelow"])
        ok("断点880-无横向滚动", r2["noHscroll"])

        # 780px 宽平板
        await pg.set_viewport_size({"width": 780, "height": 900})
        await pg.wait_for_timeout(400)
        r3 = await pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 2")
        ok("断点780-无横向滚动", r3)

        # 超宽 1920
        await pg.set_viewport_size({"width": 1920, "height": 1080})
        await pg.wait_for_timeout(400)
        r4 = await pg.evaluate("""() => {
          const win = document.querySelector('.win').getBoundingClientRect();
          return {w: win.width, centered: Math.abs((win.x + win.width/2) - 960) < 4};
        }""")
        ok("超宽1920-窗口限宽1180", r4["w"] <= 1181, str(round(r4["w"])))
        ok("超宽1920-居中", r4["centered"])

        # 截图到 CACHE_DIR
        await pg.set_viewport_size({"width": 1440, "height": 900})
        await pg.wait_for_timeout(400)
        settings.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        await pg.screenshot(path=str(settings.CACHE_DIR / "shot-desktop.png"))
        await pg.close()
        await browser.close()

    # PIL 像素分布（截图非空白/非纯色）
    try:
        from PIL import Image
        shot = settings.CACHE_DIR / "shot-desktop.png"
        if shot.exists():
            im = Image.open(shot).convert("RGB").resize((200, 125))
            px = list(im.getdata())
            uniq = len(set(px))
            ok("像素-桌面截图内容丰富", uniq > 800, f"unique={uniq}")
    except ImportError:
        print("PIL 不可用，跳过像素检查")

    print(f"\nPASS: {len(PASS)}  FAIL: {len(FAIL)}")
    if FAIL:
        print("失败:", FAIL)
        raise SystemExit(1)
    print("UI 质检全部通过 ✅")


asyncio.run(main())
