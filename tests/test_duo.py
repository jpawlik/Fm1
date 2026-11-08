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


def test_b_takes_no_emulated_firmware(page):
    a, b = open_duo(page)
    page.frame(name="a").click('.duo-tabs [data-k="b"]')
    power(b)
    b.wait_for_function("window.__catalogue && window.__catalogue.length")
    dis = b.evaluate("""() => { const e = window.__catalogue.find((x) => !x.natif); document.getElementById('fw-picker').click();
      document.getElementById('fw-search').value = e.nom; document.getElementById('fw-search').dispatchEvent(new Event('input'));
      const btn = document.querySelector(`#fw-results .fw-item[data-id='${e.id}']`); const d = btn.getAttribute('aria-disabled'); btn.click(); return d; }""")
    assert dis == "true"
    assert b.evaluate("document.getElementById('status').textContent") == "In Duo, FM1-B supports FM-1+VA or native firmware."
    assert b.evaluate("window.__engine() === window.__fw")


def test_linked_tempo(page):
    """With two FM-1+VA instances, FM1-B is ALWAYS the clock master."""
    a, b = open_duo(page, 1600, 900)
    power(a)
    power(b)
    page.click(".duo-link")
    page.wait_for_timeout(400)
    assert b.evaluate("!!window.__fw.mi.lead") and a.evaluate("!!window.__fw.mi.follow")
    assert not a.evaluate("!!window.__fw.mi.lead")
    assert a.evaluate("window.__fw.globList().rows[0].dim()")    # follower tempo is read-only
    b.evaluate("() => { const fw = window.__fw; fw.G.tempo = 150; fw.sendGlobal(); fw.seqOn(true); fw.sendSeq(); }")
    a.evaluate("""() => { const fw = window.__fw, P = fw.pats[0]; fw.G.tempo = 90; fw.sendGlobal(); P.rate = 7; P.steps = 16;
      P.notes[0] = [{ n: 60, v: 100, len: 1 }]; fw.sendSeq();
      window.__pos = []; const on = fw.onPos.bind(fw); fw.onPos = (m) => { window.__pos.push(m); on(m); }; }""")
    page.wait_for_timeout(500)
    assert a.evaluate("valText(window.__fw.globList().rows[0])") == "150"
    assert page.evaluate("document.querySelector('.duo-link').textContent").endswith("B → A")
    b.evaluate("window.__fw.seqPlay()")                         # B's Start travels to A
    page.wait_for_timeout(1500)
    pos = a.evaluate("window.__pos")
    assert len(pos) >= 8
    at = [p["at"] for p in pos]
    d = sorted(y - x for x, y in zip(at, at[1:]))
    assert 0.085 <= d[len(d) // 2] <= 0.115              # 1/16 at 150 BPM, not A's 90 BPM
    b.evaluate("window.__fw.seqPlay()")                         # B's Stop reaches A
    page.wait_for_timeout(300)
    assert not a.evaluate("window.__fw.S.playing")
    page.click(".duo-link")
    page.wait_for_timeout(400)
    assert not a.evaluate("!!window.__fw.mi.follow")


def test_native_follows(page):
    """FM1-A natif, FM1-B FM-1+VA : B mène, et le natif reçoit l'horloge dans le format de son worklet."""
    a, b = open_duo(page, 1600, 900)
    power(a)
    power(b)
    a.wait_for_function("window.__catalogue && window.__catalogue.some((e) => e.natif)")
    ok = a.evaluate("() => window.__useEngine(window.__catalogue.find((e) => e.natif && e.natif_dialecte === 'felucca'))")
    assert ok
    a.evaluate("() => { const n = window.__engine(), s = n.send.bind(n); window.__got = []; n.send = (m, t) => { if (m.type === 'midi') window.__got.push(m.data[0]); return s(m, t); }; }")
    page.click(".duo-link")
    page.wait_for_timeout(600)
    assert page.evaluate("document.querySelector('.duo-link').textContent").endswith("B → A")
    assert b.evaluate("!!window.__fw.mi.lead")
    got = a.evaluate("window.__got")
    assert got.count(0xF8) >= 10                                        # l'horloge de FM1-B


def test_native_on_b_cannot_claim_clock_master(page):
    """A native firmware on B receives MIDI but does not expose clock output."""
    a, b = open_duo(page, 1600, 900)
    power(a)
    power(b)
    b.wait_for_function("window.__catalogue && window.__catalogue.some((e) => e.natif)")
    assert b.evaluate("() => window.__useEngine(window.__catalogue.find((e) => e.natif && e.natif_dialecte === 'felucca'))")
    page.wait_for_function("document.querySelector('.duo-link').getAttribute('aria-disabled') === 'true'")
    page.click(".duo-link", force=True)
    assert page.is_visible(".fs-tip")
    assert "FM1-B" in page.inner_text(".fs-tip")
    assert page.evaluate("window.__duo.linked") is False
    assert not a.evaluate("!!window.__fw.mi.lead")


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


def test_link_disabled_explains(page):
    open_duo(page, 1600, 900)                                            # rien d'allumé : personne ne donne l'horloge
    page.click(".duo-link", force=True)                                 # aria-disabled : Playwright l'attendrait
    assert page.is_visible(".fs-tip") and "FM1-B" in page.inner_text(".fs-tip") and "FM-1+VA" in page.inner_text(".fs-tip")
    assert page.evaluate("window.__duo.linked") is False                 # le réglage ne change pas


def test_emulated_follows(page):
    """FM1-A émulé, FM1-B FM-1+VA : B mène, l'émulé reçoit son horloge par sa prise MIDI IN."""
    a, b = open_duo(page, 1600, 900)
    power(a)
    power(b)
    a.wait_for_function("window.__catalogue && window.__catalogue.length")
    assert a.evaluate("() => window.__useEngine(window.__catalogue.find((e) => e.id === 'monohull'))")
    a.evaluate("() => { const e = window.__engine(), s = e.send.bind(e); window.__got = []; e.send = (m) => { if (m.type === 'midi') window.__got.push(...m.bytes); return s(m); }; }")
    page.click(".duo-link")
    page.wait_for_timeout(600)
    assert page.evaluate("document.querySelector('.duo-link').textContent").endswith("B → A")
    assert a.evaluate("window.__got").count(0xF8) >= 10
