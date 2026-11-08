"""Lumières des boutons : seule la légende s'éclaire ; PLAY vert en lecture, rouge à l'arrêt séquenceur actif, éteint sinon."""
from conftest import power_on
from test_emu import use

CAP = "document.querySelector(`.cap[data-label=\"${l}\"]`)"


def state(page, label):
    return page.evaluate(f"""(l) => {{ const c = {CAP};
      return {{ lit: c.classList.contains('lit'), green: c.classList.contains('lit-green'), red: c.classList.contains('lit-red') }}; }}""", label)


def test_only_legend_lights(page):
    power_on(page)
    page.evaluate("() => { window.__fw.cur.env.on = 1; }")
    page.wait_for_timeout(300)
    s = page.evaluate(f"""(l) => {{ const c = {CAP}, t = c.querySelector('.legend');
      return [c.classList.contains('lit'), c.querySelectorAll('.halo, .glow').length, 0, getComputedStyle(t).fill]; }}""", "ENV")
    assert s[0] is True
    assert s[1] == 0, s                                   # plus de lueur sur le capuchon
    assert s[3] not in ("rgb(36, 48, 45)",), s           # la légende n'a plus la couleur de l'encre éteinte


def test_va_play_colours(page):
    power_on(page)
    page.evaluate("() => { window.__fw.G.seqOn = 1; }")       # séquenceur allumé, jamais lancé : éteint, comme REC
    page.wait_for_timeout(200)
    assert state(page, "PLAY") == {"lit": False, "green": False, "red": False}
    assert page.evaluate("window.__fw.buttonLit('REC')") is False
    page.evaluate("() => { window.__fw.seqPlay(); }")
    page.wait_for_timeout(200)
    assert state(page, "PLAY") == {"lit": False, "green": True, "red": False}
    page.evaluate("() => { window.__fw.seqPlay(); }")         # arrêt : rouge
    page.wait_for_timeout(200)
    assert state(page, "PLAY") == {"lit": False, "green": False, "red": True}
    page.evaluate("() => { window.__fw.seqOn(false); }")      # séquenceur éteint : plus rien
    page.wait_for_timeout(200)
    assert state(page, "PLAY") == {"lit": False, "green": False, "red": False}


def test_launch_state(page):
    """Au lancement : PLAY et REC éteints, « Jouer » replié."""
    page.goto(page.base + "index.html")
    assert page.evaluate("[window.__fw.playLight(), window.__fw.buttonLit('REC'), document.querySelectorAll('details[open]').length]") == [None, False, 0]


def test_emulated_play_colours(page):
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "fizz") is True                                # (un émulé : zp12 et gator sont natifs maintenant)
    r = page.evaluate("""() => { const e = window.__engine(); e.onHalt = null; const seq = e.running.seq;
      const leds = new Float32Array(41), out = [];
      e.onWorklet({ data: { type: 'frame', seq, leds: leds.slice(), green: 0.9 } }); out.push(e.playLight());
      leds[12] = 0.9; e.onWorklet({ data: { type: 'frame', seq, leds: leds.slice(), green: 0 } }); out.push(e.playLight());
      e.onWorklet({ data: { type: 'frame', seq, leds: new Float32Array(41), green: 0 } }); out.push(e.playLight());
      return out; }""")
    assert r == ["green", "red", None]


def test_native_play_colours(page):
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "felucca") is True
    r = page.evaluate("""() => { const e = window.__engine(), out = [];
      for (const b of [1 << 14, 1 << 10, 0]) { e.onWorklet({ data: { type: 'frame', leds: [b, 0, 0, 0, 0, 0, 0, 0] } }); out.push(e.playLight()); }
      return out; }""")
    assert r == ["green", "red", None]
    assert use(page, "x0x") is True
    r = page.evaluate("""() => { const e = window.__engine(), out = [];
      for (const b of [1 << 10, 0]) { e.onWorklet({ data: { type: 'frame', buttons: b, keys: 0 } }); out.push(e.playLight()); }
      return out; }""")
    assert r == ["green", None]


def test_seq_dark_before_power_on(page):
    """Avant l'allumage, SEQ ne clignote pas, même séquenceur allumé dans les réglages sauvegardés."""
    page.goto(page.base + "index.html")
    page.evaluate("() => { window.__fw.G.seqOn = 1; }")
    seen = page.evaluate("""() => new Promise((done) => { let lit = 0; const t = setInterval(() => { if (window.__fw.buttonLit('SEQ')) lit++; }, 25);
      setTimeout(() => { clearInterval(t); done(lit); }, 2500); })""")
    assert seen == 0, seen
    assert page.evaluate("document.querySelector('.cap[data-label=\"SEQ\"]').classList.contains('lit')") is False


def test_emulated_levels(page):
    """fm1-emu mesure la part du temps où une LED brille : allumée, une colonne sur 11 de la matrice. Ramenée à 0..1 :
    1/11 est allumée ; un tiers de cela, une lueur que le panneau dessine à son niveau."""
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "fizz") is True
    r = page.evaluate("""() => { const e = window.__engine(); e.onHalt = null; const seq = e.running.seq, leds = new Float32Array(41);
      leds[8] = 1 / 11; e.onWorklet({ data: { type: 'frame', seq, leds: leds.slice(), green: 0 } });
      const full = [e.buttonLit('HOME'), e.ledLevels()];
      leds[14] = 1 / 33; e.onWorklet({ data: { type: 'frame', seq, leds: leds.slice(), green: 0 } });
      const lv = e.ledLevels(); return [full, lv && [lv[6], lv[14]]]; }""")
    assert r[0] == [True, None]                                          # tout allumé ou éteint : le dessin habituel
    assert r[1][0] == 1 and abs(r[1][1] - (1 / 3) ** 0.5) < 0.01        # une lueur : son niveau


def test_felucca_layers(page):
    """Natif Felucca : la lueur de repos, ce qui respire et le niveau moyen des temps DRUM se voient sous l'allumé."""
    from test_natif import _natif
    _natif("felucca")
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "felucca") is True
    page.wait_for_timeout(2500)
    page.evaluate("""() => { const e = window.__engine(); e.anim = null; e.onWorklet = ((f) => (ev) => { if (!ev.data.mine) return; f.call(e, ev); })(e.onWorklet);
      e.onWorklet({ data: { mine: 1, type: 'frame', leds: [1 << 0, 1 << 0, 1 << 1, 0b110, 0, 1 << 2, 1 << 3, 1 << 4, 0] } }); }""")
    page.wait_for_timeout(300)
    keys = page.evaluate("() => [0, 1, 2, 3, 4].map((i) => document.querySelector(`#device .key[data-key='${i}']`)).map((k) => [k.className.baseVal || k.className, +getComputedStyle(k.querySelector('.lamp')).opacity])")
    caps = page.evaluate("() => ['FX', 'SEL', 'ENV'].map((l) => document.querySelector(`#device .cap[data-label='${l}']`)?.getAttribute('class'))")
    assert "lit" in keys[0][0] and keys[0][1] == 1                       # l'allumé passe devant la lueur
    assert "dim" in keys[1][0] and abs(keys[1][1] - 0.3) < 0.01          # la lueur
    assert "breath" in keys[3][0] and "mid" in keys[4][0] and abs(keys[4][1] - 0.45) < 0.01
    assert page.evaluate("getComputedStyle(document.querySelector(`#device .key[data-key='3'] .lamp`)).animationName") == "breath-lamp"
