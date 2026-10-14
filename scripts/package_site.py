#!/usr/bin/env python3
"""Package the static site and an empty setup page for restricted sharing."""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path,
        default=Path(tempfile.gettempdir()) / "phader-share",
    )
    args = parser.parse_args()
    subprocess.run([sys.executable, str(ROOT / "scripts/check_site.py")], check=True)
    files = [ROOT / name for name in ("index.html", "styles.css", "app.js", ".nojekyll")]
    files += sorted(path for path in (ROOT / "assets").rglob("*") if path.is_file())
    if len(files) > 1000 or any(path.stat().st_size > 25 * 1024**2 for path in files):
        raise ValueError("The site exceeds Cloudflare Pages dashboard upload limits")
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    website = output_dir / "phader-private-preview.zip"
    with ZipFile(website, "w", ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT))
    placeholder = output_dir / "setup-placeholder.zip"
    with ZipFile(placeholder, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "index.html",
            '<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="robots" content="noindex"><title>Preview setup</title>'
            '<body><p>Preview access is being configured.</p></body></html>\n',
        )
    print(f"Website: {website} ({website.stat().st_size / 1024**2:.2f} MiB)")
    print(f"Empty setup page: {placeholder}")
    print("Configure Access using the empty setup page before uploading the website ZIP.")


if __name__ == "__main__":
    main()
