from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+\.svg)\)")


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "docs").resolve()
    errors: list[str] = []
    svg_files = list(root.rglob("*.svg"))
    for svg in svg_files:
        try:
            ET.parse(svg)
        except ET.ParseError as exc:
            errors.append(f"invalid SVG XML: {svg}: {exc}")
            continue
        source = svg.read_text(encoding="utf-8")
        lowered = source.lower()
        if "<script" in lowered or "<foreignobject" in lowered:
            errors.append(f"unsafe active SVG content: {svg}")
        if re.search(r"<(?:image|use)\b[^>]*(?:href|xlink:href)=[\"']https?://", source, re.I):
            errors.append(f"external SVG asset reference: {svg}")
        if re.search(r"(?:file:///|[A-Za-z]:\\\\)", source):
            errors.append(f"local absolute path embedded in SVG: {svg}")

    for markdown in root.rglob("*.md"):
        text = markdown.read_text(encoding="utf-8")
        for match in IMAGE_RE.finditer(text):
            raw = match.group(1).strip().strip("<>")
            if "://" in raw:
                continue
            target = (markdown.parent / raw).resolve()
            if not target.is_file():
                errors.append(f"missing SVG link: {markdown} -> {raw}")

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"OK: {len(svg_files)} SVG files parsed; relative Markdown SVG links resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
