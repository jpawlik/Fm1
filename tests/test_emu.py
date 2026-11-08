"""Moteur émulé fm1-emu derrière le panneau, et changement de moteur."""
from conftest import lit_pixels, power_on

FLASH = 1 << 20
SECTOR = 4096


def use(page, fid):
    """Démarre un firmware du catalogue ("fm1va" pour la réimplémentation) ; renvoie le booléen de useEngine."""
    return page.evaluate("""async (id) => window.__useEngine(id === 'fm1va' ? { id } : window.__catalogue.find((e) => e.id === id))""", fid)


def rms(page):
    return page.evaluate("""() => { const an = window.__engine().an, d = new Float32Array(an.fftSize);
      an.getFloatTimeDomainData(d); let s = 0; for (const x of d) s += x * x; return Math.sqrt(s / d.length); }""")


def stored_sectors(page):
    """Positions des secteurs enregistrés pour le paquet actif."""
    return page.evaluate("""async () => { const e = window.__engine(), r = await e.saveStore.load(e.hash);
      return r ? r.sectors.map((s) => s.at) : null; }""")


def test_boot_felucca(page):
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "fizz") is True
    page.wait_for_timeout(3000)
    assert lit_pixels(page) >= 2000
    page.evaluate("window.__host.keyDown(12, 't')")
    page.wait_for_timeout(500)
    level = rms(page)
    page.evaluate("window.__host.keyUp('t')")
    assert level > 0.001, level


def test_same_audiocontext(page):
    power_on(page)
    page.evaluate("window.__ac0 = window.__ac")
    assert use(page, "fizz") is True
    assert use(page, "fm1va") is True
    assert use(page, "sloop") is True                    # (un émulé : zp12 est natif)
    assert page.evaluate("window.__ac === window.__ac0")


def test_no_stuck_key(page):
    power_on(page)
    page.evaluate("window.__host.keyDown(5, 's')")
    assert page.evaluate("window.__engine().keyNotes.size") == 1
    assert use(page, "fizz") is True
    assert use(page, "fm1va") is True
    assert page.evaluate("window.__engine().keyNotes.size") == 0


def test_crisp_lcd(page):
    power_on(page)
    assert use(page, "fizz") is True
    page.wait_for_timeout(1000)
    smooth = page.evaluate("""() => { const c = document.getElementById('screen'); c.width = c.height = 731;
      window.__engine().draw(); return c.getContext('2d').imageSmoothingEnabled; }""")
    assert smooth is False


def _seed_sector(page, fid):
    """Enregistre pour `fid` une sauvegarde contenant le dernier secteur de flash, comme l'aurait fait le firmware."""
    page.evaluate(f"""async (id) => {{ const e = window.__engine(), entry = window.__catalogue.find((x) => x.id === id);
      const bytes = new Uint8Array(await (await fetch(entry.fichier)).arrayBuffer()), hash = await e.mod.packageHash(bytes);
      const r = await e.saveStore.load(hash), data = new Uint8Array({SECTOR}).fill(0xa5);
      await e.saveStore.save({{ ...r, sectors: [{{ at: {FLASH - SECTOR}, data }}] }}, 'fm1.' + id); }}""", fid)


def test_saves_kept(page):
    power_on(page)
    assert use(page, "fizz") is True
    assert use(page, "sloop") is True                    # (un émulé : zp12 est natif)
    _seed_sector(page, "fizz")
    assert use(page, "fizz") is True
    page.wait_for_timeout(500)
    # le secteur a été restauré dans la flash au démarrage, puis réenregistré par l'instantané de démarrage
    assert FLASH - SECTOR in stored_sectors(page)


def test_factory_reset_emu(page):
    power_on(page)
    assert use(page, "fizz") is True
    assert use(page, "sloop") is True                    # (un émulé : zp12 est natif)
    _seed_sector(page, "fizz")
    assert use(page, "fizz") is True
    page.wait_for_timeout(500)
    assert FLASH - SECTOR in stored_sectors(page)
    ok = page.evaluate("async () => window.__engine().boot(window.__catalogue.find((e) => e.id === 'fizz'), { reset: true })")
    assert ok is True
    page.wait_for_timeout(500)
    assert stored_sectors(page) == []


def test_va_still_works(page):
    power_on(page)
    assert use(page, "fizz") is True
    assert use(page, "fm1va") is True
    assert page.evaluate("window.__engine() === window.__fw")
    page.evaluate("window.__host.keyDown(12, 't')")
    page.wait_for_timeout(300)
    page.evaluate("window.__host.keyUp('t')")
    assert lit_pixels(page) >= 1000
    assert page.evaluate("window.__fw.on") is True


def test_audio_ahead_default(page):
    """L'avance du son reste celle de fm1-emu (1 024) : 256 multipliait les quanta trop longs."""
    power_on(page)
    page.set_default_timeout(30000)
    page.evaluate("""() => { const e = window.__engine(); window.__sent = [];
      const orig = EmuFirmware.prototype.send;
      EmuFirmware.prototype.send = function (m) { window.__sent.push(m.type === 'boot' ? { type: 'boot', ahead: m.ahead } : { type: m.type }); return orig.call(this, m); }; }""")
    assert use(page, "sloop") is True                    # (un émulé : zp12 est natif)
    assert page.evaluate("window.__sent.find((m) => m.type === 'boot').ahead") is None
    page.wait_for_timeout(1500)
    page.evaluate("window.__host.keyDown(12, 't')")
    page.wait_for_timeout(500)
    level = rms(page)
    page.evaluate("window.__host.keyUp('t')")
    assert level > 0.0001, level


def test_screen_60fps(page):
    """Le cœur envoie l'écran environ 60 fois par seconde et la page le redessine à chaque image."""
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "fizz") is True
    page.wait_for_timeout(1000)
    rates = page.evaluate("""() => new Promise((done) => {
      const e = window.__engine(), o = e.onWorklet.bind(e), d = e.draw.bind(e); let frames = 0, draws = 0;
      e.onWorklet = (ev) => { if (ev.data.type === 'frame') frames++; o(ev); };
      e.draw = () => { draws++; d(); };
      setTimeout(() => { e.onWorklet = o; e.draw = d; done({ frames: frames / 2, draws: draws / 2 }); }, 2000); })""")
    assert rates["frames"] >= 50, rates
    assert rates["draws"] > 36, rates   # au-dessus de l'ancien plafond (33) ; le dessin suit requestAnimationFrame, qui ralentit sous charge
