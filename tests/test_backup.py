"""Portable backup across Solo/Duo localStorage and both firmware IDB stores."""
import json

from conftest import power_on


def run(page, code):
    return page.evaluate(code)


def test_backup_round_trip_all_storage_families(page):
    page.goto(page.base + "index.html")
    output = run(page, """async () => {
      localStorage.setItem("fm1va.bank", '["my patch"]');
      localStorage.setItem("fm1b.fm1va.patterns", '["duo pattern"]');
      localStorage.setItem("fm1.duo.link", "1");
      localStorage.setItem("unrelated", "leave alone");
      const mod = await import("./backup.js");
      // Initialize both IndexedDB schemas before populating synthetic firmware saves.
      await mod.createBackup();
      const native = await new Promise((ok, ko) => {
        const r = indexedDB.open("fm1-natif", 1);
        r.onsuccess = () => ok(r.result); r.onerror = () => ko(r.error);
      });
      await new Promise((ok, ko) => {
        const tx = native.transaction("flash", "readwrite");
        tx.objectStore("flash").put({ 0: new Uint8Array([4, 5, 6]), 4096: new Uint8Array(4096) }, "hortator");
        tx.oncomplete = ok; tx.onerror = () => ko(tx.error);
      });
      native.close();
      const emu = await new Promise((ok, ko) => {
        const r = indexedDB.open("fm1-emulator", 2);
        r.onsuccess = () => ok(r.result); r.onerror = () => ko(r.error);
      });
      const hash = "a".repeat(64);
      await new Promise((ok, ko) => {
        const tx = emu.transaction(["packages","states","entries"],"readwrite");
        tx.objectStore("packages").put(new Uint8Array([0, 1, 2, 3]), hash);
        tx.objectStore("states").put({version:1, revision:4,
          sectors:[{at:0, data:new Uint8Array([1, 2, 3])}]}, hash);
        tx.objectStore("entries").put({hash}, "fm1.hortator");
        tx.oncomplete = ok; tx.onerror = () => ko(tx.error);
      });
      emu.close();
      const backup = await mod.createBackup();
      const data = JSON.parse(JSON.stringify(backup));
      localStorage.setItem("fm1va.bank", '["changed"]');
      localStorage.setItem("fm1va.random", "will be deleted");
      await mod.restoreBackup(data);
      const final = await mod.createBackup();
      const afterNative = final.databases["fm1-natif"].flash.find(([key]) => key[1] === "hortator");
      const afterEmu = final.databases["fm1-emulator"];
      const snap = {
        backup: backup.format, version: backup.version,
        local: localStorage.getItem("fm1va.bank"),
        duo: localStorage.getItem("fm1b.fm1va.patterns"),
        link: localStorage.getItem("fm1.duo.link"),
        removed: localStorage.getItem("fm1va.random"),
        unrelated: localStorage.getItem("unrelated"),
        nativeUnchanged: JSON.stringify(afterNative) === JSON.stringify(backup.databases["fm1-natif"].flash.find(([key]) => key[1] === "hortator")),
        emuUnchanged: JSON.stringify(afterEmu) === JSON.stringify(backup.databases["fm1-emulator"]),
      };
      return snap;
    }""")
    assert output == {
        "backup": "fm1-fork-backup", "version": 1,
        "local": '["my patch"]', "duo": '["duo pattern"]', "link": "1",
        "removed": None, "unrelated": "leave alone",
        "nativeUnchanged": True, "emuUnchanged": True,
    }


def test_invalid_backup_rejected_before_any_data_is_replaced(page):
    page.goto(page.base + "index.html")
    result = run(page, """async () => {
      const mod = await import("./backup.js");
      localStorage.setItem("fm1va.bank", "safe");
      const backup = await mod.createBackup();
      backup.databases["fm1-emulator"].packages = [[["string","bad-key"],["binary","Uint8Array","AA=="]]];
      let rejected = false;
      try { await mod.restoreBackup(backup); } catch (e) { rejected = e.message.includes("hash"); }
      return { rejected, preserved: localStorage.getItem("fm1va.bank") === "safe" };
    }""")
    assert result == {"rejected": True, "preserved": True}


def test_backup_export_button_downloads_json(page):
    page.goto(page.base + "index.html")
    assert page.locator("#aide-backup").count() == 1
    page.locator("#aide-backup summary").click()
    page.evaluate('localStorage.setItem("fm1va.global", "{\\"tempo\\":123}")')
    with page.expect_download() as event:
        page.locator("#backup-export").click()
    download = event.value
    assert download.suggested_filename.startswith("fm1-backup-")
    assert download.suggested_filename.endswith(".json")
    with open(download.path(), encoding="utf-8") as file:
        data = json.load(file)
    assert data["format"] == "fm1-fork-backup"
    assert ["fm1va.global", '{"tempo":123}'] in data["local"]
    assert set(data["databases"]) == {"fm1-natif", "fm1-emulator"}


def test_restore_blocked_when_synth_running(page):
    power_on(page)
    result = run(page, """async () => {
      const mod = await import("./backup.js");
      const b = await mod.createBackup();
      try { await mod.restoreBackup(b); return "incorrectly restored"; }
      catch (e) { return e.message; }
    }""")
    assert "Power off" in result
