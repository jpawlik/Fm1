"""Dans un artefact Claude, les .fwsc ne sont pas servis : la page les lit en base64 (<fichier>.b64.txt)."""
import base64
import os

from conftest import ROOT, lit_pixels, power_on
from test_emu import use


def test_package_from_base64_copy(page):
    raw = open(os.path.join(ROOT, "firmwares/fizz.fwsc"), "rb").read()
    page.route("**/firmwares/fizz.fwsc", lambda r: r.fulfill(status=404, body="absent"))
    page.route("**/firmwares/fizz.fwsc.b64.txt",
               lambda r: r.fulfill(status=200, content_type="text/plain", body=base64.b64encode(raw).decode()))
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "fizz") is True
    page.wait_for_timeout(3000)
    assert lit_pixels(page) >= 2000
