# FM-1 — iPad-friendly fork

[**Open the web app**](https://jpawlik.github.io/Fm1/) · [Original project](https://github.com/Ninjathune-Human/Fm1) · [Firmware catalogue](firmwares/catalogue.json)

A small UI-focused fork of **[Ninjathune-Human/Fm1](https://github.com/Ninjathune-Human/Fm1)** for the M-VAVE FM-1. English interface, larger LCD and knobs, and white knob indicators. The original controls, touch gestures, sound engines and Duo synchronization are unchanged.

## Use

1. Open the app, power on, and choose a firmware.
2. Turn knobs by dragging up/right; hold buttons while playing with another finger.
3. On iPad, use **Safari → Share → Add to Home Screen**. Launch from the icon instead of Safari's fullscreen button.
4. Open [Duo mode](https://jpawlik.github.io/Fm1/?duo) to run two instances. **MIDI clock B → A** forwards clock and Start/Stop/Continue from FM1-B (FM-1+VA) to FM1-A (any firmware that supports incoming MIDI clock). Native firmware does not yet transmit clock.

Presets and settings are stored in your browser. **Turning the FM-1 off resets the active firmware's saved data.** Before resetting or switching devices, open **Backup and restore** below the panel in Solo mode and export a JSON backup to iPad Files / iCloud Drive. The file includes native and emulated firmware saves plus Duo settings; it can also include imported firmware, samples and ROM data, so keep it private. To restore, power off, close other tabs, import the file, and confirm replacement.

## Engines

- **FM-1+VA:** independent browser reimplementation based on [Baud Girl's manual](https://baudgirl.com/work/FM-1+VA/manual). Her compiled firmware is **not redistributed** here.
- **CPU emulation:** [Joakim Eriksson's fm1-emu](https://github.com/joakimeriksson/fm1-emu) runs original FM-1 firmware packages.
- **Native browser builds:** some firmware runs as individually compiled WebAssembly instead. See the [catalogue](firmwares/catalogue.json) for firmware authors, exact source revisions and licenses.

## Credits and licenses

This is a modified fork of **[Ninjathune-Human/Fm1](https://github.com/Ninjathune-Human/Fm1)**, © 2026 Ninjathune-Human. The original design, firmware support and Duo feature are credited to that project.

The panel is adapted from [sbegueria's DUB-1 emulator](https://github.com/sbegueria/fm1-dub) (GPL-3.0); `index.html` remains under **GPL-3.0**. Joakim's `fm1-emu` is MIT licensed. The repository is otherwise MIT licensed except for the GPL-3.0 files identified in the [upstream license notes](https://github.com/Ninjathune-Human/Fm1#licences-et-cr%C3%A9dits); bundled fonts use OFL-1.1. Each firmware retains its author's license; see [firmware license texts](firmwares/licences/) and the [catalogue](firmwares/catalogue.json).

Independent community project, not affiliated with M-VAVE.

## Deployment

GitHub Pages deploys automatically from `main` when the website changes. The [Site workflow](.github/workflows/pages.yml) normally reuses versioned emulator and native-firmware builds from GitHub Releases; documentation and test-only changes do not deploy.

Emulator source/patch changes rebuild the runtime only. Changes in `tools/` that affect native firmware rebuild the native versions. To force a build, open **Actions → Site → Run workflow** and select **site**, **runtime**, or **full**. Keep `FM1_EMU_COMMIT` and `RUNTIME_TAG` paired when upgrading Joakim's emulator.
