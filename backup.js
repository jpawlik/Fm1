// SPDX-License-Identifier: GPL-3.0-only
// One portable backup for FM-1+VA, Duo preferences, native firmware flash,
// and Joakim's CPU-emulator saves (including firmware packages).
const FORMAT = "fm1-fork-backup";
const VERSION = 1;
const MAX_JSON = 96 * 1024 * 1024;
const SCHEMAS = {
  "fm1-natif": { version: 1, stores: ["flash"] },
  "fm1-emulator": { version: 2, stores: ["packages", "states", "entries"] },
};
const APP_KEY = /^(fm1\.|fm1b\.|fm1va\.)/;
const BIN = {
  Int8Array, Uint8Array, Uint8ClampedArray, Int16Array, Uint16Array,
  Int32Array, Uint32Array, Float32Array, Float64Array, DataView,
};
if (typeof BigInt64Array !== "undefined") BIN.BigInt64Array = BigInt64Array;
if (typeof BigUint64Array !== "undefined") BIN.BigUint64Array = BigUint64Array;

function base64(bytes) {
  let text = "";
  for (let i = 0; i < bytes.length; i += 8192)
    text += String.fromCharCode(...bytes.subarray(i, i + 8192));
  return btoa(text);
}
function unbase64(text) {
  if (typeof text !== "string" || text.length > MAX_JSON ||
      text.length % 4 || /[^A-Za-z0-9+/=]/.test(text)) throw new Error("Invalid backup binary");
  try { return Uint8Array.from(atob(text), c => c.charCodeAt(0)); }
  catch { throw new Error("Invalid backup binary"); }
}
// Typed nodes prevent ambiguity with ordinary firmware data (including objects
// that happen to contain a field called "type"). They also preserve ArrayBuffer.
function encode(value, depth = 0, seen = new WeakSet()) {
  if (depth > 50) throw new Error("Backup data is nested too deeply");
  if (value === undefined) return ["undefined"];
  if (value === null) return ["null"];
  if (typeof value === "string" || typeof value === "boolean") return [typeof value, value];
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new Error("Unsupported saved number");
    return ["number", value];
  }
  if (typeof value === "bigint") return ["bigint", String(value)];
  if (value instanceof ArrayBuffer) return ["binary", "ArrayBuffer", base64(new Uint8Array(value))];
  if (ArrayBuffer.isView(value)) {
    const name = value.constructor.name;
    if (!Object.hasOwn(BIN, name)) throw new Error("Unsupported saved binary type");
    return ["binary", name, base64(new Uint8Array(value.buffer, value.byteOffset, value.byteLength))];
  }
  if (!value || typeof value !== "object") throw new Error("Unsupported saved data");
  if (seen.has(value)) throw new Error("Saved data contains a cycle");
  seen.add(value);
  let result;
  if (Array.isArray(value)) result = ["array", value.map(v => encode(v, depth + 1, seen))];
  else {
    if (Object.getPrototypeOf(value) !== Object.prototype && Object.getPrototypeOf(value) !== null)
      throw new Error("Unsupported saved object");
    result = ["object", Object.entries(value).map(([k, v]) => [k, encode(v, depth + 1, seen)])];
  }
  seen.delete(value);
  return result;
}
function decode(node, depth = 0) {
  if (depth > 50 || !Array.isArray(node) || typeof node[0] !== "string") throw new Error("Invalid backup value");
  const [tag, v] = node;
  if (tag === "undefined" && node.length === 1) return undefined;
  if (tag === "null" && node.length === 1) return null;
  if (tag === "string" && node.length === 2 && typeof v === "string") return v;
  if (tag === "boolean" && node.length === 2 && typeof v === "boolean") return v;
  if (tag === "number" && node.length === 2 && typeof v === "number" && Number.isFinite(v)) return v;
  if (tag === "bigint" && node.length === 2 && typeof v === "string" && /^-?[0-9]+$/.test(v)) return BigInt(v);
  if (tag === "binary" && node.length === 3 && typeof v === "string") {
    const bytes = unbase64(node[2]);
    if (v === "ArrayBuffer") return bytes.buffer;
    if (!Object.hasOwn(BIN, v)) throw new Error("Unknown backup binary type");
    if (v === "DataView") return new DataView(bytes.buffer);
    const Type = BIN[v];
    if (bytes.byteLength % Type.BYTES_PER_ELEMENT) throw new Error("Invalid binary length");
    return new Type(bytes.buffer);
  }
  if (tag === "array" && node.length === 2 && Array.isArray(v) && v.length < 100000)
    return v.map(n => decode(n, depth + 1));
  if (tag === "object" && node.length === 2 && Array.isArray(v) && v.length < 100000) {
    const result = Object.create(null);
    for (const pair of v) {
      if (!Array.isArray(pair) || pair.length !== 2 || typeof pair[0] !== "string" || Object.hasOwn(result, pair[0]))
        throw new Error("Invalid saved object");
      result[pair[0]] = decode(pair[1], depth + 1);
    }
    return result;
  }
  throw new Error("Unknown backup value");
}
function openDB(name) {
  const schema = SCHEMAS[name];
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(name, schema.version);
    request.onupgradeneeded = () => {
      const db = request.result;
      for (const store of schema.stores) if (!db.objectStoreNames.contains(store)) db.createObjectStore(store);
    };
    request.onerror = () => reject(request.error || new Error("Cannot open " + name));
    request.onblocked = () => reject(new Error("Close other FM-1 tabs to access saved data"));
    request.onsuccess = () => resolve(request.result);
  });
}
function readStore(db, store) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, "readonly"), obj = tx.objectStore(store);
    const keys = obj.getAllKeys(), values = obj.getAll();
    tx.oncomplete = () => resolve(keys.result.map((key, i) => [encode(key), encode(values.result[i])]));
    tx.onerror = tx.onabort = () => reject(tx.error || new Error("Cannot read " + store));
  });
}
function writeDB(db, stores) {
  return new Promise((resolve, reject) => {
    const names = Object.keys(stores), tx = db.transaction(names, "readwrite");
    for (const name of names) {
      const store = tx.objectStore(name);
      store.clear();
      for (const [key, value] of stores[name]) store.put(value, key);
    }
    tx.oncomplete = () => resolve();
    tx.onerror = tx.onabort = () => reject(tx.error || new Error("Cannot restore firmware data"));
  });
}
export async function createBackup() {
  const local = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (APP_KEY.test(key)) local.push([key, localStorage.getItem(key)]);
  }
  local.sort((a, b) => a[0].localeCompare(b[0]));
  const databases = {};
  for (const [name, schema] of Object.entries(SCHEMAS)) {
    const db = await openDB(name);
    try {
      const stores = {};
      for (const store of schema.stores) stores[store] = await readStore(db, store);
      databases[name] = stores;
    } finally { db.close(); }
  }
  const result = { format: FORMAT, version: VERSION, created: new Date().toISOString(), local, databases };
  if (JSON.stringify(result).length > MAX_JSON) throw new Error("Backup too large for a single file");
  return result;
}
function validate(data) {
  if (!data || data.format !== FORMAT || data.version !== VERSION ||
      !Array.isArray(data.local) || !data.databases ||
      Object.keys(data.databases).sort().join(",") !== Object.keys(SCHEMAS).sort().join(","))
    throw new Error("Not a supported FM-1 backup");
  const local = [], seen = new Set();
  if (data.local.length > 10000) throw new Error("Too many saved settings");
  for (const entry of data.local) {
    if (!Array.isArray(entry) || entry.length !== 2 || typeof entry[0] !== "string" ||
        !APP_KEY.test(entry[0]) || typeof entry[1] !== "string" || seen.has(entry[0]))
      throw new Error("Invalid saved setting");
    seen.add(entry[0]); local.push(entry);
  }
  const databases = {};
  for (const [name, schema] of Object.entries(SCHEMAS)) {
    const input = data.databases[name];
    if (!input || Object.keys(input).sort().join(",") !== schema.stores.slice().sort().join(","))
      throw new Error("Missing firmware save section");
    const stores = {};
    for (const store of schema.stores) {
      const records = input[store], keys = new Set();
      if (!Array.isArray(records) || records.length > 10000) throw new Error("Invalid firmware save records");
      stores[store] = records.map(record => {
        if (!Array.isArray(record) || record.length !== 2) throw new Error("Invalid firmware save record");
        const key = decode(record[0]), value = decode(record[1]);
        if (typeof key !== "string" || keys.has(key)) throw new Error("Invalid or duplicate firmware key");
        if (name === "fm1-emulator" && store !== "entries" && !/^[a-f0-9]{64}$/.test(key))
          throw new Error("Invalid emulator firmware hash");
        keys.add(key);
        return [key, value];
      });
    }
    databases[name] = stores;
  }
  return { local, databases };
}
export async function restoreBackup(backup) {
  // Active engines could overwrite restored data while running.
  if (document.getElementById("power")?.getAttribute("aria-checked") === "true")
    throw new Error("Power off the FM-1 before restoring a backup");
  const { local, databases } = validate(backup);  // validate *everything* before touching storage
  // Restore each database as a transaction. Existing entries not in the backup are
  // intentionally removed: this is a full snapshot restore, not a merge.
  for (const name of Object.keys(SCHEMAS)) {
    const db = await openDB(name);
    try { await writeDB(db, databases[name]); }
    finally { db.close(); }
  }
  for (const key of Object.keys(localStorage)) if (APP_KEY.test(key)) localStorage.removeItem(key);
  for (const [key, value] of local) localStorage.setItem(key, value);
}
// A tiny UI in the User Guide (not the panel). Solo mode backs up both Solo
// and Duo because their data lives on the same origin.
const exportButton = document.getElementById("backup-export");
const importInput = document.getElementById("backup-import");
const status = document.getElementById("backup-status");
if (exportButton && importInput && status) {
  exportButton.addEventListener("click", async () => {
    exportButton.disabled = true;
    status.textContent = "Collecting saved data…";
    try {
      const backup = await createBackup();
      const blob = new Blob([JSON.stringify(backup)], { type: "application/json" });
      const href = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = href;
      a.download = "fm1-backup-" + new Date().toISOString().slice(0, 10) + ".json";
      document.body.append(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(href), 60000);
      status.textContent = "Backup ready. Save the file in Files or iCloud Drive.";
    } catch (e) { status.textContent = "Backup failed: " + e.message; }
    finally { exportButton.disabled = false; }
  });
  importInput.addEventListener("change", async () => {
    const file = importInput.files?.[0];
    importInput.value = "";
    if (!file) return;
    if (file.size > MAX_JSON) { status.textContent = "Backup file is too large."; return; }
    try {
      if (document.getElementById("power")?.getAttribute("aria-checked") === "true")
        throw new Error("Power off the FM-1 before restoring");
      const backup = JSON.parse(await file.text());
      validate(backup);
      if (!confirm("Restore this FM-1 backup? This REPLACES all saved presets, patterns, native flash, emulated firmware saves, and settings in this browser. Close other FM-1 tabs first.")) return;
      status.textContent = "Restoring saved data…";
      await restoreBackup(backup);
      status.textContent = "Restore complete. Reloading…";
      location.reload();
    } catch (e) { status.textContent = "Restore failed: " + e.message; }
  });
}
