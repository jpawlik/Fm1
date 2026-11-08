import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const cat = JSON.parse(readFileSync(join(ROOT, "firmwares/catalogue.json"), "utf8")).firmwares;
const readme = readFileSync(join(ROOT, "README.md"), "utf8");

test("the catalogue preserves each firmware author's source revision and license", () => {
  for (const e of cat.filter((e) => e.id !== "bubba")) {
    assert.ok(e.nom && e.auteur && e.licence, `${e.id}: missing metadata`);
    assert.match(e.depot || "", /^https:\/\/github\.com\//, `${e.id}: missing source`);
    assert.match(e.commit_source || "", /^[0-9a-f]{7,40}$/, `${e.id}: missing source revision`);
  }
});

test("the README credits the upstream fork, emulator and original authors", () => {
  assert.match(readme, /Ninjathune-Human\/Fm1/);
  assert.match(readme, /joakimeriksson\/fm1-emu/);
  assert.match(readme, /sbegueria\/fm1-dub/);
  assert.match(readme, /Baud Girl/);
  assert.match(readme, /not redistributed/i);
  assert.match(readme, /firmwares\/catalogue\.json/);
  assert.match(readme, /GPL-3\.0/);
});
