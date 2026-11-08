# FM-1 — iPad-friendly fork

[**Open the web app**](https://jpawlik.github.io/Fm1/) · [Original project](https://github.com/Ninjathune-Human/Fm1) · [Firmware catalogue](firmwares/catalogue.json)

A small UI-focused fork of **[Ninjathune-Human/Fm1](https://github.com/Ninjathune-Human/Fm1)** for the M-VAVE FM-1. English interface, larger LCD and knobs, and white knob indicators. The original panel controls, touch gestures and sound engines are retained. Duo synchronization is experimental and now uses an independent MIDI host clock.

## Use

1. Open the app, power on, and choose a firmware.
2. Turn knobs by dragging up/right; hold buttons while playing with another finger.
3. On iPad, use **Safari → Share → Add to Home Screen**. Launch from the icon instead of Safari's fullscreen button.
4. Open [Duo mode](https://jpawlik.github.io/Fm1/?duo), enable **Duo sync**, choose a BPM, and press **Play** in the Duo bar. Its host MIDI clock sends Start/Stop and 24 clocks per beat to both instances, with no FM-1+VA requirement. In each firmware select external clock: **USB for built-in native Hortator; TRS for a CPU-emulated `.fwsc`**. Other firmware must support MIDI clock input to follow it. Running two CPU emulators on iPad can crackle.

**Returning to independent playback:** Turning **Duo sync off** stops the host clock but does *not* change the firmware's own clock-source setting. Native Hortator left on **GLOBAL → CLK → USB** (or imported Hortator on **CLK → TRS**) will wait for external pulses, so its panel PLAY may appear stuck. Choose **CLK → INT** on each firmware to use its own Play/Stop and internal tempo again. This also applies when leaving Duo for Solo; clock-source preferences can be saved with the firmware. The app deliberately does not silently overwrite firmware project settings.

Presets and settings are stored in your browser. **Turning the FM-1 off resets the active firmware's saved data.** Before resetting or switching devices, open **Backup and restore** below the panel in Solo mode and export a JSON backup to iPad Files / iCloud Drive. The file includes native and emulated firmware saves plus Duo settings; it can also include imported firmware, samples and ROM data, so keep it private. To restore, power off, close other tabs, import the file, and confirm replacement.

## Curated firmware collection

The main picker includes **23 curated firmware entries**, plus FM-1+VA, in just three categories:

- **Drums & Samplers:** Hortator, Elixir, ECHOFIELD, GRAINE, PIGEON, FOMAJAM.
- **Grooveboxes:** Skiff, MONO2K, MNM-1, JIANT FM, X0X, Chipbox, LOOM-8, Ravel, SLOOP, FIZZ, ORBIT, Loom FM-1.
- **System & Tools:** stock M-VAVE V15, Felucca, Dinghy, fm1-dock, CTL-1.

Sixteen of these have **native WebAssembly builds**; the others use the CPU emulator. The new native archive `natif-curated-v3` contains all 16 builds; previous archives remain available. The latest public non-prerelease versions are pinned to source revisions for existing maintainable firmware; **FIZZ** remains an upstream beta (updated to beta.14), **PIGEON** has no newer stable release, **GRAINE** is pinned to its published 0.2 source snapshot because there is no tagged 0.2 release, and the stock M-VAVE V15 reference stays unchanged. JIANT remains on its verified public release. Updated CPU firmware packages are downloaded from upstream release assets during deployment and SHA-256 verified; no obsolete local packages ship. Browser storage persistence still needs repair; Power Off currently resets saved data.

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
