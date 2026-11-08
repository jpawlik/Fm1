#!/usr/bin/env python3
"""Flatten an fm1-base AudioWorklet into one module for the FM-1 native host.

fm1-base imports optional parts through generated app_worklet.js. Our native
host loads one worklet URL. Inline those modules in dependency order, in
separate scopes so their module-local bindings cannot collide. Fail closed on
external imports, missing files, unsupported exports, and cycles.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

if len(sys.argv) != 3 or not re.fullmatch(r"natif-[a-z0-9-]+", sys.argv[2]):
    raise SystemExit("Usage: fm1base_bundle.py <emu-dir> natif-<firmware-id>")
root = Path(sys.argv[1]).resolve()
processor_name = sys.argv[2]
module_re = re.compile(r'^\s*import\s+["\'](\./[^"\']+\.js)["\'];?\s*$', re.M)
seen: set[Path] = set()
stack: set[Path] = set()
chunks: list[str] = []


def visit(path: Path) -> None:
    path = path.resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise SystemExit(f"Unsafe or missing worklet dependency: {path}")
    if path in stack:
        raise SystemExit(f"Cyclic worklet dependency: {path}")
    if path in seen:
        return
    stack.add(path)
    source = path.read_text(encoding="utf-8")
    for match in module_re.finditer(source):
        visit(path.parent / match.group(1))
    source = module_re.sub("", source)
    if re.search(r'^\s*(?:import|export)\b', source, re.M):
        raise SystemExit(f"Unsupported worklet module syntax: {path}")
    # A parts module wraps *only its own processor*. The wrapper remains on
    # AudioWorkletGlobalScope after import; matching all natif-* processors
    # breaks later firmware loaded into the same AudioContext.
    if path.name == "parts_worklet.js":
        old = 'name !== "fm1" ? Proc'
        if old not in source:
            raise SystemExit(f"Unrecognized processor wrapper: {path}")
        source = source.replace(
            old, f'name !== "fm1" && name !== "{processor_name}" ? Proc'
        )
    if path == root / "worklet.js":
        # Class methods must hold their own app callbacks instead of reading
        # globalThis.fm1App, which another firmware may replace on import.
        source = "const __fm1ScopedApp = globalThis.fm1App || {};\n" + source.replace(
            "globalThis.fm1App", "__fm1ScopedApp"
        )
    chunks.append(f"// --- {path.relative_to(root)} ---\n{{\n{source}\n}}\n")
    seen.add(path)
    stack.remove(path)


part = root / "app_worklet.js"
if part.exists():
    visit(part)
else:
    # No own app callbacks: do not inherit another firmware's old globals.
    chunks.append("globalThis.fm1App = {};\n")
visit(root / "worklet.js")
destination = root / "worklet-bundle.js"
destination.write_text(
    "// SPDX-License-Identifier: MPL-2.0\n"
    "// Generated from pinned fm1-base worklet and licensed application modules.\n"
    "// Each module retains its upstream copyright header below.\n"
    + "\n".join(chunks),
    encoding="utf-8",
)
print(f"Bundled {len(seen)} fm1-base worklet modules into {destination}")
