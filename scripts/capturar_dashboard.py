"""Record the Streamlit app as PNG frames for the reel's last scene, with the app running locally.

It needs Playwright, which is not a project dependency:
    pip install playwright && playwright install chromium
    uv run streamlit run dashboard/app.py --server.port 8501 --server.headless true
    python scripts/capturar_dashboard.py
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8501/"
OUT = Path(__file__).resolve().parent.parent / "reel" / "escenas" / "atlas" / "dashboard"
GPU_ARGS = ["--use-angle=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    with sync_playwright() as p:
        browser = p.chromium.launch(args=GPU_ARGS)
        page = browser.new_context(viewport={"width": 1200, "height": 1066}).new_page()
        page.goto(URL)
        page.wait_for_selector("canvas", timeout=90000)
        frame = 0
        for _ in range(40):
            page.wait_for_timeout(700)
            page.screenshot(path=OUT / f"{frame:03d}.png")
            frame += 1
            if page.get_by_role("button", name="Reproducir").count():
                break
        browser.close()
    print(frame, "cuadros ->", OUT)


if __name__ == "__main__":
    main()
