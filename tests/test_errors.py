"""Cas d'erreur du sélecteur et du moteur émulé."""
import os

from conftest import ROOT, power_on
from test_picker import click_row, ready, wait_status


def test_core_missing(page):
    page.route("**/runtime/fm1_web.wasm", lambda r: r.fulfill(status=404, body="absent"))
    power_on(page)
    page.click("#fw-picker")
    page.wait_for_selector('.fw-item[data-id="fizz"][aria-disabled="true"]', state="attached")
    assert page.get_attribute('.fw-item[data-id="fm1va"]', "aria-disabled") is None
    assert page.is_visible("text=Emulation core unavailable")
    click_row(page, "fizz")
    assert page.evaluate("window.__engine() === window.__fw")


def test_online_package_unreachable(page):
    # The retained native Skiff becomes an online .fwsc without native artifacts.
    page.route("**/natif/manifest.json", lambda r: r.fulfill(status=200, body="{}", content_type="application/json"))
    page.route("https://thefirmwarehub.com/**", lambda r: r.fulfill(status=503, body="indisponible"))
    power_on(page)
    nom = page.evaluate("window.__catalogue.find((e) => e.id === 'skiff').nom")
    click_row(page, "skiff")
    wait_status(page, f"{nom} : firmware package unavailable.")
    assert page.evaluate("window.__engine() === window.__fw")


def test_truncated_package(page):
    data = open(os.path.join(ROOT, "firmwares", "sloop.fwsc"), "rb").read()[:1000]
    page.route("**/firmwares/sloop.fwsc", lambda r: r.fulfill(status=200, body=data, content_type="application/octet-stream"))
    power_on(page)
    click_row(page, "sloop")
    wait_status(page, "SLOOP could not start.")
    assert page.evaluate("window.__engine() === window.__fw")


def test_storage_unavailable(page):
    page.add_init_script("Object.defineProperty(window, 'indexedDB', { value: undefined })")
    power_on(page)
    click_row(page, "fizz")
    page.wait_for_function("document.getElementById('status').textContent.includes('Saves are unavailable in this browser.')", timeout=30000)
    assert page.evaluate("window.__engine().name") == "FIZZ"


def test_invalid_local_file(page, tmp_path):
    f = tmp_path / "notes.fwsc"
    f.write_text("ceci n'est pas un firmware")
    power_on(page)
    page.set_input_files("#fw-file", str(f))
    wait_status(page, "This is not an FM-1 firmware package.")
    assert page.evaluate("window.__engine() === window.__fw")
    assert page.inner_text("#fw-name") == "FM-1+VA"


def test_halted_restart(page):
    power_on(page)
    click_row(page, "fizz")
    ready(page, "FIZZ")
    page.evaluate("""() => { const e = window.__engine();
      e.onWorklet({ data: { type: 'frame', seq: e.seq, halted: 1, lcd: null, leds: new Float32Array(41) } }); }""")
    wait_status(page, "FIZZ stopped.")
    assert page.is_visible("#fw-restart")
    page.click("#fw-restart")
    ready(page, "FIZZ")
    assert not page.is_visible("#fw-restart")
    assert page.evaluate("window.__engine().halted") == 0
