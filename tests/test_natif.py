"""Felucca compilé depuis ses sources (natif) derrière le panneau, à la place de l'émulation."""
from conftest import lit_pixels, power_on
from test_emu import rms, use


def test_felucca_runs_native(page):
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "felucca") is True
    assert page.evaluate("window.__engine().kind") == "natif"
    page.wait_for_timeout(2500)
    assert lit_pixels(page) >= 2000
    page.evaluate("window.__host.keyDown(12, 't')")
    page.wait_for_timeout(500)
    level = rms(page)
    lit = page.evaluate("window.__host.keyLit(12)")
    page.evaluate("window.__host.keyUp('t')")
    assert level > 0.001, level
    assert lit is True


def test_native_light_cost(page):
    """Le firmware natif prend une petite part du temps audio (Felucca mesure lui-même sa charge)."""
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "felucca") is True
    page.evaluate("window.__host.keyDown(12, 't'); window.__host.keyDown(16, 'u')")
    page.wait_for_function("window.__engine().load !== null", timeout=8000)
    load = page.evaluate("window.__engine().load")
    page.evaluate("window.__host.keyUp('t'); window.__host.keyUp('u')")
    assert load < 0.25, load


def test_native_then_emulated_then_back(page):
    """Felucca natif, puis un firmware émulé, puis FM-1+VA : chaque passage marche, aucune note tenue."""
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "felucca") is True
    page.evaluate("window.__host.keyDown(12, 't')")
    assert use(page, "sloop") is True                                   # (un émulé : zp12 est natif)
    assert page.evaluate("window.__engine().kind") != "natif"
    page.wait_for_timeout(2000)
    assert lit_pixels(page) >= 2000
    assert use(page, "felucca") is True
    page.wait_for_timeout(800)
    assert rms(page) < 0.001
    assert use(page, "fm1va") is True
    assert page.evaluate("window.__engine() === window.__fw")


def test_native_saves_kept(page):
    """Ce que Felucca écrit dans sa flash revient à la prochaine ouverture de la page."""
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "felucca") is True
    page.evaluate("""() => window.__engine().onWorklet({ data: { type: 'frame', sectors: { 0x97000: new Uint8Array(4096).fill(7) } } })""")
    page.wait_for_function("window.__engine().pendingSave === null", timeout=5000)
    power_on(page)
    assert use(page, "felucca") is True
    assert page.evaluate("window.__engine().lastLoadSectors && window.__engine().lastLoadSectors[0x97000][0]") == 7


def test_native_screen_60fps(page):
    """L'écran natif n'est plus plafonné à 30 images par seconde : il suit le rythme de dessin du firmware."""
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "felucca") is True
    page.wait_for_timeout(1500)
    rate = page.evaluate("""() => new Promise((done) => {
      const e = window.__engine(), o = e.onWorklet.bind(e); let n = 0;
      e.onWorklet = (ev) => { if (ev.data.fb) n++; o(ev); };
      const t = setInterval(() => window.__host.turn('KNOB1', 1), 8);
      setTimeout(() => { clearInterval(t); e.onWorklet = o; done(n / 2); }, 2000); })""")
    assert rate > 33, rate


def test_native_colours(page):
    """L'écran natif est dans l'ordre d'octets de la dalle : un pixel 0x00F8 (rouge pur côté dalle) s'affiche rouge."""
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "felucca") is True
    px = page.evaluate("""() => { const e = window.__engine(); e.onWorklet = () => {};
      e.fb = new Uint16Array(240 * 240).fill(0x00F8); e.fbNew = true; e.draw();
      const c = document.getElementById('screen'); return Array.from(c.getContext('2d').getImageData(c.width >> 1, c.height >> 1, 1, 1).data); }""")
    assert px[0] > 200 and px[1] < 40 and px[2] < 40, px


def test_x0x_runs_native(page):
    """X0X, de l'autre famille de protocole (store, master sur 4096), tourne aussi en natif."""
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "x0x") is True
    assert page.evaluate("window.__engine().kind") == "natif"
    page.wait_for_timeout(2500)
    assert lit_pixels(page) >= 2000
    # X0X est une boîte à rythmes : une touche allume un pas, PLAY lance le motif
    for k in (0, 4, 8, 12):
        page.evaluate(f"window.__host.keyDown({k}, 't')"); page.wait_for_timeout(120); page.evaluate("window.__host.keyUp('t')")
    page.wait_for_timeout(300)
    assert page.evaluate("window.__host.keyLit(12)") is True, page.evaluate("window.__engine().leds")
    page.evaluate("window.__host.press('PLAY')"); page.wait_for_timeout(150); page.evaluate("window.__host.release('PLAY')")
    level = 0
    for _ in range(10):
        page.wait_for_timeout(150); level = max(level, rms(page))
    assert level > 0.001, level
    page.wait_for_function("window.__engine().load !== null", timeout=8000)
    assert page.evaluate("window.__engine().load") < 0.25


def test_x0x_store_kept(page):
    """Ce que X0X enregistre (store) revient à la prochaine ouverture."""
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "x0x") is True
    page.evaluate("""() => window.__engine().onWorklet({ data: { type: 'frame', buttons: 0, keys: 0, store: { 3: new Uint8Array(16).fill(9) } } })""")
    page.wait_for_function("window.__engine().pendingSave === null", timeout=5000)
    power_on(page)
    assert use(page, "x0x") is True
    assert page.evaluate("window.__engine().lastLoadSectors[3][0]") == 9



def test_granular_natives_make_sound(page):
    """ECHOFIELD and GRAINE must make actual audio, not merely display a boot splash."""
    power_on(page)
    page.set_default_timeout(30000)
    for fid in ("echofield", "graine"):
        assert use(page, fid) is True
        assert page.evaluate("window.__engine().kind") == "natif"
        page.wait_for_timeout(2000)
        assert lit_pixels(page) > 500, fid
        page.evaluate("window.__host.keyDown(12, 'granular')")
        page.wait_for_timeout(900)
        level = rms(page)
        page.evaluate("window.__host.keyUp('granular')")
        assert level > 0.0002, (fid, level)


def test_base_native_capture_area_restored(page):
    """The optional fm1-base data part is stored independently of preset objects."""
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "graine") is True
    page.evaluate("""() => window.__engine().onWorklet({
        data: { type: 'app', part: 'data', data: Uint8Array.of(17, 34, 51).buffer }
    })""")
    page.wait_for_function("window.__engine().pendingSave === null", timeout=5000)
    power_on(page)
    assert use(page, "graine") is True
    assert page.evaluate("new Uint8Array(window.__engine().extraData)[0]") == 17


def test_every_native_boots(page):
    """Chaque firmware de natif/manifest.json démarre et dessine son écran."""
    import json, os
    from conftest import ROOT
    ids = sorted(json.load(open(os.path.join(ROOT, "natif/manifest.json"))))
    power_on(page)
    page.set_default_timeout(30000)
    bad = []
    for i in ids:
        if use(page, i) is not True or page.evaluate("window.__engine().kind") != "natif":
            bad.append((i, "démarrage")); continue
        for _ in range(10):                         # jusqu'à 5 s : un écran de démarrage sombre (386DX) s'allume plus tard
            page.wait_for_timeout(500)
            if lit_pixels(page) >= 500: break
        else:
            diag = page.evaluate("""() => { const e = window.__engine();
              return { node: !!e.node, on: e.on, failure: e.failure, fb: e.fb?.length || 0,
                context: e.ac?.state, load: e.load, error: String(e.bootError || "") }; }""")
            bad.append((i, "écran", diag))
    assert not bad, bad


def test_every_native_reacts(page):
    """Chaque firmware natif répond au panneau : la molette SELECT ou une touche change l'écran ou le son."""
    import json, os
    from conftest import ROOT
    # (FMDj sans ROM n'a rien à jouer : son écran le dit, test_fmdj_rom le vérifie ; aucune ROM n'est fournie ici)
    ids = sorted(i for i in json.load(open(os.path.join(ROOT, "natif/manifest.json"))) if i != "fmdj")
    shot = "() => { const c = document.getElementById('screen'), d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let h = 0; for (let i = 0; i < d.length; i += 16) h = (h * 31 + d[i] + d[i + 1] + d[i + 2]) | 0; return h; }"
    power_on(page)
    page.set_default_timeout(30000)
    mute = []
    for i in ids:
        if use(page, i) is not True:
            mute.append((i, "démarrage")); continue
        page.wait_for_timeout(4000)        # après l'écran de démarrage (environ 3 s chez fmini et pigeon), qui ignore le panneau
        before = page.evaluate(shot)
        page.evaluate("window.__host.turn('SELECT', 3)")
        page.wait_for_timeout(400)
        page.evaluate("window.__host.keyDown(12, 't')")
        page.wait_for_timeout(500)
        level = rms(page)
        page.evaluate("window.__host.keyUp('t')")
        if page.evaluate(shot) == before and level <= 0.001:
            mute.append((i, "aucune réaction"))
    assert not mute, mute


def _wav(path, seconds, hz, rate=22050):
    import math, struct, wave
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        n = int(seconds * rate)
        w.writeframes(b"".join(struct.pack("<h", int(12000 * math.sin(2 * math.pi * hz * i / rate) * (1 - i / n))) for i in range(n)))


def test_pigeon_echantillons(page, tmp_path):
    """pigeon, un échantillonneur livré vide : un son long devient sa chanson, les courts ses pads, et il joue ; la banque revient."""
    _natif("pigeon")
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "pigeon") is True
    page.wait_for_timeout(4000)                          # l'écran de démarrage
    assert page.is_visible("#samples-box") and page.is_hidden(".file >> nth=0")
    _wav(tmp_path / "chanson.wav", 4, 220); _wav(tmp_path / "coup.wav", 0.3, 880)
    page.set_input_files("#samples", [str(tmp_path / "chanson.wav"), str(tmp_path / "coup.wav")])
    page.wait_for_function("document.getElementById('status').textContent.includes('Samples loaded')", timeout=20000)
    level = 0
    for k in (0, 2, 4, 5, 7, 12):
        page.evaluate(f"window.__host.keyDown({k}, 't')")
        for _ in range(3):
            page.wait_for_timeout(120); level = max(level, rms(page))
        page.evaluate("window.__host.keyUp('t')")
    assert level > 0.001, level
    page.wait_for_function("window.__engine().pendingSave === null", timeout=5000)
    power_on(page)
    assert use(page, "pigeon") is True
    assert page.evaluate("!!(window.__engine().bank && window.__engine().bank.image.length > 4096)")


def test_sim_gets_midi_in_its_format(page):
    """Les firmwares sim (OberVave, zp12…) lisent {t: 'midi', d} : une note MIDI y arrive et sonne."""
    _natif("obervave")
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "obervave") is True
    page.wait_for_timeout(3000)
    page.evaluate("() => { const n = window.__engine(), s = n.send.bind(n); window.__sent = []; n.send = (m, t) => { window.__sent.push(m); return s(m, t); }; }")
    page.evaluate("window.__engine().midiIn(Uint8Array.from([0x90, 60, 110]))")
    page.wait_for_timeout(500)
    level = rms(page)
    page.evaluate("window.__engine().midiIn(Uint8Array.from([0x80, 60, 0]))")
    assert page.evaluate("window.__sent[0]") == {"t": "midi", "d": [0x90, 60, 110]}
    assert level > 0.001, level


def _natif(i):
    import json, os, pytest
    from conftest import ROOT
    try:
        if i not in json.load(open(os.path.join(ROOT, "natif/manifest.json"))): pytest.skip(f"{i} pas encore natif ici")
    except FileNotFoundError:
        pytest.skip("pas de natif/")


def _note(page, msg, wait=500):
    page.evaluate(f"window.__engine().midiIn(Uint8Array.from({msg}))")
    page.wait_for_timeout(wait)
    return rms(page)


def test_hortator_midi_and_saves(page):
    """Hortator : une note MIDI (canal 10, 36 la grosse caisse) frappe sa piste ; ses démos, écrites au premier
    démarrage, reviennent à l'ouverture suivante."""
    _natif("hortator")
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "hortator") is True
    page.wait_for_timeout(3000)
    quiet = rms(page)
    level = _note(page, "[0x99, 36, 120]", 150)
    assert level > max(0.001, quiet * 2), (quiet, level)
    page.wait_for_function("window.__engine().pendingSave === null", timeout=8000)
    power_on(page)
    assert use(page, "hortator") is True
    assert len(page.evaluate("Object.keys(window.__engine().lastLoadSectors || {})")) > 0


def test_zp12_midi_plays_pads(page):
    """zp12 : les notes 36 à 67 jouent ses 32 pads, sur tout canal."""
    _natif("zp12")
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "zp12") is True
    page.wait_for_timeout(3500)
    quiet = rms(page)
    level = _note(page, "[0x90, 36, 120]", 150)
    assert level > max(0.001, quiet * 2), (quiet, level)


def test_zp12_samples(page, tmp_path):
    """zp12 : deux sons de l'ordinateur sur les pads C1 et C2, comme son éditeur web les met sur l'appareil ; une note
    MIDI les joue (C1 : la note 52), et ils reviennent à l'ouverture suivante."""
    _natif("zp12")
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "zp12") is True
    page.wait_for_timeout(3500)
    assert page.is_visible("#samples-box")
    _wav(tmp_path / "bip.wav", 0.4, 660); _wav(tmp_path / "boum.wav", 0.6, 110)
    page.set_input_files("#samples", [str(tmp_path / "bip.wav"), str(tmp_path / "boum.wav")])
    page.wait_for_function("document.getElementById('status').textContent.startsWith('zp12 : 2 samples')", timeout=30000)
    assert "C1 to C2" in page.inner_text("#status")
    page.wait_for_timeout(1500)                                         # (ASSIGN fait entendre le son tout de suite : qu'il finisse)
    quiet = rms(page)
    level = _note(page, "[0x90, 52, 120]", 150)
    assert level > max(0.001, quiet * 2), (quiet, level)
    page.wait_for_function("window.__engine().pendingSave === null", timeout=8000)
    power_on(page)
    assert use(page, "zp12") is True
    keys = page.evaluate("Object.keys(window.__engine().lastLoadSectors || {}).map(Number)")
    assert 0xD8000 in keys or 0xD9000 in keys                            # le répertoire
    assert any(k >= 0xDA000 for k in keys if k not in (0xD8000, 0xD9000))   # les sons, hors de sa réserve


def test_melodee_plays(page):
    """Melodee : une touche et une note MIDI jouent la piste 1, la touche tenue s'allume ; PLAY lance le transport
    (sa lumière verte) et l'arrête ; SEQ change l'écran."""
    _natif("melodee")
    shot = "() => { const c = document.getElementById('screen'), d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let h = 0; for (let i = 0; i < d.length; i += 16) h = (h * 31 + d[i] + d[i + 1] + d[i + 2]) | 0; return h; }"
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "melodee") is True
    page.wait_for_timeout(3000)
    assert lit_pixels(page) >= 500
    quiet = rms(page)
    page.evaluate("window.__host.keyDown(12, 't')")
    page.wait_for_timeout(400)
    level = rms(page)
    assert level > max(0.001, quiet * 2), (quiet, level)
    assert page.evaluate("window.__engine().keyLit(12)")
    page.evaluate("window.__host.keyUp('t')")
    page.wait_for_timeout(1500)
    level = _note(page, "[0x90, 60, 110]", 400)
    assert level > 0.001, level
    _note(page, "[0x80, 60, 0]", 100)
    before = page.evaluate(shot)
    page.evaluate("window.__host.press('SEQ')"); page.wait_for_timeout(150); page.evaluate("window.__host.release('SEQ')")
    page.wait_for_timeout(500)
    assert page.evaluate(shot) != before
    page.evaluate("window.__host.press('PLAY')"); page.wait_for_timeout(150); page.evaluate("window.__host.release('PLAY')")
    page.wait_for_function("window.__engine().playLight() === 'green'", timeout=3000)
    page.evaluate("window.__host.press('PLAY')"); page.wait_for_timeout(150); page.evaluate("window.__host.release('PLAY')")
    page.wait_for_function("window.__engine().playLight() === null", timeout=3000)


def test_gator_plays_and_saves(page):
    """GATOR : une touche (mode GATE) et une note MIDI sonnent, la touche tenue s'allume ; SAVE deux fois écrit le preset,
    que la page garde et rend à l'ouverture suivante."""
    _natif("gator")
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "gator") is True
    page.wait_for_timeout(2500)
    assert lit_pixels(page) >= 500
    quiet = rms(page)
    page.evaluate("window.__host.keyDown(12, 't')")
    page.wait_for_timeout(400)
    level = rms(page)
    assert level > max(0.001, quiet * 2), (quiet, level)
    assert page.evaluate("window.__engine().keyLit(12)")
    page.evaluate("window.__host.keyUp('t')")
    page.wait_for_timeout(1500)
    assert _note(page, "[0x90, 60, 110]", 400) > 0.001
    _note(page, "[0x80, 60, 0]", 100)
    for _ in range(2):
        page.evaluate("window.__host.press('SAVE')"); page.wait_for_timeout(150); page.evaluate("window.__host.release('SAVE')")
        page.wait_for_timeout(400)
    page.wait_for_function("window.__engine().pendingSave === null", timeout=8000)
    power_on(page)
    assert use(page, "gator") is True
    assert "store" in page.evaluate("Object.keys(window.__engine().lastLoadSectors || {})")


def test_modelar_drone(page):
    """MODELAR : les volumes partent de 0 ; K1 monté, l'oscillateur 1 sonne sans touche ; une touche blanche déplace le
    curseur du pad (l'écran change)."""
    _natif("modelar")
    shot = "() => { const c = document.getElementById('screen'), d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let h = 0; for (let i = 0; i < d.length; i += 16) h = (h * 31 + d[i] + d[i + 1] + d[i + 2]) | 0; return h; }"
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "modelar") is True
    page.wait_for_timeout(3000)
    assert lit_pixels(page) >= 500
    for _ in range(6):
        page.evaluate("window.__host.turn('KNOB1', 5)"); page.wait_for_timeout(80)
    page.wait_for_timeout(800)
    assert rms(page) > 0.001
    before = page.evaluate(shot)
    page.evaluate("window.__host.keyDown(0, 't')")
    page.wait_for_timeout(600)
    page.evaluate("window.__host.keyUp('t')")
    assert page.evaluate(shot) != before


def test_beat_natives_play(page):
    """MNM-1, Cut-A-Dor, MYCELIUM : PLAY (ou une touche) fait sonner la machine ; une touche tenue s'allume ou
    l'écran change."""
    import json, os, pytest
    from conftest import ROOT
    try:
        have = json.load(open(os.path.join(ROOT, "natif/manifest.json")))
    except FileNotFoundError:
        pytest.skip("pas de natif/")
    listed = {e["id"] for e in json.load(open(os.path.join(ROOT, "tools/natif.json")))["firmwares"]}
    ids = [i for i in ("mnm1", "cutador", "mycelium") if i in listed]
    if not ids: pytest.skip("aucun des trois à compiler ici")
    assert all(i in have for i in ids), [i for i in ids if i not in have]   # (une compilation ratée : il serait émulé)
    power_on(page)
    page.set_default_timeout(30000)
    bad = []
    for i in ids:
        assert use(page, i) is True, i
        assert page.evaluate("window.__engine().kind") == "natif", i
        page.wait_for_timeout(4500)                 # (MYCELIUM : son logo, environ quatre secondes)
        if lit_pixels(page) < 500: bad.append((i, "écran")); continue
        page.evaluate("window.__host.press('PLAY')"); page.wait_for_timeout(150); page.evaluate("window.__host.release('PLAY')")
        page.wait_for_timeout(1500)
        level = rms(page)
        if level <= 0.001:
            page.evaluate("window.__host.keyDown(0, 't')"); page.wait_for_timeout(600)
            level = rms(page); page.evaluate("window.__host.keyUp('t')")
        if level <= 0.001: bad.append((i, "silence"))
        page.evaluate("window.__host.press('PLAY')"); page.wait_for_timeout(150); page.evaluate("window.__host.release('PLAY')")
    assert not bad, bad


def test_cutador_saves(page):
    """Cut-A-Dor : SAVE, à l'arrêt, écrit le projet, que la page garde et rend à l'ouverture suivante."""
    _natif("cutador")
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "cutador") is True
    page.wait_for_timeout(2500)
    page.evaluate("window.__host.press('SAVE')"); page.wait_for_timeout(150); page.evaluate("window.__host.release('SAVE')")
    page.wait_for_timeout(600)
    page.wait_for_function("window.__engine().pendingSave === null", timeout=8000)
    power_on(page)
    assert use(page, "cutador") is True
    assert "store" in page.evaluate("Object.keys(window.__engine().lastLoadSectors || {})")


def test_fmdj_rom(page, tmp_path):
    """FMDj : sans ROM, la page la demande (« ROM… ») ; un fichier qui n'en est pas une est refusé par l'outil de sa
    page (lsdjinstall.js, l'émulateur de son installateur), avec la raison."""
    _natif("fmdj")
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "fmdj") is True
    page.wait_for_timeout(2000)
    assert lit_pixels(page) >= 300
    assert page.is_visible("#samples-box") and page.inner_text("#samples-box").strip() == "ROM…"
    (tmp_path / "pas-une-rom.gb").write_bytes(bytes(32768))
    page.set_input_files("#samples", str(tmp_path / "pas-une-rom.gb"))
    page.wait_for_function("document.getElementById('status').textContent.startsWith('ROM : This file is not')", timeout=30000)


def test_keys_natives_play(page):
    """SPAMPY, Scintilla, Bytemania : chacun, listé dans tools/natif.json, tourne en natif ; une touche tenue sonne."""
    import json, os, pytest
    from conftest import ROOT
    try:
        have = json.load(open(os.path.join(ROOT, "natif/manifest.json")))
    except FileNotFoundError:
        pytest.skip("pas de natif/")
    listed = {e["id"] for e in json.load(open(os.path.join(ROOT, "tools/natif.json")))["firmwares"]}
    ids = [i for i in ("spampy", "scintilla", "bytemania") if i in listed]
    if not ids: pytest.skip("aucun des trois à compiler ici")
    assert all(i in have for i in ids), [i for i in ids if i not in have]
    power_on(page)
    page.set_default_timeout(30000)
    bad = []
    for i in ids:
        assert use(page, i) is True, i
        assert page.evaluate("window.__engine().kind") == "natif", i
        page.wait_for_timeout(4000)
        if lit_pixels(page) < 500: bad.append((i, "écran")); continue
        page.evaluate("window.__host.keyDown(12, 't')"); page.wait_for_timeout(700)
        level = rms(page); page.evaluate("window.__host.keyUp('t')")
        if level <= 0.001: bad.append((i, "silence"))
        page.wait_for_timeout(500)
    assert not bad, bad
