"""Régressions relevées par la relecture finale."""
from conftest import lit_pixels, power_on
from test_emu import use


def rms(page):
    """Niveau de sortie de FM-1+VA (son analyseur)."""
    return page.evaluate("""() => { const an = window.__fw.analyser, d = new Float32Array(an.fftSize);
      an.getFloatTimeDomainData(d); let s = 0; for (const x of d) s += x * x; return Math.sqrt(s / d.length); }""")


def frames_accepted(page):
    """Une image de la machine qui tourne encore est prise en compte (ici, son arrêt est détecté)."""
    return page.evaluate("""() => { const e = window.__engine(); e.onHalt = null;
      e.onWorklet({ data: { type: 'frame', seq: e.running.seq, halted: 1 } }); return e.halted === 1; }""")


def test_failed_emu_switch_keeps_screen(page):
    """Failed online package fetch keeps the prior emulated firmware running."""
    page.route("**/natif/manifest.json", lambda r: r.fulfill(status=200, body="{}", content_type="application/json"))
    page.route("https://thefirmwarehub.com/**", lambda r: r.fulfill(status=503, body="indisponible"))
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "fizz") is True
    page.wait_for_timeout(2000)
    assert use(page, "skiff") is False
    page.wait_for_timeout(1500)
    assert lit_pixels(page) >= 2000
    assert frames_accepted(page)


def test_failed_emu_boot_keeps_screen(page):
    """Felucca puis un paquet invalide : même chose après un échec de démarrage."""
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "fizz") is True
    page.wait_for_timeout(2000)
    ok = page.evaluate("""async () => window.__useEngine({ id: 'local', nom: 'x', bytes: new Uint8Array(1000) })""")
    assert ok is False
    page.wait_for_timeout(1500)
    assert lit_pixels(page) >= 2000
    assert frames_accepted(page)


def test_key_during_switch_not_stuck(page):
    """Une touche jouée pendant le passage de FM-1+VA à un firmware émulé ne reste pas tenue."""
    power_on(page)
    page.set_default_timeout(30000)
    page.evaluate("""() => { window.__p = window.__useEngine(window.__catalogue.find((e) => e.id === 'sloop'));
      setTimeout(() => window.__host.keyDown(16, 'late'), 20); }""")
    assert page.evaluate("window.__p") is True
    page.evaluate("window.__host.keyUp('late')")
    assert use(page, "fm1va") is True
    page.wait_for_timeout(800)
    assert page.evaluate("window.__fw.keyNotes.size") == 0
    assert rms(page) < 0.001


def test_boot_exception_falls_back_to_va(page):
    """Une exception pendant le démarrage laisse FM-1+VA branché et audible."""
    power_on(page)
    page.set_default_timeout(30000)
    page.evaluate("() => { crypto.subtle.digest = () => { throw new Error('refusé'); }; }")
    ok = page.evaluate("""async () => { try { return await window.__useEngine(window.__catalogue.find((e) => e.id === 'fizz')); }
      catch (err) { return 'rejet'; } }""")
    assert ok is False
    assert page.evaluate("window.__engine() === window.__fw")
    page.evaluate("window.__host.keyDown(16, 't')")
    page.wait_for_timeout(600)
    level = rms(page)
    page.evaluate("window.__host.keyUp('t')")
    assert level > 0.001, level
