#!/usr/bin/env python3
"""Export one HTML file with embedded media, fonts, figures, and recorded traces."""

import argparse
import base64
import json
import mimetypes
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BOOTSTRAP = r"""
(() => {
  const element = document.querySelector('#phader-inline-data');
  const payload = JSON.parse(element.textContent);
  element.textContent = '';
  const assets = {};
  for (const [path, resource] of Object.entries(payload.assets)) {
    const binary = atob(resource.base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    assets[path] = URL.createObjectURL(new Blob([bytes], {type: resource.type}));
  }
  window.PhaDeRInline = {assets, experiments: payload.experiments};
  for (const attribute of ['src', 'poster', 'href']) {
    const name = `data-inline-${attribute}`;
    document.querySelectorAll(`[${name}]`).forEach(node => {
      const path = node.getAttribute(name);
      if (!assets[path]) throw new Error(`Missing embedded asset: ${path}`);
      node.setAttribute(attribute, assets[path]);
      node.removeAttribute(name);
    });
  }
  // Source elements were assigned after the browser parsed their parent videos.
  document.querySelectorAll('video').forEach(video => video.load());
})();
"""


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Standalone export needs an updated replacement for: {old}")
    return text.replace(old, new, 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "_site/PhaDeR.html")
    args = parser.parse_args()
    subprocess.run([sys.executable, str(ROOT / "scripts/check_site.py")], check=True)

    page = (ROOT / "index.html").read_text()
    styles = (ROOT / "styles.css").read_text()
    app = (ROOT / "app.js").read_text()
    font_paths = set()

    def inline_css_asset(match):
        path = match.group(1)
        font_paths.add(path)
        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
        encoded = base64.b64encode((ROOT / path).read_bytes()).decode("ascii")
        return f'url("data:{mime};base64,{encoded}")'

    styles = re.sub(r'url\([\"\']?(assets/[^\"\')]+)[\"\']?\)', inline_css_asset, styles)
    page = re.sub(r'<link\b[^>]*\brel="preload"[^>]*>', "", page)
    page = replace_once(page, '<link rel="stylesheet" href="styles.css" />', f"<style>\n{styles}\n</style>")
    page = replace_once(page, '<script src="app.js" defer></script>', "")
    page = re.sub(
        r'<noscript\b.*?</noscript\s*>',
        '<noscript><p class="figure-note">Download this HTML file and open it in a browser '
        'with JavaScript enabled to view its embedded media.</p></noscript>',
        page, flags=re.DOTALL,
    )
    page = re.sub(
        r'\b(src|href|poster)="(assets/[^\"]+)"',
        lambda match: f'data-inline-{match[1]}="{match[2]}"', page,
    )

    # Keep the hosted app unchanged; redirect its three file lookups in this export.
    app = replace_once(app, 'demo.poster = `assets/images/${key}.webp`;',
                       'demo.poster = window.PhaDeRInline.assets[`assets/images/${key}.webp`];')
    app = replace_once(app, 'demo.src = `assets/videos/${key}.mp4`;',
                       'demo.src = window.PhaDeRInline.assets[`assets/videos/${key}.mp4`];')
    app = replace_once(
        app,
        'const response = await fetch("assets/experiments.json");\n'
        '    if (!response.ok) throw new Error("Trace data unavailable");\n'
        '    experiments = await response.json();',
        'experiments = window.PhaDeRInline.experiments;',
    )

    assets = {}
    license_path = "assets/fonts/OFL.txt"
    for path in sorted((ROOT / "assets").rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT).as_posix()
        if relative in font_paths or relative in {license_path, "assets/experiments.json"}:
            continue
        assets[relative] = {
            "type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            "base64": base64.b64encode(path.read_bytes()).decode("ascii"),
        }
    payload = json.dumps({
        "assets": assets,
        "experiments": json.loads((ROOT / "assets/experiments.json").read_text()),
    }, separators=(",", ":")).replace("<", "\\u003c")
    license_text = (ROOT / license_path).read_text()
    scripts = re.sub(r"</script", r"<\\/script", BOOTSTRAP + "\n" + app, flags=re.IGNORECASE)
    embedded = (
        f'<script id="phader-font-license" type="text/plain">\n{license_text}\n</script>\n'
        f'<script id="phader-inline-data" type="application/json">{payload}</script>\n'
        f'<script>\n{scripts}\n</script>\n'
    )
    page = replace_once(page, "</body>", embedded + "</body>")
    output = args.output.resolve()
    if output == ROOT / "index.html":
        raise ValueError("Choose an export path other than the source index.html")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page)
    print(f"Standalone HTML: {output} ({output.stat().st_size / 1024**2:.2f} MiB)")
    print("Send this one file. Download it and open it in a browser; no server is needed.")


if __name__ == "__main__":
    main()
