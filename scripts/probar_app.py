"""Browser checks of the Streamlit app: every control must change the page, with no exceptions and no console errors.

Needs Playwright, which is not a project dependency, and the app running locally:
    pip install playwright && playwright install chromium
    uv run streamlit run dashboard/app.py --server.port 8501 --server.headless true
    python scripts/probar_app.py [url]
"""
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8501/"
OUT = Path(tempfile.gettempdir()) / "huella_app_shots"
OUT.mkdir(exist_ok=True)
FAILS = []
GPU = ["--use-angle=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"]


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILS.append(name)


def kpis(page):
    return page.locator(".kpis").inner_text().replace("\n", " ")


def settle(page, ms=1200):
    page.wait_for_timeout(ms)
    page.wait_for_function("!document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=60000)
    page.wait_for_timeout(300)


def wait_for_text(page, selector, text, timeout=45000):
    """The app answers in about a second on a laptop and later on a slow link, so checks wait for the change itself."""
    try:
        page.locator(selector, has_text=text).first.wait_for(timeout=timeout)
    except Exception:
        pass
    page.wait_for_timeout(250)


def choose(page, label, option):
    box = page.get_by_role("combobox", name=label)
    box.click()
    page.wait_for_timeout(250)
    box.fill(option) if box.is_editable() else None
    page.wait_for_timeout(250)
    page.get_by_role("option", name=option, exact=False).first.click()
    settle(page)


with sync_playwright() as p:
    browser = p.chromium.launch(args=GPU)
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "font" not in m.text.lower() else None)
    page.goto(URL)
    page.wait_for_selector(".kpis", timeout=120000)
    first_kpis = kpis(page)
    page.evaluate("""() => {
      window.yearGap = {longest: 0, since: null};
      const tick = () => {
        const slider = document.querySelector('[data-testid="stSliderThumbValue"]')?.textContent;
        const label = document.querySelector('.big-year')?.textContent;
        const gap = window.yearGap, now = performance.now();
        if (slider && label && slider !== label) {
          gap.since ??= now;
          gap.longest = Math.max(gap.longest, now - gap.since);
        } else {
          gap.since = null;
        }
        requestAnimationFrame(tick);
      };
      tick();
    }""")
    page.screenshot(path=OUT / "1_start.png")
    print("  first:", first_kpis[:90])
    seen = set()
    for _ in range(120):
        seen.add(page.locator(".big-year").inner_text())
        if "2025" in seen and page.get_by_role("button", name="Reproducir").count():
            break
        page.wait_for_timeout(150)
    print("  years seen:", sorted(seen))
    check("autoplay shows most years on the way", len(seen) >= 8, str(len(seen)))

    # Autoplay reaches the last year on its own
    page.wait_for_selector("button:has-text('Reproducir')", timeout=120000)
    settle(page)
    final = kpis(page)
    check("autoplay ends in 2025 with the national figures", "1,985" in final and "×2.7" in final and "310" in final and "73 %" in final, final[:120])
    check("autoplay started earlier than the end", "2025" not in first_kpis, first_kpis[:40])
    year_gap = page.evaluate("window.yearGap.longest")
    check("the slider and the year on the map change together", year_gap < 1000, f"{year_gap:.0f} ms")
    check("no exception box after playing", page.locator('[data-testid="stException"]').count() == 0)
    page.screenshot(path=OUT / "2_end_2025.png")

    # Slider
    def set_year(target):
        thumb = page.locator('[data-testid="stSlider"] input[type="range"]').first
        current = int(thumb.get_attribute("value"))
        thumb.focus()
        for _ in range(abs(target - current)):
            page.keyboard.press("ArrowLeft" if target < current else "ArrowRight")
            page.wait_for_timeout(40)
        wait_for_text(page, ".big-year", str(target))

    set_year(2018)
    check("slider changes the KPI", "1,041" in kpis(page) and "2018" in kpis(page), kpis(page)[:60])
    set_year(2025)
    check("slider returns to the last year", "1,985" in kpis(page), kpis(page)[:60])

    # Pause
    page.get_by_role("button", name="Reproducir").click()
    wait_for_text(page, ".big-year", "2014")
    page.get_by_role("button", name="Pausar").click()
    page.get_by_role("button", name="Reproducir").wait_for(timeout=30000)
    page.wait_for_timeout(5000)  # the numeral is drawn after the map, so give the last frame time to arrive
    paused = page.locator(".big-year").inner_text()
    page.wait_for_timeout(3000)
    check("pause holds the year", page.locator(".big-year").inner_text() == paused and paused != "2025", paused)
    set_year(2025)

    # Department
    choose(page, "Departamento", "Madre de Dios")
    wait_for_text(page, ".scope", "Madre de Dios")
    check("department changes the KPI", "1,130" in kpis(page), kpis(page)[:70])
    check("department has no false top ten", "solo 6 distritos" in kpis(page), kpis(page)[-50:])
    check("department changes the trend title", page.get_by_text("Madre de Dios: de 336 a 1,130 km²").count() > 0)
    page.wait_for_timeout(1500)
    page.screenshot(path=OUT / "3_madre_de_dios.png")

    # Indicator
    for option, title in (("Huella nueva", "donde más creció"), ("Luz nocturna", "más luz por km²"), ("Pobreza monetaria", "mayor pobreza")):
        choose(page, "Mostrar en el mapa", option)
        check(f"indicator {option} changes the ranking", page.get_by_text(title).count() > 0)
        check(f"indicator {option} changes the legend", option.split()[0] in page.locator(".legend").inner_text())
        page.wait_for_timeout(800)
        page.screenshot(path=OUT / f"4_{option.split()[0]}.png")
    choose(page, "Mostrar en el mapa", "Huella minera")
    choose(page, "Departamento", "Todo el Perú")

    # Search
    choose(page, "Buscar distrito", "Inambari, Tambopata")
    wait_for_text(page, ".card", "Inambari")
    check("search opens the card", page.locator(".card").count() == 1 and "Inambari" in page.locator(".card").inner_text(), page.locator(".card").inner_text()[:80] if page.locator(".card").count() else "")
    page.wait_for_timeout(1500)
    page.screenshot(path=OUT / "5_inambari.png")
    page.get_by_role("button", name="Cerrar la ficha").click()
    settle(page)
    check("the card closes", page.locator(".card").count() == 0)

    # Tooltip over the Andes
    settle(page)
    page.locator("h1").scroll_into_view_if_needed()
    page.wait_for_timeout(1500)
    box = page.locator('[data-testid="stDeckGlJsonChart"]').first.bounding_box()
    page.mouse.move(box["x"] + box["width"] * 0.48, box["y"] + box["height"] * 0.40)
    page.wait_for_timeout(1200)
    tooltip = page.locator(".deck-tooltip")
    check("the map names the district under the pointer", tooltip.count() > 0 and "Huella minera" in tooltip.first.inner_text(),
          tooltip.first.inner_text().replace("\n", " ") if tooltip.count() else "no tooltip")
    page.screenshot(path=OUT / "6_tooltip.png")

    # Download
    with page.expect_download() as download:
        page.get_by_role("button", name="Descargar estos distritos").click()
    lines = Path(download.value.path()).read_text(encoding="utf-8").strip().split("\n")
    check("CSV has a row for each district", len(lines) == 1899, str(len(lines)))

    page.screenshot(path=OUT / "7_full.png", full_page=True)
    page.locator("text=Lo que muestran los datos").scroll_into_view_if_needed()
    page.wait_for_timeout(600)
    page.screenshot(path=OUT / "8_findings.png")
    page.locator("text=¿Se puede confiar").scroll_into_view_if_needed()
    page.wait_for_timeout(600)
    page.screenshot(path=OUT / "9_contrast.png")
    check("no exceptions on the page", page.locator('[data-testid="stException"]').count() == 0)
    check("no console errors at 1440", not errors, "; ".join(errors)[:300])

    phone = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True).new_page()
    phone.goto(URL)
    phone.wait_for_selector(".kpis", timeout=120000)
    phone.wait_for_selector("button:has-text('Reproducir')", timeout=120000)
    phone.wait_for_timeout(1500)
    width = phone.evaluate("document.documentElement.scrollWidth")
    check("no horizontal scroll at 390", width <= 392, str(width))
    phone.screenshot(path=OUT / "10_phone.png")
    browser.close()

print(f"\n{len(FAILS)} failed: {FAILS}")
print("shots:", OUT)
sys.exit(1 if FAILS else 0)
