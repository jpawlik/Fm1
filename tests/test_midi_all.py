"""Le MIDI pour tous les firmwares : l'entrée et le canal choisis, le voyant ; un émulé reçoit le MIDI et l'horloge du tempo lié."""
from conftest import power_on
from test_emu import use


def test_route_channel_and_input(page):
    power_on(page)
    page.evaluate("""() => { const fw = window.__fw; window.__got = []; const f = fw.midiIn.bind(fw); fw.midiIn = (d) => { window.__got.push(Array.from(d)); return f(d); }; }""")
    page.evaluate("window.__midiRoute({ name: 'Clavier' }, Uint8Array.from([0x93, 60, 100]))")
    page.evaluate("() => { const s = document.getElementById('midi-ch'); s.value = '5'; s.dispatchEvent(new Event('change')); }")   # un canal imposé
    page.evaluate("window.__midiRoute({ name: 'Clavier' }, Uint8Array.from([0x93, 62, 100]))")
    page.evaluate("window.__midiRoute({ name: 'Clavier' }, Uint8Array.from([0xF8]))")   # le temps réel n'a pas de canal
    assert page.evaluate("window.__got") == [[0x93, 60, 100], [0x94, 62, 100], [0xF8]]
    assert page.evaluate("localStorage.getItem('fm1.midi.ch')") == "5"
    page.evaluate("() => { const s = document.getElementById('midi-in'); s.add(new Option('Pads', 'Pads')); s.value = 'Pads'; s.dispatchEvent(new Event('change')); }")
    page.evaluate("window.__midiRoute({ name: 'Clavier' }, Uint8Array.from([0x90, 64, 100]))")   # une autre entrée : ignorée
    page.evaluate("window.__midiRoute({ name: 'Pads' }, Uint8Array.from([0x90, 65, 100]))")
    assert page.evaluate("window.__got.length") == 4 and page.evaluate("window.__got[3]") == [0x94, 65, 100]


def test_popover_and_light(page):
    power_on(page)
    page.evaluate("document.getElementById('midi-box').hidden = false")   # (Web MIDI absent du navigateur de test)
    page.click("#midi-btn")
    assert page.is_visible("#midi-pop") and page.get_attribute("#midi-btn", "aria-expanded") == "true"
    page.evaluate("window.__midiRoute({ name: 'x' }, Uint8Array.from([0x90, 60, 1]))")
    assert page.evaluate("document.getElementById('midi-btn').classList.contains('rx')")
    page.mouse.click(5, 5)
    assert not page.is_visible("#midi-pop")


def test_emulated_takes_midi(page):
    power_on(page)
    page.set_default_timeout(30000)
    assert use(page, "fizz") is True
    page.evaluate("() => { const e = window.__engine(), s = e.send.bind(e); window.__sent = []; e.send = (m) => { if (m.type === 'midi') window.__sent.push(m.bytes); return s(m); }; }")
    page.evaluate("window.__midiRoute({ name: 'x' }, Uint8Array.from([0x90, 60, 100]))")
    assert page.evaluate("window.__engine().kind") == "emu"
    assert page.evaluate("window.__sent") == [[0x90, 60, 100]]
