"""Cross-browser sync smoke test (desktop WebKit is a Safari proxy, not an iPad substitute)."""

from test_duo import open_duo, power
from test_duo_host import native, capture


def test_webkit_host_clock_sends_native_midi_on_both_sides(base_url, playwright_runtime):
    """AudioWorklet must actually run in WebKit; both native engines need clock."""
    browser = playwright_runtime.webkit.launch()
    context = browser.new_context(viewport={"width": 1366, "height": 900})
    try:
        page = context.new_page()
        page.base = base_url
        a, b = open_duo(page, 1600, 900)
        power(a)
        power(b)
        native(a, "hortator")
        native(b, "felucca")
        capture(a)
        capture(b)
        page.click(".duo-link")
        page.click(".duo-play")
        page.wait_for_function("window.__duo.playing && window.__duo.stats.pulses >= 10", timeout=12000)
        for frame in (a, b):
            messages = frame.evaluate("window.__clockBytes")
            assert 0xfa in messages and messages.count(0xf8) >= 8
        page.click(".duo-play")
        assert not page.evaluate("window.__duo.playing")
        for frame in (a, b):
            assert 0xfc in frame.evaluate("window.__clockBytes")
    finally:
        context.close()
        browser.close()
