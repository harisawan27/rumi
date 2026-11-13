"""Collect the installed distributions' license files alongside the portable app."""
import importlib.metadata
from pathlib import Path
root = Path(__file__).resolve().parent
output = root / "dist/RumiDesktop/THIRD-PARTY-NOTICES.txt"
parts = ["Rumi Desktop dependency notices. Build dependencies are included for transparency.\n"]
for package in sorted(importlib.metadata.distributions(), key=lambda d: d.metadata["Name"].lower()):
    parts.append(f"\n{'=' * 60}\n{package.metadata['Name']} {package.version}\n")
    found = False
    for file in package.files or []:
        if any(word in file.name.lower() for word in ("license", "copying", "notice")):
            source = Path(package.locate_file(file))
            if source.is_file() and source.stat().st_size < 300000:
                parts.append(source.read_text(encoding="utf-8", errors="replace"))
                found = True
    if not found:
        parts.append(package.metadata.get("License-Expression") or package.metadata.get("License") or "See the package's upstream distribution for license details.")
# The static export contains shared chunks. Include notices from the entire
# installed JS dependency tree, including vendored Next packages, conservatively.
modules = root.parent / "frontend/node_modules"
for source in sorted(modules.rglob("*")):
    if source.is_file() and source.name.lower().startswith(("license", "copying", "notice")) and source.stat().st_size < 300000:
        parts.extend([f"\n{source.relative_to(modules)}\n", source.read_text(encoding="utf-8", errors="replace")])
for source in sorted((root / "licenses").glob("*.txt")):
    parts.extend([f"\n{source.name}\n", source.read_text(encoding="utf-8")])
output.write_text("\n".join(parts), encoding="utf-8")
