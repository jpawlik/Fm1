#!/usr/bin/env python3
"""Fetch pinned upstream .fwsc assets for the published FM-1 website.

Only catalogue entries with paquet_a_telecharger are fetched. Each file is
written atomically after an exact byte-count and SHA-256 match. This avoids
committing duplicate ~600KB generated release binaries, without serving the
previously checked-in outdated packages.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

root = Path(__file__).resolve().parent.parent
dest = Path(sys.argv[1]) if len(sys.argv) > 1 else root
cat = json.loads((root / "firmwares/catalogue.json").read_text())["firmwares"]
packages = [f for f in cat if f.get("paquet_a_telecharger")]
for entry in packages:
    out = (dest / entry["fichier"]).resolve()
    if not out.is_relative_to(dest.resolve() / "firmwares"):
        raise SystemExit(f"Invalid package path: {entry['id']}")
    url, sha, size = entry["paquet_en_ligne"], entry["sha256"], entry["taille"]
    if not url.startswith("https://github.com/") or "/releases/download/" not in url:
        raise SystemExit(f"Non-release URL for {entry['id']}")
    if len(sha) != 64 or not all(c in "0123456789abcdef" for c in sha):
        raise SystemExit(f"No verified digest for {entry['id']}")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.is_file() and out.stat().st_size == size and hashlib.sha256(out.read_bytes()).hexdigest() == sha:
        print(f"{entry['id']}: checked {size} bytes")
        continue
    request = Request(url, headers={"User-Agent": "FM1-curated-native-site"})
    with urlopen(request, timeout=60) as response:
        data = response.read(size + 1)
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != size or digest != sha:
        raise SystemExit(f"{entry['id']}: release checksum/size mismatch (got {len(data)}, {digest})")
    with tempfile.NamedTemporaryFile(dir=out.parent, delete=False) as temp:
        temp.write(data)
        tmp = Path(temp.name)
    os.replace(tmp, out)
    print(f"{entry['id']}: pinned {size} bytes sha256={sha[:12]}")
