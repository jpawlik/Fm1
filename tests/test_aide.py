"""L'aide : manuel, raccourcis clavier, fiches par firmware."""

NO_LAYOUT = "Object.defineProperty(Navigator.prototype, 'keyboard', { get: () => undefined });"


def titles(page):
    return page.eval_on_selector_all(".notes > details > summary", "s => s.map(x => x.textContent.trim())")


def test_titres(page):
    page.goto(page.base + "index.html")
    assert titles(page)[:2] == ["User guide", "Keyboard shortcuts"]


def test_manuel_rubriques(page):
    page.goto(page.base + "index.html")
    assert page.eval_on_selector_all("#aide-manuel dt", "d => d.map(x => x.textContent)") == [
        "Power on", "Firmware", "Firmware-specific controls", "Colors", "Solo and Duo", "MIDI", "Full screen",
        "Browser storage", "Credits and licenses"]


def test_clavier_dessine(page):
    page.goto(page.base + "index.html")
    page.click("#aide-clavier summary")
    want = page.evaluate("keyboardModel(keyLetters(navigator.language, null)).keys.filter(k => k.family)"
                         ".map(k => [k.code, k.label])")
    got = page.eval_on_selector_all("#clavier g[data-family]:not([data-family=''])",
                                    "g => g.map(x => [x.dataset.code, x.querySelector('.fonction').textContent])")
    assert sorted(got) == sorted(want) and len(got) == 40          # 18 notes, 16 boutons, 6 sens de molette


def lettre(browser, base, locale, code):
    ctx = browser.new_context(locale=locale)
    ctx.add_init_script(NO_LAYOUT)
    pg = ctx.new_page()
    pg.goto(base + "index.html")
    t = pg.text_content(f"#clavier [data-code='{code}'] .lettre")
    ctx.close()
    return t


def test_azerty_par_defaut(browser, base_url):
    assert lettre(browser, base_url, "fr-FR", "KeyA") == "Q"
    assert lettre(browser, base_url, "en-US", "KeyA") == "A"


def test_volet_large(page):
    page.goto(page.base + "index.html")
    page.click("#aide-clavier summary")
    w = page.evaluate("[document.querySelector('#aide-clavier').offsetWidth, document.querySelector('.notes').clientWidth]")
    assert abs(w[0] - w[1]) <= 2


def test_clavier_iphone(browser, base_url):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    pg = ctx.new_page()
    pg.goto(base_url + "index.html")
    pg.click("#aide-clavier summary")
    over = pg.evaluate("[document.documentElement.scrollWidth, innerWidth]")
    box = pg.evaluate("(() => { const s = document.querySelector('.clavier-scroll'); return [s.scrollWidth, s.clientWidth]; })()")
    ctx.close()
    assert over[0] <= over[1] and box[0] > box[1]


# ---------------------------------------------------------------- les fiches par firmware
import json

from test_picker import click_row
from conftest import power_on


def fake(page, fid, delay=0, status=200, modes=()):
    """Sert une fiche factice pour firmwares/fiches/<fid>.json, après `delay` ms."""
    def handle(route):
        if delay:
            page.wait_for_timeout(delay)
        if status != 200:
            return route.fulfill(status=status, body="")
        body = {"id": fid, "resume": f"Résumé de {fid}.", "commandes": [{"commande": "FX", "role": "Effets de test."}],
                "gestes": [], "modes": list(modes), "source": {"url": f"https://github.com/x/{fid}/blob/y/README.md", "commit": "y"},
                "d_apres_le_code": False}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))
    page.route(f"**/firmwares/fiches/{fid}.json", handle)


def stub_core(page):
    """Le cœur d'émulation n'est pas toujours là (runtime/ n'est pas suivi) : un .wasm factice suffit tant que rien ne démarre."""
    page.route("**/runtime/fm1_web.wasm", lambda r: r.fulfill(status=200, content_type="application/wasm", body=b"\x00asm\x01\x00\x00\x00"))


def open_fiche(page):
    page.click("#aide-fiche summary")


def fiche_titre(page):
    return page.inner_text("#aide-fiche summary").strip()


def test_fiche_fm1va(page):
    page.goto(page.base + "index.html")
    open_fiche(page)
    page.wait_for_selector("#fiche dt")
    assert fiche_titre(page) == "Features of FM-1+VA"
    assert "SEL" in page.eval_on_selector_all("#fiche dt", "d => d.map(x => x.textContent)")
    assert "baudgirl.com" in page.get_attribute("#fiche a", "href")


def test_fiche_suit_le_choix_eteint(page):
    stub_core(page)
    fake(page, "amb")
    page.goto(page.base + "index.html")
    open_fiche(page)
    page.click("#fw-picker")
    click_row(page, "amb")
    page.wait_for_function("document.getElementById('fiche').textContent.includes('Résumé de amb.')")
    assert fiche_titre(page) == "Features of AMB-1"
    assert "Charles Vestal" in page.inner_text(".fiche-meta")


def test_fiche_local(page):
    stub_core(page)
    page.goto(page.base + "index.html")
    open_fiche(page)
    page.set_input_files("#fw-file", files=[{"name": "perso.fwsc", "mimeType": "application/octet-stream", "buffer": b"x" * 64}])
    page.wait_for_function("document.getElementById('fiche').textContent.includes('No information sheet for this firmware.')")


def test_fiche_absente(page):
    stub_core(page)
    fake(page, "amb", status=404)
    page.goto(page.base + "index.html")
    open_fiche(page)
    page.click("#fw-picker")
    click_row(page, "amb")
    page.wait_for_function("document.getElementById('fiche').textContent.includes('No firmware information available yet.')")


def test_fiche_indisponible(page):
    stub_core(page)
    fake(page, "amb", status=500)
    page.goto(page.base + "index.html")
    open_fiche(page)
    page.click("#fw-picker")
    click_row(page, "amb")
    page.wait_for_function("document.getElementById('fiche').textContent.includes('Firmware information is temporarily unavailable.')")


def test_fiche_course(page):
    stub_core(page)
    fake(page, "amb", delay=1500)
    fake(page, "386dx")
    page.goto(page.base + "index.html")
    open_fiche(page)
    page.click("#fw-picker")
    click_row(page, "amb")
    page.click("#fw-picker")
    click_row(page, "386dx")
    page.wait_for_timeout(2500)
    assert "Résumé de 386dx." in page.inner_text("#fiche")
    assert "Résumé de amb." not in page.inner_text("#fiche")


def test_fiche_restauree(browser, base_url):
    ctx = browser.new_context()
    ctx.add_init_script("localStorage.setItem('fm1.firmware', JSON.stringify({id: 'amb', nom: 'AMB-1'}))")
    pg = ctx.new_page()
    pg.goto(base_url + "index.html")
    pg.click("#aide-fiche summary")
    assert pg.inner_text("#aide-fiche summary").strip() == "Features of AMB-1"
    ctx.close()


def test_fiche_echec_garde(page):
    stub_core(page)
    page.route("**/natif/**", lambda r: r.abort())
    page.route("**/firmwares/*.fwsc*", lambda r: r.abort())
    power_on(page)
    page.click("#fw-picker")
    click_row(page, "amb")
    page.wait_for_function("document.getElementById('status').textContent !== ''", timeout=30000)
    assert fiche_titre(page) == "Features of FM-1+VA"


def test_fiche_absente_garde_la_ligne_meta(page):
    stub_core(page)
    fake(page, "amb", status=404)
    page.goto(page.base + "index.html")
    open_fiche(page)
    page.click("#fw-picker")
    click_row(page, "amb")
    page.wait_for_function("document.getElementById('fiche').textContent.includes('No firmware information available yet.')")
    page.wait_for_function("document.getElementById('fiche-meta').textContent.trim().length > 0")


def test_fiche_iphone_sans_debordement(browser, base_url):
    ctx = browser.new_context(viewport={"width": 375, "height": 812}, is_mobile=True, has_touch=True)
    pg = ctx.new_page()
    stub_core(pg)
    fake(pg, "amb", modes=[{"nom": "Potentiomètres en DRUMS et TUNE avec accords", "texte": "Texte."}])
    pg.goto(base_url + "index.html")
    pg.click("#fw-picker")
    click_row(pg, "amb")
    pg.click("#aide-fiche summary")
    pg.wait_for_function("document.getElementById('fiche').textContent.includes('Résumé de amb.')")
    over = pg.evaluate("[document.documentElement.scrollWidth, innerWidth]")
    boite = pg.evaluate("(() => { const f = document.getElementById('fiche'); const d = f.closest('details'); return [f.scrollWidth, d.clientWidth]; })()")
    ctx.close()
    assert over[0] <= over[1] and boite[0] <= boite[1], (over, boite)


def test_manuel_et_fiche_pleine_largeur(browser, base_url):
    ctx = browser.new_context(viewport={"width": 1180, "height": 820})
    pg = ctx.new_page()
    stub_core(pg)
    pg.goto(base_url + "index.html")
    res = {}
    for ident in ("aide-manuel", "aide-fiche"):
        pg.click(f"#{ident} summary")
        res[ident] = pg.evaluate(
            "(i) => { const d = document.getElementById(i); const dt = d.querySelector('dt');"
            " return [d.offsetWidth, document.querySelector('.notes').clientWidth, dt ? dt.offsetWidth : 0, d.querySelector('.note').offsetWidth]; }", ident)
    ctx.close()
    for ident, (w, total, dt, note) in res.items():
        assert abs(w - total) <= 2, (ident, w, total)
        assert note <= 840, (ident, note)
    assert res["aide-manuel"][2] <= res["aide-manuel"][3] * 0.34 + 2, res
