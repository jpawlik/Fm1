"""Sélecteur de firmwares."""
import os

from conftest import ROOT, lit_pixels, power_on

SHOTS = os.path.join(ROOT, "test-results")


def status(page):
    return page.inner_text("#status")


def wait_status(page, text, timeout=30000):
    page.wait_for_function("(t) => document.getElementById('status').textContent === t", arg=text, timeout=timeout)


def ready(page, nom, timeout=30000):                                    # démarré : son nom dans le sélecteur, la ligne d'état vide
    page.wait_for_function("(n) => document.getElementById('fw-name').textContent === n && document.getElementById('status').textContent === ''", arg=nom, timeout=timeout)


def click_row(page, fid):
    page.evaluate("(id) => document.querySelector(`.fw-item[data-id=\"${id}\"]`).click()", fid)


def notch_transform(page, sel):
    return page.evaluate("(s) => getComputedStyle(document.querySelector(s)).transform", sel)


def test_open_close(page):
    page.goto(page.base + "index.html")
    closed = notch_transform(page, "#fw-picker .notch")
    page.click("#fw-picker")
    assert page.is_visible("#fw-sheet")
    assert page.get_attribute("#fw-picker", "aria-expanded") == "true"
    page.wait_for_timeout(300)
    assert notch_transform(page, "#fw-picker .notch") != closed
    page.keyboard.press("Escape")
    assert not page.is_visible("#fw-sheet")
    assert page.get_attribute("#fw-picker", "aria-expanded") == "false"


def test_search(page):
    page.goto(page.base + "index.html")
    page.click("#fw-picker")
    page.fill("#fw-search", "sloop")
    texts = page.eval_on_selector_all("#fw-results .fw-item", "els => els.map((e) => e.textContent.toLowerCase())")
    # les correspondances directes passent avant celles admises par tolérance aux fautes (« loop »)
    has = ["sloop" in t for t in texts]
    assert texts and has[0] and has == sorted(has, reverse=True)
    page.fill("#fw-search", "bubba")
    assert "bubba machine" not in page.inner_text("#fw-sheet").lower()
    page.fill("#fw-search", "sloop zzzzqq")
    assert page.is_visible("text=Closest matches")
    page.click("#fw-clear")
    assert page.input_value("#fw-search") == ""
    assert page.is_visible(".fw-sec-head")
    page.fill("#fw-search", "chipb")
    page.keyboard.press("Escape")
    assert page.input_value("#fw-search") == ""
    assert page.is_visible("#fw-sheet")


def test_pick(page):
    power_on(page)
    click_row(page, "sloop")
    assert status(page) == "Starting SLOOP…"
    ready(page, "SLOOP")
    assert page.inner_text("#fw-name") == "SLOOP"
    assert not page.is_visible("#fw-sheet")


def test_enter_picks_first(page):
    power_on(page)
    page.click("#fw-picker")
    page.fill("#fw-search", "chipbox")
    page.keyboard.press("Enter")
    assert not page.is_visible("#fw-sheet")
    ready(page, "Chipbox")


def test_last_wins(page):
    power_on(page)
    page.evaluate("""() => { document.querySelector('.fw-item[data-id="x0x"]').click();
      setTimeout(() => document.querySelector('.fw-item[data-id="monohull"]').click(), 30); }""")
    ready(page, "Monohull", timeout=60000)
    page.wait_for_timeout(500)
    assert page.evaluate("window.__engine().name") == "Monohull"
    assert page.evaluate("window.__nodes().length") == 1


def test_restore_last(page):
    power_on(page)
    click_row(page, "monohull")
    ready(page, "Monohull")
    page.reload()
    assert page.inner_text("#fw-name") == "Monohull"
    page.click("#go")
    page.wait_for_function("window.__engine && window.__engine().name === 'Monohull'", timeout=30000)
    assert page.evaluate("window.__engine().name") == "Monohull"


def test_sections_fold(page):
    page.goto(page.base + "index.html")
    page.click("#fw-picker")
    head = '.fw-sec[data-tier="emule"][data-cat="Synthé"] .fw-sec-head'
    before = page.get_attribute(head, "aria-expanded")
    notch = notch_transform(page, head + " .notch")
    page.click(head)
    page.wait_for_timeout(300)
    assert page.get_attribute(head, "aria-expanded") != before
    assert notch_transform(page, head + " .notch") != notch
    expanded = page.get_attribute(head, "aria-expanded") == "true"
    assert page.is_visible('.fw-sec[data-tier="emule"][data-cat="Synthé"] .fw-items') == expanded


def test_optimised_first(page):
    """Les firmwares optimisés (natifs) d'abord, les non optimisés (émulés) à la fin."""
    page.goto(page.base + "index.html")
    page.click("#fw-picker")
    page.wait_for_selector('.fw-item[data-id="x0x"]', state="attached")
    order = page.evaluate("""() => [...document.querySelectorAll('#fw-sections > .fw-tier, #fw-sections > .fw-sec')]
      .map((n) => n.classList.contains('fw-tier') ? 'T:' + n.textContent : n.dataset.tier)""")
    assert order[0] == "T:Optimized"
    k = order.index("T:Emulated")
    assert set(order[1:k]) == {"optimise"} and set(order[k + 1:]) == {"emule"}
    tier = lambda i: page.evaluate("(id) => document.querySelector(`.fw-item[data-id=\"${id}\"]`).closest('.fw-sec').dataset.tier", i)
    assert tier("fm1va") == "optimise" and tier("x0x") == "optimise" and tier("felucca") == "optimise"
    assert tier("sloop") == "emule" and tier("monohull") == "emule" and tier("obervave") == "optimise"


def test_layouts(browser, base_url):
    os.makedirs(SHOTS, exist_ok=True)
    for w, h in [(390, 844), (820, 1180), (1440, 900)]:
        ctx = browser.new_context(viewport={"width": w, "height": h}, has_touch=w < 1000)
        pg = ctx.new_page()
        pg.goto(base_url + "index.html")
        pg.click("#fw-picker")
        pg.wait_for_timeout(400)
        sheet = pg.eval_on_selector("#fw-sheet", "e => e.getBoundingClientRect().toJSON()")
        picker = pg.eval_on_selector("#fw-picker", "e => e.getBoundingClientRect().toJSON()")
        # la liste tient dans la fenêtre : son pied « Ouvrir un .fwsc… » reste visible sans faire défiler la page
        assert sheet["bottom"] <= h + 1, (w, sheet)
        if w < 700:
            assert abs(sheet["bottom"] - h) <= 1, sheet
        else:
            assert sheet["top"] >= picker["bottom"] - 1 or sheet["bottom"] <= picker["top"] + 1, (sheet, picker)   # dessous, ou dessus quand la place manque
            assert sheet["top"] >= 0 and pg.evaluate("scrollY") == 0
        assert sheet["left"] >= 0 and sheet["right"] <= w
        pg.screenshot(path=os.path.join(SHOTS, f"selecteur-{w}.png"))
        ctx.close()


def test_contextual_controls(page):
    power_on(page)
    assert page.is_visible(".file")
    click_row(page, "sloop")
    ready(page, "SLOOP")
    assert not page.is_visible(".file")
    click_row(page, "fm1va")
    ready(page, "FM-1+VA")
    assert page.is_visible(".file")


def test_open_local(page):
    power_on(page)
    n = page.evaluate("window.__catalogue.length")
    page.set_input_files("#fw-file", os.path.join(ROOT, "firmwares", "gator.fwsc"))
    ready(page, "gator")
    assert page.inner_text("#fw-name") == "gator"
    page.wait_for_timeout(3000)
    assert lit_pixels(page) >= 2000
    assert page.evaluate("window.__catalogue.length") == n


def test_tag_no_boot(page):
    import json
    cat = json.load(open(os.path.join(ROOT, "firmwares", "catalogue.json")))
    for e in cat["firmwares"]:
        if e["id"] == "x0x":
            e["emulateur_fm1emu"] = "ne démarre pas"
    page.route("**/firmwares/catalogue.json", lambda r: r.fulfill(status=200, body=json.dumps(cat), content_type="application/json"))
    page.goto(page.base + "index.html")
    page.wait_for_selector('.fw-item[data-id="x0x"]', state="attached")
    assert "does not boot" in page.eval_on_selector('.fw-item[data-id="x0x"]', "e => e.textContent")


def test_no_dead_zone_between_keys(page):
    """Entre deux touches ou deux boutons voisins, un appui tombe sur l'une ou l'autre, jamais dans le vide."""
    from conftest import power_on
    power_on(page)
    gaps = page.evaluate("""() => {
      const mid = (a, b) => { const r = a.getBoundingClientRect(), s = b.getBoundingClientRect();
        return [(r.right + s.left) / 2, (Math.max(r.top, s.top) + Math.min(r.bottom, s.bottom)) / 2]; };
      const hitAt = ([x, y]) => { const e = document.elementFromPoint(x, y); return !!e && e.classList.contains('hit'); };
      const keys = [...document.querySelectorAll('.key')], caps = [...document.querySelectorAll('.cap')];
      const out = [];
      for (let i = 0; i + 1 < keys.length; i++) {
        keys[i].scrollIntoView({ block: 'center' });
        const r = keys[i].getBoundingClientRect(), s = keys[i + 1].getBoundingClientRect();
        if (s.left > r.right && s.top < r.bottom && s.bottom > r.top) out.push(['key', i, hitAt(mid(keys[i], keys[i + 1]))]);
      }
      caps[0].scrollIntoView({ block: 'center' });
      caps.forEach((c, i) => {                       // chaque bouton et son voisin de droite sur la même rangée
        const r = c.getBoundingClientRect();
        const right = caps.filter((d) => { const s = d.getBoundingClientRect(); return s.left > r.right && s.left - r.right < r.width && s.top < r.bottom && s.bottom > r.top; })
          .sort((a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left)[0];
        if (right) out.push(['cap', i, hitAt(mid(c, right))]);
      });
      return out; }""")
    assert len([g for g in gaps if g[0] == "key"]) >= 10 and len([g for g in gaps if g[0] == "cap"]) >= 8, [g for g in gaps if g[0] == "cap"]
    assert all(g[2] for g in gaps), [g for g in gaps if not g[2]]


def test_sheet_keeps_page_still(page):
    page.set_viewport_size({"width": 834, "height": 1112})
    page.goto(page.base + "index.html")
    page.click("#fw-picker")
    page.wait_for_timeout(300)
    assert page.evaluate("scrollY") == 0
    assert page.evaluate("document.getElementById('fw-sheet').getBoundingClientRect().bottom <= document.getElementById('fw-picker').getBoundingClientRect().top")
