"""Regression coverage for the special fm1-base native worklet family."""
import subprocess
import sys
from pathlib import Path

from conftest import ROOT
ROOT = Path(ROOT)

ROOT = Path(ROOT)


def test_base_worklet_bundle_follows_nested_imports_and_preserves_parts(tmp_path):
    (tmp_path / "parts").mkdir()
    (tmp_path / "app_own_worklet.js").write_text('globalThis.fm1App = {load() {}};')
    (tmp_path / "parts" / "parts_worklet.js").write_text(
        'const register = globalThis.registerProcessor;\n'
        'globalThis.registerProcessor = (name, Proc) => register(name, name !== "fm1" ? Proc : class extends Proc {});\n'
    )
    (tmp_path / "app_worklet.js").write_text(
        'import "./app_own_worklet.js";\n'
        'import "./parts/parts_worklet.js";\n'
    )
    (tmp_path / "worklet.js").write_text(
        'const Fm1 = class {};\n'
        'registerProcessor("fm1", Fm1);\n'
    )
    subprocess.run([sys.executable, str(ROOT / "tools/worklets/fm1base_bundle.py"), str(tmp_path)],
                   check=True)
    bundle = (tmp_path / "worklet-bundle.js").read_text()
    assert bundle.index("globalThis.fm1App") < bundle.index('registerProcessor("fm1"')
    assert "name.startsWith(\"natif-\")" in bundle
    assert 'import "./' not in bundle
    assert bundle.count("globalThis.fm1App") == 1


def test_base_worklet_bundle_rejects_escaping_imports(tmp_path):
    (tmp_path / "app_worklet.js").write_text('import "../outside.js";')
    (tmp_path / "worklet.js").write_text('registerProcessor("fm1", class {});')
    result = subprocess.run([sys.executable, str(ROOT / "tools/worklets/fm1base_bundle.py"), str(tmp_path)],
                            capture_output=True, text=True)
    assert result.returncode != 0


def test_native_base_protocol_is_wired_to_host():
    s = (ROOT / "index.html").read_text(encoding="utf-8")
    assert 'this.dialect === "base"' in s
    assert 'case "base": return { type: "load", wasm, store: saved || {}, master };' in s
    assert '{ type: "app", part: "midi", data: [s, a, b] }' in s
    assert "this.basePixels" in s


def test_only_pinned_licenced_base_engines_use_the_new_protocol():
    import json
    builds = json.loads((ROOT / "tools/natif.json").read_text())["firmwares"]
    native = {b["id"]: b for b in builds}
    for id_ in ("echofield", "graine"):
        assert native[id_]["dialecte"] == "base"
        assert len(native[id_]["commit"]) == 40
        assert 'fm1base_bundle.py' in native[id_]["construction"]
