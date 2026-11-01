"""Browser checks of the atlas: every control must change what the page shows, with no console errors.

Needs Playwright, which is not a project dependency, with its chromium, and a URL where the page is served with its data:
    python scripts/probar_web.py http://127.0.0.1:8596/
"""
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8596/"
OUT = Path(tempfile.gettempdir()) / "huella_web_shots"
OUT.mkdir(exist_ok=True)
FAILS = []


ALL_ERRORS = []


def watch_errors(page):
    page.on("console", lambda m: ALL_ERRORS.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: ALL_ERRORS.append(str(e)))
    return page


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILS.append(name)


def text(page, selector):
    return page.locator(selector).inner_text().replace("\n", " ")


def set_range(page, value):
    page.evaluate("v => { const e = document.getElementById('year'); e.value = v; e.dispatchEvent(new Event('input', {bubbles:true})); }", value)
    page.wait_for_timeout(250)


# Records, on every frame of the autoplay, whether anything but the map dims and whether the year labels disagree
WATCH = """
window.__watch = {dimmed: {}, disagree: 0, frames: 0};
const opacity = (el) => { let o = 1; for (let e = el; e; e = e.parentElement) o *= parseFloat(getComputedStyle(e).opacity); return o; };
const tick = () => {
  const w = window.__watch, year = document.getElementById('year'), big = document.getElementById('big-year'), out = document.getElementById('year-output');
  if (year && big && out) {
    w.frames++;
    if (year.value !== big.textContent || year.value !== out.textContent) w.disagree++;
    for (const sel of ['h1', '.question', '.lead', '.kpis', '.controls', '#year', '#big-year', '#legend', '#trend', '#rank']) {
      const el = document.querySelector(sel);
      if (el && opacity(el) < 0.99) w.dimmed[sel] = (w.dimmed[sel] || 0) + 1;
    }
  }
  requestAnimationFrame(tick);
};
requestAnimationFrame(tick);
"""


def farthest_view_is_the_start(page, label):
    """Zooms in, drags, zooms out as far as it goes and drags again: the map must end where it started."""
    page.locator("#map").scroll_into_view_if_needed()
    page.wait_for_timeout(1500)
    box = page.locator("#map").bounding_box()
    middle = (box["x"] + box["width"] / 2, box["y"] + min(box["height"], page.viewport_size["height"] - box["y"]) / 2)
    corner = (box["x"] + box["width"] - 6, box["y"] + 6)  # no district there, so it clears the highlight of the last one

    def rest():
        page.mouse.move(*corner)
        page.wait_for_timeout(300)
        page.mouse.move(corner[0] - 2, corner[1] + 2)
        page.wait_for_timeout(1800)

    def matches_start():
        # The highlight of the last district under the pointer can take a moment to clear; a map out of place never matches
        for _ in range(10):
            if page.locator("#map").screenshot() == start_view:
                return True
            rest()
        return False

    def centered():
        return page.evaluate("Math.abs(viewState.longitude - home.longitude) + Math.abs(viewState.latitude - home.latitude) + Math.abs(viewState.zoom - home.zoom)") < 1e-9

    def drag(dx, dy):
        page.mouse.move(*middle)
        page.mouse.down()
        page.mouse.move(middle[0] + dx, middle[1] + dy, steps=8)
        page.mouse.up()

    rest()
    start_view = page.locator("#map").screenshot()
    page.mouse.move(box["x"] + 40, middle[1] - 60)
    for _ in range(6):
        page.mouse.wheel(0, -240)
        page.wait_for_timeout(120)
    drag(100, -120)
    page.wait_for_timeout(800)
    check(f"{label}: wheel and drag move the map", page.locator("#map").screenshot() != start_view)
    for _ in range(40):  # as far as it goes: a slow machine takes more turns of the wheel
        page.mouse.move(box["x"] + 30, middle[1] + 90)
        page.mouse.wheel(0, 480)
        page.wait_for_timeout(80)
        if centered():
            break
    drag(-120, 140)
    rest()
    check(f"{label}: the farthest view with the wheel is the start", centered() and matches_start())
    page.click("#zoom-in")
    page.wait_for_timeout(500)
    drag(90, 90)
    for _ in range(5):
        page.click("#zoom-out")
        page.wait_for_timeout(350)
    rest()
    check(f"{label}: the farthest view with the button is the start", centered() and matches_start())


with sync_playwright() as p:
    browser = p.chromium.launch(args=["--use-angle=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"])
    context = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    page = watch_errors(context.new_page())
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
    page.wait_for_function("document.getElementById('play').textContent === 'Reproducir'", timeout=30000)
    check("play advances the year", page.input_value("#year") == "2025", page.input_value("#year"))
    check("play stops and offers replay", text(page, "#play") == "Reproducir", text(page, "#play"))

    # The figures must never outlive their selection, or claim more than the sum allows
    page.select_option("#indicator", "nueva")
    set_range(page, 2013)
    check("an empty ranking still updates the table", "2013" in page.locator("#table th").nth(2).text_content(), page.locator("#table th").nth(2).text_content())
    page.select_option("#indicator", "huella")
    page.select_option("#department", "CAJAMARCA")
    set_range(page, 2021)
    check("the top ten never claims all of a net increase with losses", "perdieron" in text(page, "#kpi-top"), text(page, "#kpi-top"))
    page.select_option("#department", "")
    set_range(page, 2025)
    page.wait_for_timeout(700)

    # The legend's numbers sit on the boundaries between its colors
    page.select_option("#indicator", "nueva")
    page.wait_for_timeout(300)
    tick = page.locator("#legend .legend-ticks span", has_text="20").first.get_attribute("style") or ""
    check("the legend puts 20 km2 on its fifth boundary", tick.startswith("left:71.4"), tick)
    page.select_option("#indicator", "huella")

    # Asking for the same place again recenters the map, and a row keeps the keyboard's place
    page.evaluate("selectDepartment('MADRE DE DIOS')")
    page.wait_for_timeout(900)
    wanted = page.evaluate("[viewState.longitude, viewState.latitude, viewState.zoom]")
    box = page.locator("#map").bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + 400)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] / 2 + 150, box["y"] + 490, steps=8)
    page.mouse.up()
    page.wait_for_timeout(500)
    page.evaluate("selectDepartment('MADRE DE DIOS')")
    page.wait_for_timeout(900)
    again = page.evaluate("[viewState.longitude, viewState.latitude, viewState.zoom]")
    check("the same department recenters the map again", max(abs(a - b) for a, b in zip(again, wanted)) < 1e-6, str(again))
    page.evaluate("selectDepartment('')")
    page.wait_for_timeout(900)
    page.locator("#departments .bar").nth(2).focus()
    page.keyboard.press("Enter")
    page.wait_for_timeout(1000)
    check("a row chosen with the keyboard keeps the focus", page.evaluate("document.activeElement.classList.contains('bar')"), page.evaluate("document.activeElement.tagName"))
    page.select_option("#department", "")
    page.wait_for_timeout(1000)

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

    # The data link replaces a download, which an Artifact's frame blocks
    link = page.locator(".data-link a").get_attribute("href")
    check("the data link points to the repository's CSV", link.endswith("datos/procesados/panel_distrito_anio.csv"), link)

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
    page.evaluate("window.scrollTo(0, 0)")
    farthest_view_is_the_start(page, "1440")
    narrow = watch_errors(browser.new_context(viewport={"width": 1024, "height": 800}, reduced_motion="reduce").new_page())
    narrow.goto(URL)
    narrow.wait_for_function("document.querySelectorAll('#findings li').length === 3", timeout=60000)
    farthest_view_is_the_start(narrow, "1024")

    # First visit: the map plays once by itself
    moving = browser.new_context(viewport={"width": 1440, "height": 900})
    first = watch_errors(moving.new_page())
    first.add_init_script(WATCH)
    first.goto(URL)
    first.wait_for_function("document.querySelectorAll('#findings li').length === 3", timeout=60000)
    start = int(first.input_value("#year"))
    first.wait_for_function("document.getElementById('year').value === '2025' && document.getElementById('play').textContent === 'Reproducir'", timeout=30000)
    check("autoplay runs from the first years to 2025", start < 2020, str(start))
    watch = first.evaluate("window.__watch")
    check("during autoplay only the map changes its light", watch["frames"] > 20 and not watch["dimmed"], f'{watch["frames"]} frames, {watch["dimmed"]}')
    check("during autoplay the year labels never disagree", watch["disagree"] == 0, str(watch["disagree"]))
    first.select_option("#department", "MADRE DE DIOS")
    first.wait_for_timeout(300)
    check("a department with few districts does not claim a top ten", "100 %" not in text(first, "#kpi-top"), text(first, "#kpi-top"))

    # A click on a row during the animation stops it and is never lost
    playing = watch_errors(browser.new_context(viewport={"width": 1440, "height": 900}).new_page())
    playing.goto(URL)
    playing.wait_for_function("document.querySelectorAll('#rank .bar').length > 0 && state.playing", timeout=60000)
    playing.evaluate("document.getElementById('rank').scrollIntoView({block: 'center'})")
    row = playing.evaluate("(() => { const r = document.querySelector('#rank .bar').getBoundingClientRect(); return {x: r.x, y: r.y, height: r.height}; })()")
    playing.mouse.move(row["x"] + 30, row["y"] + row["height"] / 2)
    playing.mouse.down()
    playing.wait_for_timeout(800)  # longer than a year of the animation, so the row would have been rebuilt
    playing.mouse.up()
    playing.wait_for_timeout(300)
    check("a slow click on a row selects it and stops the animation", playing.evaluate("state.district !== null && !state.playing"), playing.evaluate("String(state.district)"))

    # Mobile
    mobile = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, reduced_motion="reduce", has_touch=True)
    phone = watch_errors(mobile.new_page())
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
    phone.locator("#map").scroll_into_view_if_needed()
    farthest_view_is_the_start(phone, "390")
    phone.locator("#map").screenshot(path=OUT / "9_phone_map.png")

    touch = browser.new_context(viewport={"width": 390, "height": 844}, reduced_motion="reduce", has_touch=True, is_mobile=True)
    swiped = watch_errors(touch.new_page())
    swiped.goto(URL)
    swiped.wait_for_function("document.querySelectorAll('#findings li').length === 3", timeout=60000)
    swiped.wait_for_timeout(2000)
    swiped.evaluate("document.querySelector('#map').scrollIntoView({block: 'center'})")
    swiped.wait_for_timeout(500)
    cdp = touch.new_cdp_session(swiped)
    box = swiped.locator("#map").bounding_box()
    y = box["y"] + box["height"] * 0.7
    before, view = swiped.evaluate("scrollY"), swiped.evaluate("viewState.latitude")
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": 195, "y": y}]})
    for step in range(1, 11):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": 195, "y": y - 25 * step}]})
        swiped.wait_for_timeout(30)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    swiped.wait_for_timeout(700)
    check("390: a swipe on the map moves the page and not the map", swiped.evaluate("scrollY") > before + 100 and swiped.evaluate("viewState.latitude") == view, f'{before} to {swiped.evaluate("scrollY")}')
    check("no console errors on any page", not ALL_ERRORS, "; ".join(ALL_ERRORS)[:300])
    browser.close()

print(f"\n{len(FAILS)} failed: {FAILS}")
sys.exit(1 if FAILS else 0)
