"""Browser checks of the atlas: every control must change what the page shows, with no console errors.

Needs Playwright, which is not a project dependency, and the page served locally:
    pip install playwright && playwright install chromium
    python -m http.server 8765 -d web
    python scripts/probar_web.py
"""
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/"
OUT = Path(tempfile.gettempdir()) / "huella_web_shots"
OUT.mkdir(exist_ok=True)
FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILS.append(name)


def text(page, selector):
    return page.locator(selector).inner_text().replace("\n", " ")


def set_range(page, value):
    page.evaluate("v => { const e = document.getElementById('year'); e.value = v; e.dispatchEvent(new Event('input', {bubbles:true})); }", value)
    page.wait_for_timeout(250)


with sync_playwright() as p:
    browser = p.chromium.launch(args=["--use-angle=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"])
    context = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    page = context.new_page()
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("requestfailed", lambda r: errors.append("failed: " + r.url))
    page.goto(URL)
    page.wait_for_function("document.querySelectorAll('#findings li').length === 3", timeout=60000)
    page.wait_for_timeout(2500)
    page.screenshot(path=OUT / "1_hero_2025.png")

    check("reduced motion starts at the last year", page.input_value("#year") == "2025")
    base_area = text(page, "#kpi-area")
    base_change = text(page, "#kpi-change")
    base_districts = text(page, "#kpi-districts")
    base_top = text(page, "#kpi-top")
    check("national 2025 is 1,985 km2", "1,985" in base_area, base_area)
    check("national ratio is x2.7", "×2.7" in base_change, base_change)
    check("310 districts, 215 in 2013", "310" in base_districts and "215" in base_districts, base_districts)
    check("top ten explain 73 %", "73 %" in base_top, base_top)
    print("  findings:", " | ".join(page.locator("#findings li").all_inner_texts())[:900])
    print("  contrast:", text(page, "#contrast-text")[:900])
    print("  method:", text(page, "#method-check"))

    # Year control
    set_range(page, 2018)
    check("year changes the KPI", text(page, "#kpi-area") != base_area, text(page, "#kpi-area"))
    check("year changes the big numeral", text(page, "#big-year") == "2018")
    rank_2018 = text(page, "#rank")
    set_range(page, 2025)
    check("year changes the ranking", text(page, "#rank") != rank_2018)

    # Play control
    set_range(page, 2023)
    page.click("#play")
    page.wait_for_timeout(1900)
    check("play advances the year", page.input_value("#year") == "2025", page.input_value("#year"))
    check("play stops and offers replay", text(page, "#play") == "Reproducir", text(page, "#play"))

    # Department control
    trend_all = text(page, "#trend-title")
    page.select_option("#department", "MADRE DE DIOS")
    page.wait_for_timeout(1200)
    check("department changes the KPI", "1,130" in text(page, "#kpi-area"), text(page, "#kpi-area"))
    check("department changes the trend", text(page, "#trend-title") != trend_all, text(page, "#trend-title"))
    check("department limits the ranking", "Moquegua" not in text(page, "#rank"))
    page.screenshot(path=OUT / "2_madre_de_dios.png")

    # Indicator control
    rank_huella = text(page, "#rank")
    legend_huella = text(page, "#legend")
    for value, name in (("nueva", "new"), ("luz", "light"), ("pobreza", "poverty")):
        page.select_option("#indicator", value)
        page.wait_for_timeout(700)
        check(f"indicator {name} changes the ranking", text(page, "#rank") != rank_huella)
        check(f"indicator {name} changes the legend", text(page, "#legend") != legend_huella, text(page, "#legend")[:70])
        page.screenshot(path=OUT / f"3_indicator_{name}.png")
    page.select_option("#indicator", "huella")

    # Search control
    page.select_option("#department", "")
    page.wait_for_timeout(300)
    page.fill("#search", "Inambari, Tambopata, Madre de Dios")
    page.press("#search", "Tab")
    page.wait_for_timeout(1300)
    check("search opens the card", page.locator("#card").is_visible() and "Inambari" in text(page, "#card"), text(page, "#card")[:120])
    check("search adds the district to the trend", "Inambari" in page.locator("#trend svg").text_content(), "")
    page.screenshot(path=OUT / "4_inambari.png")
    page.click(".card-close")
    check("card closes", not page.locator("#card").is_visible())

    # Search by name alone, and a clear message when it fails
    page.fill("#search", "inambari")
    page.press("#search", "Enter")
    page.wait_for_timeout(300)
    check("a unique name found with Enter", "Inambari" in text(page, "#card"), text(page, "#card")[:40])
    page.fill("#search", "zzz")
    page.press("#search", "Enter")
    page.wait_for_timeout(200)
    check("an unknown name explains itself", "No se encontró" in text(page, "#search-note"), text(page, "#search-note"))
    page.fill("#search", "")
    page.press("#search", "Enter")
    page.click(".card-close")

    # Download
    with page.expect_download() as download:
        page.click("#download")
    path = download.value.path()
    lines = Path(path).read_text(encoding="utf-8").strip().split("\n")
    check("CSV has a row for each district", len(lines) == 1 + 1898, str(len(lines)))
    check("CSV names the year", download.value.suggested_filename.endswith("2025.csv"), download.value.suggested_filename)

    # Rank and department rows select things
    page.locator("#departments .bar").nth(1).click()
    page.wait_for_timeout(1000)
    check("clicking a department row filters", page.input_value("#department") != "", page.input_value("#department"))
    page.select_option("#department", "")
    page.wait_for_timeout(1000)

    page.screenshot(path=OUT / "5_full.png", full_page=True)
    page.evaluate("document.querySelector('.charts').scrollIntoView()")
    page.wait_for_timeout(400)
    box = page.locator("#trend svg").bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.wait_for_timeout(250)
    check("trend shows a tooltip on hover", page.locator("#trend .chart-tip").is_visible(), text(page, "#trend .chart-tip"))
    page.screenshot(path=OUT / "6_charts.png")

    check("no console errors at 1440", not errors, "; ".join(errors)[:300])

    # First visit: the map plays once by itself
    moving = browser.new_context(viewport={"width": 1440, "height": 900})
    first = moving.new_page()
    first.goto(URL)
    first.wait_for_function("document.querySelectorAll('#findings li').length === 3", timeout=60000)
    start = int(first.input_value("#year"))
    first.wait_for_function("document.getElementById('year').value === '2025' && document.getElementById('play').textContent === 'Reproducir'", timeout=30000)
    check("autoplay runs from the first years to 2025", start < 2020, str(start))
    first.select_option("#department", "MADRE DE DIOS")
    first.wait_for_timeout(300)
    check("a department with few districts does not claim a top ten", "100 %" not in text(first, "#kpi-top"), text(first, "#kpi-top"))

    # Mobile
    mobile = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, reduced_motion="reduce", has_touch=True)
    phone = mobile.new_page()
    phone_errors = []
    phone.on("console", lambda m: phone_errors.append(m.text) if m.type == "error" else None)
    phone.on("pageerror", lambda e: phone_errors.append(str(e)))
    phone.goto(URL)
    phone.wait_for_function("document.querySelectorAll('#findings li').length === 3", timeout=60000)
    phone.wait_for_timeout(2000)
    phone.screenshot(path=OUT / "7_phone_top.png")
    width = phone.evaluate("document.documentElement.scrollWidth")
    check("no horizontal scroll at 390", width <= 390, str(width))
    phone.screenshot(path=OUT / "8_phone_full.png", full_page=True)
    check("no console errors at 390", not phone_errors, "; ".join(phone_errors)[:300])
    browser.close()

print(f"\n{len(FAILS)} failed: {FAILS}")
sys.exit(1 if FAILS else 0)
