"""Duo host-clock integration tests. Real native and CPU-emulated receivers, no FM-1+VA leader."""

import statistics
from test_duo import open_duo, power


def native(frame, fw_id):
    frame.wait_for_function(f"window.__catalogue && window.__catalogue.some(e => e.id === '{fw_id}' && e.natif)")
    assert frame.evaluate(f"() => window.__useEngine(window.__catalogue.find(e => e.id === '{fw_id}' && e.natif))")
    frame.wait_for_function("window.__engine().kind === 'natif'")


def capture(frame):
    frame.evaluate("""() => {
      const e = window.__engine();
      const original = e.midiIn.bind(e);
      window.__clockBytes = [];
      e.midiIn = (bytes) => { window.__clockBytes.push([...bytes][0]); return original(bytes); };
    }""")


def test_host_clock_native_to_native_play_stop_and_24ppqn(page):
    """Two independent native engines receive Start/Clock/Stop from one host sample clock."""
    a, b = open_duo(page, 1600, 900)
    power(a)
    power(b)
    native(a, "hortator")
    native(b, "felucca")
    capture(a)
    capture(b)
    page.click(".duo-link")
    assert page.get_attribute(".duo-link", "aria-checked") == "true"
    assert page.get_attribute(".duo-play", "aria-pressed") == "false"
    page.click(".duo-play")
    page.wait_for_function("window.__duo.stats.pulses >= 30", timeout=10000)
    stats = page.evaluate("""() => ({
      ...window.__duo.stats,
      bpm: window.__duo.bpm,
      rate: window.__duo.sampleRate
    })""")
    assert stats["bpm"] == 120
    assert stats["rate"] > 0
    diffs = [b-a for a,b in zip(stats["frames"], stats["frames"][1:])]
    # These are actual AudioWorklet sample frames, not main-thread arrival times.
    want = stats["rate"] * 60 / (24 * stats["bpm"])
    assert abs(statistics.median(diffs) - want) <= 2, (diffs, want)
    for frame in (a,b):
        data = frame.evaluate("window.__clockBytes")
        assert 0xFA in data and data.count(0xF8) >= 25
    page.click(".duo-play")
    page.wait_for_function("!window.__duo.playing")
    for frame in (a,b):
        assert 0xFC in frame.evaluate("window.__clockBytes")


def test_host_clock_changes_tempo_without_synth_leader(page):
    a,b = open_duo(page, 1600, 900)
    power(a)
    power(b)
    native(a, "hortator")
    native(b, "felucca")
    page.click(".duo-link")
    page.fill(".duo-bpm", "150")
    page.locator(".duo-bpm").dispatch_event("change")
    page.click(".duo-play")
    page.wait_for_function("window.__duo.stats.pulses >= 36", timeout=10000)
    stats = page.evaluate("""() => ({
      frames: window.__duo.stats.frames,
      rate: window.__duo.sampleRate
    })""")
    intervals = [b-a for a,b in zip(stats["frames"], stats["frames"][1:])]
    expected = stats["rate"] * 60 / (150 * 24)
    assert abs(statistics.median(intervals) - expected) < 2
    page.click(".duo-link")
    assert not page.evaluate("window.__duo.playing")
    assert page.get_attribute(".duo-play", "aria-pressed") == "false"


def test_native_hortator_sequencer_follows_real_host_transport(page):
    """Observe Hortator's *own* PLAY LED while using its GLOBAL CLK USB setting."""
    a,b = open_duo(page, 1600, 900)
    power(a)
    power(b)
    native(a, "hortator")
    native(b, "felucca")
    a.evaluate("window.__engine().press('GLO')")
    a.wait_for_timeout(130)
    a.evaluate("window.__engine().release('GLO')")
    a.wait_for_timeout(140)
    a.evaluate("window.__engine().turn('KNOB3', 1)")
    a.wait_for_timeout(250)
    assert a.evaluate("window.__engine().playLight()") != "green"
    page.click(".duo-link")
    page.click(".duo-play")
    a.wait_for_function("window.__engine().playLight() === 'green'", timeout=6000)
    page.click(".duo-play")
    a.wait_for_function("window.__engine().playLight() !== 'green'", timeout=6000)


def test_cpu_emulator_receives_host_clock_via_virtual_trs(page):
    """The imported .fwsc path uses Joakim's MIDI UART, not the native worklet."""
    a,b = open_duo(page, 1600, 900)
    power(a)
    power(b)
    native(b, "felucca")
    a.wait_for_function("window.__catalogue && window.__catalogue.some(e => e.id === 'sloop' && e.fichier)")
    # SLOOP remains an actual CPU-emulated .fwsc. Hortator is native-only in
    # the curated catalogue and no longer ships a bundled .fwsc package.
    ok = a.evaluate("""() => {
      const e = window.__catalogue.find(e => e.id === 'sloop');
      return window.__useEngine(e);
    }""")
    assert ok
    a.wait_for_function("window.__engine().kind === 'emu'", timeout=20000)
    capture(a)
    capture(b)
    page.click(".duo-link")
    page.click(".duo-play")
    page.wait_for_function("window.__duo.stats.pulses >= 12", timeout=10000)
    for fr in (a,b):
        midi = fr.evaluate("window.__clockBytes")
        assert 0xFA in midi and midi.count(0xF8) >= 8
    page.click(".duo-play")
    assert 0xFC in a.evaluate("window.__clockBytes")


def test_rapid_start_stop_restart_never_forwards_stale_stop(page):
    """A late worklet Stop from a previous session cannot stop a newer Start."""
    a,b = open_duo(page, 1600, 900)
    power(a)
    power(b)
    native(a, "hortator")
    native(b, "felucca")
    capture(a)
    capture(b)
    page.click(".duo-link")
    page.click(".duo-play")
    page.wait_for_function("window.__duo.stats.pulses > 5", timeout=10000)
    page.click(".duo-play")
    page.click(".duo-play")
    page.wait_for_function("window.__duo.playing && window.__duo.stats.pulses > 8", timeout=10000)
    for frame in (a,b):
        messages = frame.evaluate("window.__clockBytes")
        assert messages.count(0xFA) == 2
        assert messages.count(0xFC) == 1
        assert messages.index(0xFC) < len(messages) - 1
        assert messages[-1] == 0xF8  # no stale Stop after the new Start
    page.click(".duo-play")


def test_unlink_cancels_worklet_start_in_progress(page):
    """Tap Play then immediately unlink: no delayed Start after async addModule."""
    a,b = open_duo(page, 1600, 900)
    power(a)
    power(b)
    native(a, "hortator")
    native(b, "felucca")
    capture(a)
    capture(b)
    page.click(".duo-link")
    page.click(".duo-play")
    page.click(".duo-link")
    page.wait_for_timeout(200)
    assert page.get_attribute(".duo-link", "aria-checked") == "false"
    assert not page.evaluate("window.__duo.playing")
    counts = [frame.evaluate("window.__clockBytes.length") for frame in (a,b)]
    # A fast browser might complete Start before the second click. In that
    # case it must send Stop; no additional messages may arrive after unlink.
    for frame in (a,b):
        messages = frame.evaluate("window.__clockBytes")
        if 0xFA in messages:
            assert 0xFC in messages and messages.index(0xFC) > messages.index(0xFA)
    page.wait_for_timeout(450)
    assert [frame.evaluate("window.__clockBytes.length") for frame in (a,b)] == counts


def test_poweroff_stops_host_clock_and_old_receiver(page):
    """A lost receiver stops the shared transport, rather than leaving B running."""
    a,b = open_duo(page, 1600, 900)
    power(a)
    power(b)
    native(a, "hortator")
    native(b, "felucca")
    capture(a)
    capture(b)
    page.click(".duo-link")
    page.click(".duo-play")
    page.wait_for_function("window.__duo.stats.pulses >= 12", timeout=10000)
    b.evaluate("document.getElementById('power').click()")
    page.wait_for_function("!window.__duo.playing", timeout=5000)
    assert 0xFC in a.evaluate("window.__clockBytes")
    assert page.get_attribute(".duo-play", "aria-pressed") == "false"


def test_invalid_bpm_is_clamped_and_persisted(page):
    a,b = open_duo(page, 1600, 900)
    power(a)
    power(b)
    native(a, "hortator")
    native(b, "felucca")
    page.click(".duo-link")
    page.fill(".duo-bpm", "999")
    page.locator(".duo-bpm").dispatch_event("change")
    assert page.evaluate("window.__duo.bpm") == 240
    assert page.evaluate("localStorage.getItem('fm1.duo.bpm')") == "240"
    page.fill(".duo-bpm", "-40")
    page.locator(".duo-bpm").dispatch_event("change")
    assert page.evaluate("window.__duo.bpm") == 40
    page.click(".duo-play")
    page.wait_for_function("window.__duo.stats.pulses >= 20", timeout=10000)
    info = page.evaluate("() => ({f:window.__duo.stats.frames, r:window.__duo.sampleRate})")
    diffs = [b-a for a,b in zip(info["f"],info["f"][1:])]
    assert abs(statistics.median(diffs) - info["r"] * 60/(24*40)) < 2
    page.click(".duo-play")


def test_cpu_emulator_on_b_uses_separate_save_store_and_receives_clock(page):
    """Actual B-side CPU firmware boots, uses its own IDB and receives 24-PPQN MIDI."""
    a,b = open_duo(page, 1600, 900)
    power(a)
    power(b)
    native(a, "hortator")
    b.wait_for_function("window.__catalogue && window.__catalogue.some(e => e.id === 'fizz')")
    ok = b.evaluate("""() => {
      const e = window.__catalogue.find(e => e.id === 'fizz');
      return window.__useEngine({ ...e, natif: null, natif_wasm: null });
    }""")
    assert ok
    b.wait_for_function("window.__engine().kind === 'emu' && window.__engine().running", timeout=25000)
    database = b.evaluate("async () => (await window.__engine().saveStore.open()).name")
    assert database == "fm1-emulator-b"
    capture(a)
    capture(b)
    page.click(".duo-link")
    page.click(".duo-play")
    page.wait_for_function("window.__duo.stats.pulses >= 12", timeout=10000)
    assert b.evaluate("window.__clockBytes").count(0xF8) >= 10
    page.click(".duo-play")
    assert 0xFC in b.evaluate("window.__clockBytes")


def tap_native(frame, button):
    """A normal short panel-button press; do not invoke the sequencer directly."""
    frame.evaluate("""button => {
      const fw = window.__engine();
      fw.press(button);
      setTimeout(() => fw.release(button), 100);
    }""", button)
    frame.wait_for_timeout(160)


def test_native_hortator_local_play_after_duo_unlink_requires_clk_int(page):
    """Regression for iPad report: panel PLAY in USB mode has no free-running clock.
    Switching the firmware itself back to INT restores local playback.
    """
    a, b = open_duo(page, 1600, 900)
    power(a)
    power(b)
    native(a, "hortator")
    native(b, "hortator")
    for f in (a, b):
        tap_native(f, "GLO")
        f.evaluate("window.__engine().turn('KNOB3', 1)")  # CLK INT -> USB
        f.wait_for_timeout(180)
    page.click(".duo-link")
    page.click(".duo-play")
    for f in (a, b):
        f.wait_for_function("window.__engine().playLight() === 'green'", timeout=6000)
    page.click(".duo-link")  # sends Stop and removes clock pulses
    assert page.get_attribute(".duo-link", "aria-checked") == "false"
    for f in (a, b):
        f.wait_for_function("window.__engine().playLight() !== 'green'", timeout=6000)
        # The control still responds, but USB-clock mode times out with no external pulses.
        tap_native(f, "PLAY")
        f.wait_for_timeout(750)
        assert f.evaluate("window.__engine().playLight()") != "green"
    # App must give specific guidance instead of silently indicating local Play works.
    assert "CLK INT" in page.inner_text(".duo-sync-state")
    assert "CLK" in page.get_attribute(".duo-link", "title")
    for f in (a, b):
        f.evaluate("window.__engine().turn('KNOB3', -1)")  # CLK USB -> INT
        f.wait_for_timeout(220)
        tap_native(f, "PLAY")
        f.wait_for_function("window.__engine().playLight() === 'green'", timeout=4000)
        f.wait_for_timeout(700)  # survives the external-clock 500 ms timeout
        f.wait_for_function("window.__engine().playLight() === 'green'", timeout=3000)
    for f in (a, b):
        tap_native(f, "PLAY")
        f.wait_for_function("window.__engine().playLight() !== 'green'", timeout=4000)
    assert not page.evaluate("window.__duo.playing")


def test_fm1va_local_transport_survives_disabling_duo_sync(page):
    """FM-1+VA must not retain its MIDI follower flag after unlink."""
    a, b = open_duo(page, 1600, 900)
    power(a)
    power(b)
    a.evaluate("window.__fw.seqOn(true)")
    b.evaluate("window.__fw.seqOn(true)")
    page.click(".duo-link")
    page.wait_for_function("window.__duo.linked")
    a.wait_for_function("window.__fw.mi.follow")
    b.wait_for_function("window.__fw.mi.follow")
    page.click(".duo-play")
    a.wait_for_function("window.__fw.S.playing", timeout=6000)
    b.wait_for_function("window.__fw.S.playing", timeout=6000)
    page.click(".duo-link")
    a.wait_for_function("!window.__fw.mi.follow && !window.__fw.S.playing", timeout=6000)
    b.wait_for_function("!window.__fw.mi.follow && !window.__fw.S.playing", timeout=6000)
    a.evaluate("window.__fw.seqPlay()")
    b.evaluate("window.__fw.seqPlay()")
    a.wait_for_function("window.__fw.S.playing", timeout=4000)
    b.wait_for_function("window.__fw.S.playing", timeout=4000)
    page.wait_for_timeout(700)
    assert a.evaluate("window.__fw.S.playing") and b.evaluate("window.__fw.S.playing")
    a.evaluate("window.__fw.seqPlay()")
    b.evaluate("window.__fw.seqPlay()")


def test_midi_delivery_exception_stops_other_receiver_and_reports_fault(page):
    """Throwing adapter must not strand the healthy receiver or leave the host running."""
    a, b = open_duo(page, 1600, 900)
    power(a)
    power(b)
    native(a, "hortator")
    native(b, "hortator")
    capture(a)
    b.evaluate("""() => { window.__engine().midiIn = () => { throw Error('simulated MIDI adapter failure'); }; }""")
    page.click(".duo-link")
    page.click(".duo-play")
    page.wait_for_function("!window.__duo.playing && document.querySelector('.duo-sync-state').textContent.includes('delivery failed')", timeout=10000)
    assert 0xFC in a.evaluate("window.__clockBytes")
    assert page.get_attribute(".duo-play", "aria-pressed") == "false"


def test_turning_off_duo_sync_while_stopped_does_not_send_spurious_stop(page):
    a, b = open_duo(page, 1600, 900)
    power(a)
    power(b)
    native(a, "hortator")
    native(b, "hortator")
    capture(a)
    capture(b)
    page.click(".duo-link")
    assert not page.evaluate("window.__duo.playing")
    page.click(".duo-link")
    assert page.evaluate("window.__duo.stats.stops") == 0
    assert 0xFC not in a.evaluate("window.__clockBytes")
    assert 0xFC not in b.evaluate("window.__clockBytes")
