"""Visual regressions for the English, iPad-friendly fork (no DSP or gesture changes)."""


def test_english_navigation(page):
    page.goto(page.base + "index.html")
    assert page.locator("html").get_attribute("lang") == "en"
    assert page.get_by_text("User guide").count() == 1
    assert page.get_by_text("Keyboard shortcuts").count() == 1
    assert page.get_by_text("Colors", exact=True).count() >= 1
    page.click("#fw-picker")
    assert page.get_by_placeholder("Search firmware").count() == 1


def test_knob_markers_are_visible_and_targets_are_separated(page):
    page.goto(page.base + "index.html")
    result = page.evaluate("""() => {
      const knobs = Object.values(window.__panel.knobs);
      const markers = knobs.map(k => k.ind.querySelector('line'));
      const hits = [...document.querySelectorAll('.hit.knob')]
        .map(e => e.getBoundingClientRect());
      const panel = document.querySelector('.device').getBoundingClientRect();
      const collide = (a,b) => a.left < b.right && a.right > b.left &&
                               a.top < b.bottom && a.bottom > b.top;
      let overlaps = 0;
      for (let i=0;i<hits.length;i++)
        for (let j=i+1;j<hits.length;j++)
          if (collide(hits[i],hits[j])) overlaps++;
      return {
        count: knobs.length,
        white: markers.filter(m => m?.getAttribute('stroke') === '#ffffff').length,
        minWidth: Math.min(...hits.map(x => x.width / panel.width)),
        overlaps
      };
    }""")
    assert result["count"] == result["white"] == 8
    assert result["minWidth"] > 0.07
    assert result["overlaps"] == 0


def test_lcd_is_larger_and_square(page):
    page.goto(page.base + "index.html")
    result = page.evaluate("""() => {
      const p = document.querySelector('.device').getBoundingClientRect();
      const s = document.getElementById('screen').getBoundingClientRect();
      return [s.width / p.width, s.width / s.height];
    }""")
    assert 0.22 < result[0] < 0.24
    assert abs(result[1] - 1) < 0.02
