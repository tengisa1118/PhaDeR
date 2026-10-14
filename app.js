"use strict";

// Static, dependency-free interactions. All times are from the recorded logs.
const taskInfo = {
  mobile: {
    title: "Recover the grasp. Finish the delivery.",
    context: "Controlled grasp perturbation",
    description:
      "After a perturbed grasp, the recovery adapter reacquires the box. The frozen nominal policy then carries it to the second table and completes the task.",
    label: "Selected Mobile Pick and Place recovery execution",
    trigger_step: 144,
    handoff_step: 289,
    end_step: 790,
  },
  handover: {
    title: "Retry the acquisition. Complete the handover.",
    context: "Natural missed grasp · same run as overview",
    description:
      "The same execution as the overview, from the robot’s view. The initial grasp loses contact. The recovery adapter retries, secures and lifts the box, then the frozen nominal policy resumes and completes the handover.",
    label:
      "First-person view of the overview Handover execution: natural missed grasp, learned regrasp, and nominal continuation",
    trigger_step: 144,
    handoff_step: 644,
    end_step: 821,
  },
  container: {
    title: "Recover the object. Continue the sequence.",
    context: "Controlled grasp perturbation",
    description:
      "The left-hand acquisition is perturbed while the right hand already holds an object. Recovery restores the grasp, and the frozen nominal policy completes the remaining task.",
    label: "Selected Pick and Place and HugContainer recovery execution",
    trigger_step: 169,
    handoff_step: 297,
    end_step: 576,
  },
};

const demo = document.querySelector("#demo-video");
const tabs = [...document.querySelectorAll("[data-task]")];
const rate = document.querySelector("#demo-speed");
let currentTask = "handover";
let experiments = {};
let chartCursor;
const timeForStep = (step) => (step + 1) / 50;

function currentExperiment() {
  return { ...taskInfo[currentTask], ...experiments[currentTask] };
}

function updateEvents() {
  const record = currentExperiment();
  for (const event of ["trigger", "handoff", "end"]) {
    const label = document.querySelector(`[data-event-time="${event}"]`);
    label.textContent = `${timeForStep(record[`${event}_step`]).toFixed(2)}s`;
  }
}

function selectTask(key) {
  if (key === currentTask) return;
  const wasPlaying = !demo.paused;
  demo.pause();
  currentTask = key;
  const info = taskInfo[key];
  tabs.forEach((tab) => {
    const selected = tab.dataset.task === key;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
  });
  document
    .querySelector("#task-panel")
    .setAttribute("aria-labelledby", `tab-${key}`);
  document.querySelector("#task-title").textContent = info.title;
  document.querySelector("#task-description").textContent = info.description;
  document.querySelector("#task-context").textContent =
    info.context.toUpperCase();
  demo.poster = `assets/images/${key}.webp`;
  demo.src = `assets/videos/${key}.mp4`;
  demo.setAttribute("aria-label", info.label);
  demo.load();
  demo.playbackRate = Number(rate.value);
  updateEvents();
  drawTrace();
  updatePlayback();
  if (wasPlaying) demo.play().catch(() => {});
}

tabs.forEach((tab, index) => {
  tab.addEventListener("click", () => selectTask(tab.dataset.task));
  tab.addEventListener("keydown", (event) => {
    let next;
    if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
    if (event.key === "ArrowLeft")
      next = (index - 1 + tabs.length) % tabs.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = tabs.length - 1;
    if (next === undefined) return;
    event.preventDefault();
    tabs[next].focus();
    selectTask(tabs[next].dataset.task);
  });
});

rate.addEventListener("change", () => {
  demo.playbackRate = Number(rate.value);
});
demo.addEventListener("loadedmetadata", () => {
  demo.playbackRate = Number(rate.value);
});
document.querySelectorAll("[data-event]").forEach((button) => {
  button.addEventListener("click", () => {
    const key = currentTask;
    const target = timeForStep(
      currentExperiment()[`${button.dataset.event}_step`],
    );
    const seek = () => {
      if (currentTask !== key) return;
      demo.currentTime = Math.min(target, Math.max(0, demo.duration - 0.001));
      updatePlayback();
    };
    if (demo.readyState >= 1) seek();
    else demo.addEventListener("loadedmetadata", seek, { once: true });
    demo.play().catch(() => {});
  });
});

function drawTrace() {
  const record = currentExperiment();
  const panel = document.querySelector("#trace-panel");
  const svg = document.querySelector("#failure-trace");
  chartCursor = undefined;
  if (!record.samples?.length) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  const x = (step) => 34 + (step / record.end_step) * 667;
  const y = (probability) => 112 - probability * 94;
  let markup = "";
  for (const probability of [0, 0.5, 1]) {
    markup += `<line class="trace-grid" x1="34" y1="${y(probability)}" x2="701" y2="${y(probability)}"/>`;
    markup += `<text class="trace-axis-label" x="20" y="${y(probability) + 4}" text-anchor="end">${probability.toFixed(1)}</text>`;
  }
  markup += `<rect x="${x(record.trigger_step)}" y="18" width="${x(record.handoff_step) - x(record.trigger_step)}" height="94" fill="#e5ddcb" opacity="0.5"/>`;
  for (const [step, label, className] of [
    [record.trigger_step, "Trigger", ""],
    [record.handoff_step, "Handoff", "trace-handoff"],
  ]) {
    markup += `<line class="trace-marker ${className}" x1="${x(step)}" x2="${x(step)}" y1="18" y2="112"/>`;
    markup += `<text class="trace-axis-label" x="${x(step)}" y="10" text-anchor="middle">${label}</text>`;
  }
  for (let fraction = 0; fraction <= 1; fraction += 0.25) {
    const step = record.end_step * fraction;
    markup += `<text class="trace-axis-label" x="${x(step)}" y="135" text-anchor="middle">${(step / 50).toFixed(1)}s</text>`;
  }
  // No smoothing or interpolation beyond connecting successive logged samples.
  const path = record.samples
    .map(
      (sample, index) =>
        `${index ? "L" : "M"}${x(sample.step).toFixed(2)},${y(sample.probability).toFixed(2)}`,
    )
    .join(" ");
  markup += `<path class="trace-line" d="${path}"/><line id="trace-cursor" class="trace-cursor" x1="34" x2="34" y1="18" y2="112"/>`;
  svg.innerHTML = markup;
  chartCursor = svg.querySelector("#trace-cursor");
}

function updatePlayback() {
  const record = currentExperiment();
  const step = Math.max(0, demo.currentTime * 50 - 1);
  const recovery = step >= record.trigger_step && step < record.handoff_step;
  const mode = recovery
    ? "RECOVERY ADAPTER ACTIVE"
    : step >= record.handoff_step
      ? "NOMINAL POLICY RESUMED"
      : "NOMINAL EXECUTION";
  document.querySelector("#demo-mode").textContent = mode;
  document.querySelector(".demo-video-label").dataset.mode = recovery
    ? "recovery"
    : "nominal";
  if (chartCursor) {
    const x = 34 + Math.min(step / record.end_step, 1) * 667;
    chartCursor.setAttribute("x1", x);
    chartCursor.setAttribute("x2", x);
    let sample;
    for (const candidate of record.samples) {
      if (candidate.step <= step) sample = candidate;
      else break;
    }
    document.querySelector("#trace-reading").textContent = sample
      ? `${sample.probability.toFixed(3)} · predicted phase: ${sample.phase ?? "unknown"}`
      : "Monitor warm-up";
  }
}
demo.addEventListener("timeupdate", updatePlayback);
demo.addEventListener("seeked", updatePlayback);
updateEvents();

// Fetch the small, auditable trace file when the gallery approaches the viewport.
let tracesRequested = false;
async function loadTraces() {
  if (tracesRequested) return;
  tracesRequested = true;
  try {
    const response = await fetch("assets/experiments.json");
    if (!response.ok) throw new Error("Trace data unavailable");
    experiments = await response.json();
    updateEvents();
    drawTrace();
    updatePlayback();
  } catch {
    // Native video controls and logged event timings remain usable offline.
    document.querySelector("#trace-panel").hidden = true;
  }
}
if ("IntersectionObserver" in window) {
  const traceObserver = new IntersectionObserver(
    (entries, observer) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        loadTraces();
        observer.disconnect();
      }
    },
    { rootMargin: "300px" },
  );
  traceObserver.observe(document.querySelector(".demo-gallery"));
} else loadTraces();

const hero = document.querySelector("#hero-video");
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
let heroStarted = false;
let heroInteracted = false;
hero.addEventListener("pointerdown", () => {
  heroInteracted = true;
});
hero.addEventListener("keydown", () => {
  heroInteracted = true;
});
hero.addEventListener("timeupdate", () => {
  const record = experiments.handover ?? taskInfo.handover;
  const stage =
    hero.currentTime < timeForStep(record.trigger_step)
      ? 0
      : hero.currentTime < timeForStep(record.handoff_step)
        ? 1
        : 2;
  document.querySelectorAll("[data-hero-stage]").forEach((item) => {
    item.classList.toggle(
      "is-active",
      Number(item.dataset.heroStage) === stage,
    );
  });
});
if ("IntersectionObserver" in window) {
  const observer = new IntersectionObserver(
    (entries) => {
      const visible = entries[0].isIntersecting;
      if (!visible) {
        hero.pause();
        return;
      }
      if (
        !heroStarted &&
        !heroInteracted &&
        !reducedMotion.matches &&
        !navigator.connection?.saveData
      ) {
        heroStarted = true;
        hero.play().catch(() => {});
      }
    },
    { threshold: 0.3 },
  );
  observer.observe(hero);
}
reducedMotion.addEventListener("change", () => {
  if (reducedMotion.matches) hero.pause();
});

const graspReplay = document.querySelector("#grasp-detail-video");
document
  .querySelector(".grasp-disclosure")
  .addEventListener("toggle", (event) => {
    if (!event.currentTarget.open) graspReplay.pause();
  });
// Slow motion is encoded in this clip; keep its native playback rate at 1.
graspReplay.addEventListener("play", () => hero.pause());

const comparisons = [...document.querySelectorAll(".comparison-grid video")];
const comparisonButton = document.querySelector("#play-comparison");
comparisonButton.addEventListener("click", async () => {
  if (comparisons.some((video) => !video.paused)) {
    comparisons.forEach((video) => video.pause());
    return;
  }
  comparisons.forEach((video) => {
    video.currentTime = 0;
    video.playbackRate = 1;
  });
  const results = await Promise.allSettled(
    comparisons.map((video) => video.play()),
  );
  if (results.some((result) => result.status === "rejected")) {
    comparisons.forEach((video) => video.pause());
    comparisonButton.textContent = "Use each video’s play control";
  }
});
function updateComparisonButton() {
  comparisonButton.textContent = comparisons.some((video) => !video.paused)
    ? "Pause both Ⅱ"
    : "Play both from start ↻";
}
comparisons.forEach((video) => {
  video.addEventListener("play", updateComparisonButton);
  video.addEventListener("pause", updateComparisonButton);
  video.addEventListener("ended", updateComparisonButton);
});
document
  .querySelector(".comparison-disclosure")
  .addEventListener("toggle", (event) => {
    if (!event.currentTarget.open)
      comparisons.forEach((video) => video.pause());
  });
document.addEventListener("visibilitychange", () => {
  if (document.hidden)
    document.querySelectorAll("video").forEach((video) => video.pause());
});

// Highlight the chapter currently passing through the reading area.
if ("IntersectionObserver" in window) {
  const sectionObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        document.querySelectorAll(".contents nav a").forEach((link) => {
          const active = link.hash === `#${entry.target.id}`;
          link.classList.toggle("is-current", active);
          if (active) link.setAttribute("aria-current", "location");
          else link.removeAttribute("aria-current");
        });
      });
    },
    { rootMargin: "-5% 0px -65% 0px", threshold: 0 },
  );
  document
    .querySelectorAll(".chapter")
    .forEach((section) => sectionObserver.observe(section));
}

// Reveal cited entries when following an inline citation or a direct link.
const references = document.querySelector("#references");
function revealReference(hash) {
  const entry = document.getElementById(hash.slice(1));
  if (!entry?.matches(".reference-list > li")) return;
  references.open = true;
  requestAnimationFrame(() => {
    entry.scrollIntoView({ block: "center" });
    entry.focus({ preventScroll: true });
  });
}
document.querySelectorAll(".reference-link").forEach((link) => {
  link.addEventListener("click", () => revealReference(link.hash));
});
window.addEventListener("hashchange", () => revealReference(location.hash));
revealReference(location.hash);

document.querySelector("#copy-citation").addEventListener("click", async () => {
  const code = document.querySelector("#bibtex");
  const status = document.querySelector("#copy-status");
  try {
    if (!navigator.clipboard) throw new Error("Clipboard unavailable");
    await navigator.clipboard.writeText(code.textContent.trim());
    status.textContent = "BibTeX copied to clipboard.";
  } catch {
    const range = document.createRange();
    range.selectNodeContents(code);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    status.textContent = "Citation selected. Press Ctrl+C or ⌘C to copy.";
  }
});
