// SPDX-License-Identifier: MIT
// One AudioWorklet sample timeline for Duo MIDI Clock (24 pulses per quarter note).
// MIDI delivery to firmware still passes through browser MessagePorts; receiver
// audio is not sample-aligned across the iframe AudioContexts.
class DuoHostClock extends AudioWorkletProcessor {
  constructor() {
    super();
    this.bpm = 120;
    this.running = false;
    this.nextPulse = 0;
    this.pending = [];
    this.epoch = 0;
    this.port.onmessage = ({ data: m }) => {
      if (m.type === "start") {
        this.epoch = m.epoch;
        this.bpm = this.clamp(m.bpm || this.bpm);
        this.running = true;
        this.nextPulse = currentFrame;
        this.pending.length = 0; // discard old Stop / Start on rapid restart
        this.pending.push(0xfa);
      } else if (m.type === "continue" && m.epoch === this.epoch) {
        this.running = true;
        this.nextPulse = currentFrame;
        this.pending.push(0xfb);
      } else if (m.type === "stop" && m.epoch === this.epoch) {
        // The host sends MIDI Stop synchronously to each receiver already.
        this.running = false;
        this.pending.length = 0;
      } else if (m.type === "tempo") {
        const old = this.period(), next = this.clamp(m.bpm);
        // Preserve fractional time to the next tick on a tempo change.
        this.nextPulse = currentFrame + Math.max(0, this.nextPulse - currentFrame) * (sampleRate * 60 / (next * 24)) / old;
        this.bpm = next;
      }
    };
  }
  clamp(v) { return Math.max(40, Math.min(240, Math.round(Number(v) || 120))); }
  period() { return sampleRate * 60 / (24 * this.bpm); }
  process(_inputs, outputs) {
    const channel = outputs[0]?.[0];
    if (channel) channel.fill(0);
    const now = currentFrame, end = now + (channel?.length || 128);
    const events = this.pending.splice(0).map((byte) => ({ byte, frame: now }));
    if (this.running) {
      const period = this.period();
      // After a suspended browser context, drop missed clocks rather than bursting them.
      if (this.nextPulse < now - period) this.nextPulse = now;
      while (this.nextPulse < end) {
        events.push({ byte: 0xf8, frame: Math.round(this.nextPulse) });
        this.nextPulse += period;
      }
    }
    if (events.length) this.port.postMessage({ type: "events", epoch: this.epoch, events });
    return true;
  }
}
registerProcessor("duo-host-clock", DuoHostClock);
