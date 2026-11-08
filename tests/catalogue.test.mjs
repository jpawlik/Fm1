import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const cat = JSON.parse(readFileSync(join(ROOT, "firmwares/catalogue.json"), "utf8"));

test("the curated 23 firmware entries and their categories are exact", () => {
  const approved = ["hortator", "elixir", "echofield", "graine", "skiff", "mono2k", "mnm1", "jiant", "x0x", "pigeon", "chipbox",
    "loom", "ravel", "sloop", "fomajam", "fizz", "orbit", "loomfm1",
    "mvave15", "felucca", "dinghy", "fm1dock", "ctl"];
  assert.equal(cat.firmwares.length, 23);
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

test("each native-only entry has a pinned native build and any external package has an approved origin", () => {
  const nativeIds = new Set(JSON.parse(readFileSync(join(ROOT, "tools/natif.json"), "utf8")).firmwares.map(e => e.id));
  for (const e of cat.firmwares.filter((e) => !e.fichier)) {
    if (e.natif_seulement) assert.ok(nativeIds.has(e.id), e.id);
    else assert.ok(e.paquet_en_ligne, e.id);
    if (e.paquet_en_ligne) assert.match(e.paquet_en_ligne,
      /^https:\/\/(?:thefirmwarehub\.com\/fw\/|github\.com\/[\w.-]+\/[\w.-]+\/releases\/download\/)/, e.id);
  }
});

test("chaque firmware a un état d'émulation mesuré ou déclaré", () => {
  const allowed = new Set(["fonctionne selon fm1-emu", "vérifié", "ne démarre pas"]);
  // un paquet seulement en ligne n'a pas pu être essayé ici : il garde « pas encore évalué »
  for (const e of cat.firmwares) assert.ok(allowed.has(e.emulateur_fm1emu) || ((!e.fichier || e.paquet_a_telecharger) && e.emulateur_fm1emu === "pas encore évalué"), `${e.id} : ${e.emulateur_fm1emu}`);
});

test("native build list matches the approved optimized subset", () => {
  const native = JSON.parse(readFileSync(join(ROOT, "tools/natif.json"), "utf8")).firmwares;
  const allowed = new Set(cat.firmwares.map(e => e.id));
  assert.equal(native.length, 16);
  assert.deepEqual(new Set(native.map(e => e.id)), new Set([
    "chipbox", "ctl", "echofield", "elixir", "graine", "felucca", "hortator", "jiant", "loom", "loomfm1", "mnm1",
    "mono2k", "pigeon", "ravel", "skiff", "x0x"
  ]));
  for (const e of native) assert.ok(allowed.has(e.id), e.id);
});

test("four approved upstream upgrades are pinned to stable/public release source", () => {
  const upgrades = new Map([
    ["mnm1", ["1.0.1", "2c7aee4c277bb642404c4638dbc77a360d36cf55"]],
    ["elixir", ["0.25.2", "088b055c507ad4dd83a90fb7e648c211d58148da"]],
    ["jiant", ["V10.6z2", "cac23c6d0bb9a7f6986eb79bbe42ae710805ce98"]],
    ["ravel", ["1.27.0", "407276ca17e8b2941967d21981542f4001f9d32a"]],
  ]);
  const native = JSON.parse(readFileSync(join(ROOT, "tools/natif.json"), "utf8")).firmwares;
  for (const [id, [version, commit]] of upgrades) {
    const entry = cat.firmwares.find(e => e.id === id), build = native.find(e => e.id === id);
    assert.ok(entry && build, id);
    assert.equal(entry.version, version, id);
    assert.equal(entry.commit_source, commit, id);
    assert.equal(build.commit, commit, id);
    assert.equal(entry.natif_seulement, true, id);
  }
});

test("stable refresh and special upstream channels are explicit", () => {
 const byId = Object.fromEntries(cat.firmwares.map(e => [e.id,e]));
 for (const [id,version] of Object.entries({
  hortator:"1.0.1", skiff:"2.2", mono2k:"1.9", x0x:"1.2.1", chipbox:"1.5.1",
  loom:"0.14", felucca:"1.7.0", ctl:"1.0.3", sloop:"2.8.5",
  fomajam:"0.1.10", orbit:"1.0.0", dinghy:"0.5", fm1dock:"0.8",
  echofield:"0.2.10", graine:"0.2 (source snapshot)", fizz:"0.12.0-beta.14"
 })) assert.equal(byId[id]?.version,version,id);
 assert.equal(byId.graine.beta,true);
 assert.equal(byId.fizz.beta,true);
 assert.equal(byId.pigeon.version,"0.5.0-beta.1");
 for(const f of cat.firmwares.filter(e=>e.paquet_a_telecharger)){
  assert.match(f.paquet_en_ligne,/^https:\/\/github\.com\//);
  assert.match(f.sha256,/^[a-f0-9]{64}$/);
  assert.ok(f.taille>300000);
 }
});
