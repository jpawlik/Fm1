import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const cat = JSON.parse(readFileSync(join(ROOT, "firmwares/catalogue.json"), "utf8"));

test("the approved 18 firmware entries and their categories are exact", () => {
  const approved = ["hortator", "skiff", "mono2k", "x0x", "pigeon", "chipbox",
    "loom", "ravel", "sloop", "fomajam", "fizz", "orbit", "loomfm1",
    "mvave15", "felucca", "dinghy", "fm1dock", "ctl"];
  assert.equal(cat.firmwares.length, 18);
  assert.deepEqual(new Set(cat.firmwares.map(e => e.id)), new Set(approved));
  assert.equal(cat.defaut, "hortator");
  assert.deepEqual(new Set(cat.firmwares.flatMap(e => e.categories)),
    new Set(["Drums & Samplers", "Grooveboxes", "System & Tools"]));
  for (const e of cat.firmwares) {
    assert.equal(e.categories.length, 1, e.id);
    assert.ok(e.description.length >= 65, e.id);
  }
});

test("chaque paquet local existe et a l'empreinte du catalogue", () => {
  for (const e of cat.firmwares.filter((e) => e.fichier)) {
    const p = join(ROOT, e.fichier);
    assert.ok(existsSync(p), `${e.id} : ${e.fichier} absent`);
    assert.equal(createHash("sha256").update(readFileSync(p)).digest("hex"), e.sha256, e.id);
  }
});

test("une entrée sans paquet local a un paquet en ligne sur le Hub", () => {
  for (const e of cat.firmwares.filter((e) => !e.fichier)) {
    assert.match(e.paquet_en_ligne || "", /^https:\/\/thefirmwarehub\.com\/fw\//, e.id);
  }
});

test("chaque firmware a un état d'émulation mesuré ou déclaré", () => {
  const allowed = new Set(["fonctionne selon fm1-emu", "vérifié", "ne démarre pas"]);
  // un paquet seulement en ligne n'a pas pu être essayé ici : il garde « pas encore évalué »
  for (const e of cat.firmwares) assert.ok(allowed.has(e.emulateur_fm1emu) || (!e.fichier && e.emulateur_fm1emu === "pas encore évalué"), `${e.id} : ${e.emulateur_fm1emu}`);
});

test("native build list matches the approved optimized subset", () => {
  const native = JSON.parse(readFileSync(join(ROOT, "tools/natif.json"), "utf8")).firmwares;
  const allowed = new Set(cat.firmwares.map(e => e.id));
  assert.equal(native.length, 11);
  assert.deepEqual(new Set(native.map(e => e.id)), new Set([
    "chipbox", "ctl", "felucca", "hortator", "loom", "loomfm1",
    "mono2k", "pigeon", "ravel", "skiff", "x0x"
  ]));
  for (const e of native) assert.ok(allowed.has(e.id), e.id);
});
