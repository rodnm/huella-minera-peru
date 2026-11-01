"""Record the dashboard as PNG frames for the reel's last scene, with the page served locally.

It needs Playwright, which is not a project dependency:
    pip install playwright && playwright install chromium
    python -m http.server 8765 -d web
    python scripts/capturar_dashboard.py
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8765/"
OUT = Path(__file__).resolve().parent.parent / "reel" / "escenas" / "atlas" / "dashboard"
GPU_ARGS = ["--use-angle=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=GPU_ARGS)
        page = browser.new_context(viewport={"width": 1080, "height": 960}, reduced_motion="reduce").new_page()
        page.goto(URL)
        page.wait_for_function("document.querySelectorAll('#findings li').length === 3", timeout=60000)
        page.wait_for_timeout(1500)
        frame = 0
        for year in range(2019, 2026):
            page.evaluate("y => { state.year = y; refresh(); }", year)
            page.wait_for_timeout(350)
            page.screenshot(path=OUT / f"{frame:03d}.png")
            frame += 1
        page.fill("#search", "Inambari, Tambopata, Madre de Dios")
        page.press("#search", "Tab")
        for _ in range(6):
            page.wait_for_timeout(250)
            page.screenshot(path=OUT / f"{frame:03d}.png")
            frame += 1
        browser.close()
    print(frame, "cuadros ->", OUT)


if __name__ == "__main__":
    main()
