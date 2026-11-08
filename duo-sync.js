// SPDX-License-Identifier: MIT
// Duo host MIDI clock. No firmware-specific clock source is required.
// The 24-PPQN pulse *timeline* lives in duo-clock.js (AudioWorklet); messages
// reach each engine via the existing midiIn adapter. MessagePort delivery is
// not sample-accurate between the two iframe AudioContexts.
(function () {
  "use strict";
  window.setupDuoHost = function ({ frames, tabsOf, show, keep, linkBtn, tempoBox, playBtn, state, initialLinked }) {
    const clamp = (v) => Math.max(40, Math.min(240, Math.round(Number(v) || 120)));
    let bpm = clamp(keep("bpm") || 120);
    let linked = initialLinked, playing = false, starting = false, ctx = null, node = null, setup = null;
    let epoch = 0; // invalidates stale worklet messages and asynchronous start requests
    let currentPlayers = null, pendingPlayers = null, cached = { a: null, b: null };
    const stats = { pulses: 0, starts: 0, stops: 0, late: 0, maxLagMs: 0, frames: [], arrivals: [] };
    tempoBox.value = String(bpm);

    function engine(k) {
      try {
        const w = frames[k].contentWindow, e = w.__engine && w.__engine();
        // A halted CPU emulation instance cannot consume further MIDI clock.
        return e && e.on && !(e.kind === "emu" && (e.halted || !e.live)) &&
          typeof e.midiIn === "function" ? e : null;
      } catch { return null; }
    }
    const engines = () => ({ a: engine("a"), b: engine("b") });
    const ready = (e) => !!(e.a && e.b);
    const same = (a, b) => !!a && !!b && a.a === b.a && a.b === b.b;

    function deliver(byte, to = engines()) {
      for (const k of ["a", "b"]) {
        if (to[k]?.on) to[k].midiIn(Uint8Array.of(byte));
      }
    }
    function paint() {
      linkBtn.setAttribute("aria-checked", String(linked));
      linkBtn.title = "Shared host MIDI clock; native Hortator external clock = USB; imported .fwsc external clock = TRS.";
      tempoBox.disabled = !linked;
      playBtn.disabled = !linked || !ready(cached) || starting;
      playBtn.setAttribute("aria-pressed", String(playing));
      playBtn.textContent = playing ? "Stop" : starting ? "Starting…" : "Play";
      // 'Ready' means only that both engines have a MIDI input adapter, NOT
      // that their chosen firmware actually follows external clock.
      state.textContent = !linked ? "Sync off" : !ready(cached) ? "Power on both" :
        playing ? (stats.late > 3 ? "Clock delays detected" : "Clock sent · set ext sync") :
        starting ? "Starting clock…" : "Clock ready · set ext sync";
    }
    function stop() {
      // Invalidate any pending asynchronous start, including Play followed by
      // immediate unlink, firmware change or page backgrounding.
      const old = epoch++;
      starting = false;
      if (playing) {
        playing = false;
        node?.port.postMessage({ type: "stop", epoch: old });
        // Stop both immediately, even with a suspended audio context.
        deliver(0xfc, currentPlayers || engines());
        stats.stops++;
      }
      currentPlayers = null;
      pendingPlayers = null;
      paint();
    }
    function fromClock({ data: message }) {
      if (message.type !== "events" || message.epoch !== epoch || !playing || !linked) return;
      const e = engines();
      if (!same(e, currentPlayers)) { stop(); return; }
      for (const event of message.events) {
        deliver(event.byte, e);
        if (event.byte === 0xf8) {
          stats.pulses++;
          // A valid sample timeline does not mean each MIDI message arrived on
          // time. Track main-thread stalls separately, without claiming zero jitter.
          const lag = Math.max(0, (ctx.currentTime * ctx.sampleRate - event.frame) * 1000 / ctx.sampleRate);
          if (lag > 80) stats.late++;
          stats.maxLagMs = Math.max(stats.maxLagMs, lag);
          stats.frames.push(event.frame);
          stats.arrivals.push(performance.now());
          if (stats.frames.length > 144) stats.frames.shift();
          if (stats.arrivals.length > 144) stats.arrivals.shift();
        } else if (event.byte === 0xfa || event.byte === 0xfb) stats.starts++;
      }
    }
    async function getClock() {
      if (!setup) setup = (async () => {
        const AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) throw Error("AudioContext unavailable");
        ctx = new AC({ latencyHint: "interactive" });
        // Resume within the direct iPad user gesture, before awaiting addModule.
        const resumed = ctx.resume();
        await ctx.audioWorklet.addModule("./duo-clock.js");
        node = new AudioWorkletNode(ctx, "duo-host-clock", {
          numberOfInputs: 0, numberOfOutputs: 1, outputChannelCount: [1]
        });
        const silent = ctx.createGain();
        silent.gain.value = 0;
        node.connect(silent).connect(ctx.destination); // keep the worklet active on Safari
        node.port.onmessage = fromClock;
        await resumed;
        node.port.postMessage({ type: "tempo", bpm });
        return node;
      })().catch((err) => {
        setup = null;
        ctx?.close().catch(() => {});
        ctx = null; node = null;
        throw err;
      });
      return setup;
    }

    function tick() {
      const e = engines();
      // A changed firmware, power-off or suspended clock must STOP, not silently drift.
      if (playing && (!linked || !same(e, currentPlayers) || ctx?.state !== "running")) stop();
      if (starting && (!linked || !same(e, pendingPlayers))) stop();
      cached = e;
      // FM-1+VA retains the existing MIDI follower setting but is never required as source.
      for (const k of ["a", "b"]) {
        let fw;
        try { fw = frames[k].contentWindow.__fw; } catch { continue; }
        if (!fw?.mi) continue;
        const follow = linked && ready(e) && e[k] === fw;
        if (fw.mi.follow !== follow || fw.mi.lead || fw.mi.link || (follow && fw.mi.tempo !== bpm)) {
          fw.mi.follow = follow;
          fw.mi.lead = false; fw.mi.link = null; fw.mi.linkTo = null;
          fw.mi.tempo = follow ? bpm : 0;
          fw.sendGlobal();
        }
      }
      paint();
      const beat = {};
      for (const k of ["a", "b"]) {
        try { beat[k] = frames[k].contentWindow.__fw; } catch { beat[k] = null; }
      }
      for (const k of ["a", "b"]) {
        const tabs = tabsOf(k);
        if (tabs) for (const button of tabs.children) {
          const fw = beat[button.dataset.k];
          button.querySelector(".beat").classList.toggle("on",
            !!(fw && fw.S?.playing && fw.beatPhase() < 0.3));
        }
      }
    }
    linkBtn.addEventListener("click", () => {
      stop(); // cancel start even if the worklet has not loaded yet
      linked = !linked;
      keep("link", linked ? "1" : "0");
      tick();
    });
    tempoBox.addEventListener("change", () => {
      bpm = clamp(tempoBox.value || bpm);
      tempoBox.value = String(bpm);
      keep("bpm", String(bpm));
      node?.port.postMessage({ type: "tempo", bpm });
      tick();
    });
    playBtn.addEventListener("click", async () => {
      if (playing) { stop(); return; }
      if (starting) return;
      tick();
      if (!linked || !ready(cached)) return;
      const selected = cached, attempt = ++epoch;
      starting = true;
      pendingPlayers = selected;
      paint();
      try {
        // Resume on the click, not after async module compilation.
        const resumed = ctx?.state === "suspended" ? ctx.resume() : Promise.resolve();
        const clock = await getClock();
        await resumed;
        if (attempt !== epoch || document.hidden || !linked || !same(selected, engines())) return;
        if (ctx.state !== "running") throw Error("Audio clock suspended");
        currentPlayers = selected;
        pendingPlayers = null;
        playing = true;
        stats.late = 0; stats.maxLagMs = 0;
        stats.frames.length = stats.arrivals.length = 0;
        clock.port.postMessage({ type: "start", bpm, epoch: attempt });
      } catch (err) {
        if (attempt === epoch) {
          stop();
          if (window.__tip) window.__tip(playBtn, "Duo clock unavailable: " + (err?.message || err));
        }
      } finally {
        if (attempt === epoch) { starting = false; pendingPlayers = null; paint(); }
      }
    });
    window.addEventListener("pagehide", stop);
    document.addEventListener("visibilitychange", () => { if (document.hidden) stop(); });
    setInterval(tick, 120); // UI and engine lifecycle only; never generates clock pulses.
    tick();
    return { frames, show, tick,
      get linked() { return linked; }, get playing() { return playing; }, get bpm() { return bpm; },
      get sampleRate() { return ctx?.sampleRate || 0; },
      get stats() { return { ...stats, frames: [...stats.frames], arrivals: [...stats.arrivals] }; }
    };
  };
})();
