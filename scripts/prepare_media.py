#!/usr/bin/env python3
"""Create presentation copies; never modify experimental source artifacts.

Requires Pillow, PyMuPDF, and ffmpeg (or imageio-ffmpeg).
Usage: python scripts/prepare_media.py --experiments PATH --paper PATH
"""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image
import pymupdf


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiments", type=Path, required=True)
    parser.add_argument("--paper", type=Path, required=True)
    parser.add_argument("--mobile-selection", type=Path,
                        help="Optional reviewed Mobile P&P selection; defaults to the original locopick_014 example")
    parser.add_argument("--handover-selection", type=Path,
                        default=Path("handover_natural_20261007/selection.json"),
                        help="Reviewed natural Handover selection, relative to the experiment directory")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    selections = {}
    for name, path in [("mobile", args.mobile_selection), ("handover", args.handover_selection)]:
        selected = (json.loads((args.experiments / path).read_text()) if path else {
            "selected_attempt": "locopick_014",
            "relative_case_path": "recovery_chain_slope/attempts/locopick_014",
            "handoff_step": 289,
            "poster_time": 4,
            "presentation_filters": "scale=640:-2",
        })
        report = json.loads((args.experiments / selected["relative_case_path"] / "result.json").read_text())
        if not (report["task_success"] and report["chain_safe"] and report["handoff_completed"]):
            raise ValueError(f"The selected {name} demo must complete the task after safe handoff")
        handoff = next(row["step"] for row in report["rows"] if row["source"] == "nominal_suffix")
        if handoff != selected["handoff_step"]:
            raise ValueError("Selected handoff must be the first committed nominal action")
        selections[name] = selected
    selection = selections["handover"]
    featured_prefix = selection["relative_case_path"]
    featured_report = json.loads((args.experiments / featured_prefix / "result.json").read_text())
    perturbation = featured_report["controlled_perturbation"]
    if (selection.get("failure_source") != "natural" or perturbation["config"] is not None
            or perturbation["executed_changed_steps"]
            or any(row["controlled_perturbation"] for row in featured_report["rows"])):
        raise ValueError("The featured natural missed grasp must have no configured or executed perturbation")
    if not selection.get("visible_failure_before_trigger") or not selection.get("nominal_action_audit_passed"):
        raise ValueError("A natural missed grasp requires visual review and an unmodified nominal-command audit")
    missed_time = (selection["keyframes"]["missed_grasp"] + 1) / 50
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    records = []

    def video(source, name, filters, duration=None, poster_time=1, start=0, speed=1):
        src = args.experiments / source
        dst = root / "assets/videos" / f"{name}.mp4"
        dst.parent.mkdir(parents=True, exist_ok=True)
        command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
        if start:
            command += ["-ss", str(start)]
        if duration:
            command += ["-t", str(duration)]
        command += ["-i", str(src)]
        if speed != 1:
            filters += f",setpts=PTS/{speed}"
        subprocess.run(command + ["-vf", filters + ",fps=25", "-an", "-c:v", "libx264",
                                  "-crf", "23", "-preset", "slow", "-pix_fmt", "yuv420p",
                                  "-movflags", "+faststart", "-threads", "4", str(dst)], check=True)
        poster = root / "assets/images" / f"{name}.webp"
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", str(poster_time),
                        "-i", str(dst), "-frames:v", "1", "-quality", "85", str(poster)], check=True)
        records.append({"output": str(dst.relative_to(root)), "source": source,
                        "source_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
                        "filters": filters, "fps": 25, "playback_speed": f"{speed}x",
                        "audio": "removed; source is a simulation recording",
                        "excerpt_seconds": [start, start + duration] if duration else "complete recording"})
        print(f"Prepared {name}: {dst.stat().st_size / 1048576:.2f} MB", flush=True)

    video(f"{featured_prefix}/result.third_person.mp4", "recovery-overview",
          "crop=1440:900:0:90,eq=gamma=1.18,scale=1120:700", poster_time=missed_time)
    replay = selection["replay"]
    x, y, width, height = replay["observer_crop"]
    video(f"{featured_prefix}/result.third_person.mp4", "handover-grasp-detail",
          f"crop={width}:{height}:{x}:{y},eq=gamma=1.18,scale=832:-2",
          start=replay["start_seconds"], duration=replay["end_seconds"]-replay["start_seconds"],
          speed=replay["playback_speed"],
          poster_time=(missed_time-replay["start_seconds"])/replay["playback_speed"])
    for branch, duration in [("nominal", 9), ("recovery", 15)]:
        video(f"locopick_third_person/{branch}_001/result.third_person.mp4", f"comparison-{branch}",
              "eq=gamma=1.18,scale=800:600", duration=duration, poster_time=8)

    gallery = {}
    for name, attempt, handoff, description in [
        ("handover", selection["selected_attempt"], selection["handoff_step"], "Natural missed grasp · same run as overview"),
        ("mobile", selections["mobile"]["selected_attempt"], selections["mobile"]["handoff_step"], "Controlled grasp perturbation"),
        ("container", "hugcontainer_030", 297, "Controlled grasp perturbation"),
    ]:
        prefix = selections[name]["relative_case_path"] if name in selections else f"recovery_chain_slope/attempts/{attempt}"
        selected = selections.get(name, {})
        filters = selected.get("presentation_filters", "eq=gamma=1.5,scale=640:-2" if name == "mobile" else "scale=640:-2")
        poster_time = selected.get("poster_time", (selected["keyframes"]["missed_grasp"] + 1) / 50 if "keyframes" in selected else 4)
        video(f"{prefix}/result.mp4", name, filters, poster_time=poster_time)
        report = json.loads((args.experiments / prefix / "result.json").read_text())
        gallery[name] = {
            "attempt": attempt, "trigger_step": report["trigger"]["step"],
            "handoff_step": handoff, "end_step": report["executed_steps"] - 1,
            "control_hz": 50, "frame_offset": 1, "task_success": report["task_success"],
            "context": description,
            "samples": [{"step": s["feature_step"], "probability": s["probability"],
                         "phase": s.get("phase")} for s in report["monitor_samples"]],
        }
        gallery[name].update(source_case=prefix, shared_with_overview=name == "handover",
                             failure_source="natural" if name == "handover" else "controlled")
        if name == "handover":
            gallery[name].update(
                                 missed_grasp_step=selection["keyframes"]["missed_grasp"],
                                 recovered_grasp_step=selection["keyframes"]["recovered_grasp"],
                                 natural_action_audit_passed=True,
                                 visible_failure_before_trigger=True,
                                 detail_replay=replay)

    for name, step, source, filters in [
        ("handover-missed", selection["keyframes"]["missed_grasp"], "result.third_person.mp4", f"crop={width}:{height}:{x}:{y},eq=gamma=1.18"),
        ("handover-recovered", selection["keyframes"]["recovered_grasp"], "result.third_person.mp4", f"crop={width}:{height}:{x}:{y},eq=gamma=1.18"),
        ("handover-completed", selection["keyframes"]["completion"], "result.mp4", "scale=640:-2"),
    ]:
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                        "-ss", str((step+1)/50), "-i", str(args.experiments / featured_prefix / source),
                        "-vf", filters, "-frames:v", "1", "-quality", "90",
                        str(root / "assets/images" / f"{name}.webp")], check=True)
        records.append({"output": f"assets/images/{name}.webp", "source": f"{featured_prefix}/{source}",
                        "source_control_step": step, "filters": filters,
                        "source_sha256": hashlib.sha256((args.experiments / featured_prefix / source).read_bytes()).hexdigest()})

    (root / "assets/experiments.json").write_text(json.dumps(gallery, indent=2) + "\n")
    for source, name in [("overview", "method-overview"),
                         ("failure_probability_keyframes", "failure-monitoring"),
                         ("recovery_chain_successes_v2_2", "recovery-chains")]:
        src = args.paper / "figures" / f"{source}.pdf"
        doc = pymupdf.open(src)
        page = doc[0]
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2200 / page.rect.width, 2200 / page.rect.width))
        img = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
        img.save(root / "assets/images" / f"{name}.webp", quality=88)
        shutil.copy2(src, root / "assets/images" / f"{name}.pdf")
        records.append({"output": f"assets/images/{name}.webp", "source": f"paper/figures/{source}.pdf",
                        "processing": "PDF rasterization only; no changes to figure content"})
    (root / "assets/media-manifest.json").write_text(json.dumps({
        "manuscript": "figures/R2C_LfC_2026_v3.tex",
        "notes": ["All videos show simulated Unitree G1 executions.",
                  f"The overview and Handover demo show the same successful run, {featured_prefix}, in simultaneous observer and ego views.",
                  "The Handover miss is natural: no injected perturbation or human takeover; nominal commands and visible pre-trigger failure were audited.",
                  "Handover reaches the original task-success criterion based on target-container contact; this does not require complete hand release or settled placement.",
                  "Mobile Pick & Place and HugContainer remain explicitly labeled controlled grasp perturbations.",
                  f"The close-up replay shows source seconds {replay['start_seconds']}–{replay['end_seconds']} at explicitly labeled {replay['playback_speed']}x speed; full videos retain original timing.",
                  "The older third-person comparison shows grasp-stage excerpts: nominal seconds 0–9 and recovery seconds 0–15, at original speed.",
                  "Comparison runs are independent stochastic executions, not matched-state counterfactuals.",
                  "Task-gallery clips are selected development successes, not a success-rate estimate.",
                  "Uniform gamma adjustment brightens third-person footage. All presentation filters are recorded per asset; no scene content is altered.",
                  "Gallery timestamps use frame(step+1)/50; probabilities are original, unsmoothed monitor samples."],
        "assets": records}, indent=2) + "\n")


if __name__ == "__main__":
    main()
