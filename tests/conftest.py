import os

import pytest
from playwright.sync_api import sync_playwright

from serve import serve

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session")
def base_url():
    with serve(ROOT) as url:
        yield url


@pytest.fixture(scope="session")
def playwright_runtime():
    # One shared event loop for Chromium and WebKit: nesting sync_playwright()
    # inside an already-running Sync API fixture raises an asyncio-loop error.
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright_runtime):
    b = playwright_runtime.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    yield b
    b.close()


@pytest.fixture
def page(browser, base_url):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    pg.base = base_url
    yield pg
    ctx.close()


def power_on(page, path="index.html"):
    page.goto(page.base + path)
    page.click("#go")
    page.wait_for_function("document.getElementById('power').getAttribute('aria-checked') === 'true'", timeout=20000)
    # l'écran d'accueil de FM-1+VA ignore les touches tant qu'il est affiché
    page.wait_for_function("!window.__fw.splash", timeout=20000)


def lit_pixels(page):
    """Nombre de pixels non noirs du canvas #screen."""
    return page.evaluate("""() => {
      const c = document.getElementById('screen'), d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
      let n = 0; for (let i = 0; i < d.length; i += 4) if (d[i] + d[i + 1] + d[i + 2] > 30) n++; return n; }""")
