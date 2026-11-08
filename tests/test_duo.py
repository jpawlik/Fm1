"""Duo : deux FM-1 dans la même page (FM1-A, FM1-B), leurs dispositions, leurs mémoires, le tempo lié."""


def open_duo(page, w=1180, h=820):
    page.set_viewport_size({"width": w, "height": h})
    page.goto(page.base + "index.html?duo")
    page.wait_for_function("window.__duo && window.__duo.frames.a.contentWindow.__fw && window.__duo.frames.b.contentWindow.__fw")
    return page.frame(name="a"), page.frame(name="b")


def power(fr):
    fr.evaluate("document.getElementById('go').click()")
    fr.wait_for_function("window.__fw.on && !window.__fw.splash", timeout=20000)


def test_layouts(page):
    open_duo(page, 820, 1180)
    assert page.evaluate("document.querySelector('.duo-stage').dataset.layout") == "stack"
    page.set_viewport_size({"width": 1180, "height": 820})
    page.wait_for_function("document.querySelector('.duo-stage').dataset.layout === 'one'")
    page.frame(name="a").click('.duo-tabs [data-k="b"]')
    assert page.evaluate("document.querySelector('iframe[name=b]').classList.contains('shown')")
    assert page.evaluate("window.__duo.frames.b.contentWindow.__midiActive") is True
    assert page.evaluate("window.__duo.frames.a.contentWindow.__midiActive") is False   # le MIDI va au FM-1 affiché
    page.set_viewport_size({"width": 1600, "height": 900})
    page.wait_for_function("document.querySelector('.duo-stage').dataset.layout === 'side'")
    page.click('.duo-view [data-v="one"]')
    assert page.evaluate("document.querySelector('.duo-stage').dataset.layout") == "one"


def test_separate_memories(page):
    a, b = open_duo(page)
    power(a)
    page.frame(name="a").click('.duo-tabs [data-k="b"]')
    power(b)
    b.evaluate("() => { const fw = window.__fw; fw.G.tempo = 150; fw.loadPreset(7); fw.save(); }")
    keys = page.evaluate("Object.keys(localStorage)")
    assert "fm1b.fm1va.global" in keys and "fm1b.fm1va.idx" in keys
    assert page.evaluate("localStorage.getItem('fm1va.idx')") != "7"
    assert a.evaluate("window.__fw.G.tempo") == 120 and b.evaluate("window.__fw.G.tempo") == 150


def test_fm1_b_can_select_cpu_emulated_firmware(page):
    """Duo does not require FM-1+VA or a native engine on either side."""
    _, b = open_duo(page)
    power(b)
    b.wait_for_function("window.__catalogue && window.__catalogue.some(e => e.id === 'gator')")
    disabled = b.evaluate("""() => {
      document.getElementById('fw-picker').click();
      document.getElementById('fw-search').value = 'GATOR';
      document.getElementById('fw-search').dispatchEvent(new Event('input'));
      return document.querySelector("#fw-results .fw-item[data-id='gator']").getAttribute('aria-disabled');
    }""")
    assert disabled != "true"


def test_sheet_opens_upward_frame_stays(page):
    a, _ = open_duo(page, 834, 1112)
    a.click("#fw-picker")
    page.wait_for_timeout(300)
    up = a.evaluate("document.getElementById('fw-sheet').getBoundingClientRect().bottom <= document.getElementById('fw-picker').getBoundingClientRect().top")
    assert up and a.evaluate("scrollY") == 0                            # la liste au-dessus du contrôle, le cadre en place
    a.evaluate("scrollTo(0, 40)")
    page.wait_for_timeout(100)
    a.click("#fw-picker")
    assert a.evaluate("scrollY") == 0


def test_sheet_visible_side_by_side(page):
    a, _ = open_duo(page, 1366, 1024)
    page.wait_for_function("document.querySelector('.duo-stage').dataset.layout === 'side'")
    a.click("#fw-picker")
    a.wait_for_function("document.getElementById('fw-sheet').getBoundingClientRect().bottom <= innerHeight + 1", timeout=3000)   # (sa montée finie)
    top, bottom, h = a.evaluate("() => { const r = document.getElementById('fw-sheet').getBoundingClientRect(); return [r.top, r.bottom, innerHeight]; }")
    assert 0 <= top < bottom <= h + 1 and bottom - top > 200           # la liste dans le cadre, pas hors de vue


