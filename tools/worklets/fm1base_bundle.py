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

root = Path(sys.argv[1]).resolve()
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
    # The fm1-base parts wrapper intercepts registerProcessor('fm1') to
    # initialize its data/midi/resample parts. Our packager renames the
    # processor to natif-ID after bundling, so recognize that name as well.
    source = source.replace(
        'name !== "fm1" ? Proc',
        'name !== "fm1" && !name.startsWith("natif-") ? Proc',
    )
    chunks.append(f"// --- {path.relative_to(root)} ---\n{{\n{source}\n}}\n")
    seen.add(path)
    stack.remove(path)


part = root / "app_worklet.js"
if part.exists():
    visit(part)
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
