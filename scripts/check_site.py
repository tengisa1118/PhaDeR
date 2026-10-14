#!/usr/bin/env python3
"""Check public asset references and experiment timing before deployment.

Uses only the Python standard library. Run from any directory.
"""
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.references = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if identifier := attributes.get("id"):
            if identifier in self.ids:
                self.errors.append(f"Duplicate id: {identifier}")
            self.ids.add(identifier)
        for attribute in ("src", "href", "poster"):
            if value := attributes.get(attribute):
                self.references.append(value)
        for attribute in ("aria-controls", "aria-labelledby"):
            self.references.extend(f"#{value}" for value in attributes.get(attribute, "").split())
        if tag == "img" and not attributes.get("alt"):
            self.errors.append("Image is missing descriptive alt text")
        if tag == "video" and "controls" not in attributes:
            self.errors.append("Video is missing native playback controls")


def main():
    page = Page()
    page.feed((ROOT / "index.html").read_text())
    for path in re.findall(r"url\([\"']?([^\"')]+)", (ROOT / "styles.css").read_text()):
        page.references.append(path)
    for reference in page.references:
        url = urlsplit(reference)
        if url.scheme or url.netloc:
            continue
        if url.path and not (ROOT / unquote(url.path)).is_file():
            page.errors.append(f"Missing asset: {url.path}")
        if not url.path and url.fragment and url.fragment not in page.ids:
            page.errors.append(f"Missing anchor: {url.fragment}")
    records = json.loads((ROOT / "assets/experiments.json").read_text())
    for key, record in records.items():
        if not 0 < record["trigger_step"] < record["handoff_step"] < record["end_step"]:
            page.errors.append(f"Invalid event order: {key}")
        samples = record["samples"]
        if not samples or any(not 0 <= s["probability"] <= 1 for s in samples):
            page.errors.append(f"Invalid failure probability samples: {key}")
        steps = [s["step"] for s in samples]
        if steps != sorted(steps) or steps[-1] > record["end_step"]:
            page.errors.append(f"Invalid trace timing: {key}")
        for path in [f"assets/videos/{key}.mp4", f"assets/images/{key}.webp"]:
            if not (ROOT / path).is_file():
                page.errors.append(f"Missing gallery asset: {path}")
    manifest = json.loads((ROOT / "assets/media-manifest.json").read_text())
    assets = {asset["output"]: asset for asset in manifest["assets"]}
    for path in assets:
        if not (ROOT / path).is_file():
            page.errors.append(f"Missing documented asset: {path}")
    featured = [(key, record) for key, record in records.items() if record.get("shared_with_overview")]
    if len(featured) != 1:
        page.errors.append("Exactly one task must share the overview execution")
    for key, record in featured:
        if not record["task_success"]:
            page.errors.append("The overview claims completion but the selected run did not succeed")
        if record.get("failure_source") == "natural" and not (
                record.get("natural_action_audit_passed") and record.get("visible_failure_before_trigger")):
            page.errors.append("Natural failure requires both command audit and visual review")
        for name, source in [("recovery-overview", "result.third_person.mp4"),
                             (key, "result.mp4")]:
            asset = assets[f"assets/videos/{name}.mp4"]
            if asset["source"] != f'{record["source_case"]}/{source}':
                page.errors.append(f"Mismatched featured execution: {name}")
            if asset["excerpt_seconds"] != "complete recording" or asset["playback_speed"] != "1x":
                page.errors.append(f"Full featured view must preserve timing: {name}")
        replay = record["detail_replay"]
        detail = assets[f"assets/videos/{key}-grasp-detail.mp4"]
        if detail["source"] != assets["assets/videos/recovery-overview.mp4"]["source"]:
            page.errors.append("Close-up must come from the overview recording")
        if (detail["excerpt_seconds"] != [replay["start_seconds"], replay["end_seconds"]]
                or detail["playback_speed"] != f'{replay["playback_speed"]}x'):
            page.errors.append("Close-up timing does not match its recorded presentation metadata")
    if page.errors:
        raise SystemExit("\n".join(page.errors))
    video_bytes = sum(p.stat().st_size for p in (ROOT / "assets/videos").glob("*.mp4"))
    print(f"Passed: {len(page.references)} references, {len(records)} recorded traces; "
          f"videos total {video_bytes / 1048576:.2f} MiB.")


if __name__ == "__main__":
    main()
