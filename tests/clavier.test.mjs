// Le modèle du clavier dessiné dans l'aide : les raccourcis, leurs fonctions, les lettres selon la disposition.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import vm from "node:vm";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const html = readFileSync(join(ROOT, "index.html"), "utf8");
const m = html.match(/<script id="fm1-lib">([\s\S]*?)<\/script>/);
const lib = vm.runInNewContext(m[1] + "\n;({ KEYMAP, ENCMAP, keyNoteName, isAzerty, keyLetters, KB_ROWS, keyboardModel })", { Map });

test("noms des notes", () => {
  assert.equal(lib.keyNoteName(0), "F 3");
  assert.equal(lib.keyNoteName(7), "C 4");
  assert.equal(lib.keyNoteName(8), "C♯ 4");
  assert.equal(lib.keyNoteName(24), "F 5");
});

test("AZERTY seulement en français de France et de Belgique", () => {
  for (const l of ["fr", "fr-FR", "fr-fr", "fr-BE"]) assert.ok(lib.isAzerty(l), l);
  for (const l of ["fr-CA", "fr-CH", "en-US", ""]) assert.ok(!lib.isAzerty(l), l);
});

test("lettres", () => {
  const fr = lib.keyLetters("fr-FR", null), en = lib.keyLetters("en-US", null);
  assert.deepEqual(["KeyA", "KeyQ", "KeyW", "KeyZ", "Semicolon", "Comma", "Period", "Digit1"].map(fr), ["Q", "A", "Z", "W", "M", ";", ":", "1"]);
  assert.deepEqual(["KeyA", "Semicolon", "Quote", "Comma", "Digit0"].map(en), ["A", ";", "'", ",", "0"]);
  assert.equal(lib.keyLetters("en-US", new Map([["KeyA", "q"], ["Digit1", "&"]]))("KeyA"), "Q");     // la carte du navigateur d'abord
  assert.equal(lib.keyLetters("en-US", new Map([["Digit1", "&"]]))("Digit1"), "1");                 // les chiffres restent des chiffres
  assert.deepEqual(["Escape", "Enter", "Space", "ArrowLeft"].map(fr), ["Esc", "Enter", "Space", "←"]);
});

test("le modèle dessine chaque raccourci, une fois, avec sa fonction", () => {
  const mo = lib.keyboardModel(lib.keyLetters("en-US", null));
  const by = Object.fromEntries(mo.keys.map((k) => [k.code, k]));
  assert.equal(mo.keys.length, new Set(mo.keys.map((k) => k.code)).size);
  for (const c of [...Object.keys(lib.KEYMAP), ...Object.keys(lib.ENCMAP)]) assert.ok(by[c] && by[c].family, c);
  assert.deepEqual([by.KeyA.family, by.KeyA.label], ["note", "C 4"]);
  assert.deepEqual([by.KeyW.label, by.Quote.label], ["C♯ 4", "F 5"]);
  assert.deepEqual([by.Digit1.family, by.Digit1.label, by.Digit0.label], ["bouton", "FX", "SEQ"]);
  assert.deepEqual([by.KeyZ.label, by.Space.label, by.Enter.label, by.Escape.label], ["OCT−", "PLAY", "SEL", "HOME"]);
  assert.deepEqual([by.Comma.family, by.Comma.label, by.ArrowUp.label], ["molette", "ALGORITHM −", "PRESETS +"]);
  assert.deepEqual([by.KeyQ.family, by.KeyQ.label], [null, ""]);
  for (const k of mo.keys) assert.ok(k.w > 0 && k.x >= 0 && k.x + k.w <= mo.width && k.y >= 0 && k.y < mo.height, k.code);
});
