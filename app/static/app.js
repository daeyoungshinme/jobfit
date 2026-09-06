"use strict";

// Feature inits are independent; each bails out quietly if its DOM hooks are
// absent, so this one file can serve every page.
document.addEventListener("DOMContentLoaded", () => {
  initToast();
  initThemeToggle();
  initTabs();
  initAutoSubmit();
  initConfirmForms();
  initSourceSiteGuess();
  initSkillPreview();
  initOcr();
  initRawTextCounter();
  initGapChips();
  initCopyButtons();
});

// --- shared helpers -------------------------------------------------------

const MSG = {
  analyzing: "분석 중...",
  // constants.py의 EMPTY_REQUIRED_SKILLS / EMPTY_PREFERRED_SKILLS와 동일하게 유지.
  noRequiredSkills: "인식된 필수 스킬 없음",
  noPreferredSkills: "인식된 우대 스킬 없음",
  ocrOne: "인식 중...",
  ocrBatch: (i, n) => `이미지 ${i}/${n} 처리 중...`,
  ocrDoneOne: "텍스트 추출 완료",
  ocrDoneBatch: (n) => `${n}개 이미지 텍스트 추출 완료`,
  requestFailed: "요청을 처리하지 못했습니다. 잠시 후 다시 시도해주세요.",
};

// Fade `el` out after `delay` ms, then remove it (300ms matches the .toast
// opacity transition in style.css). Shared by the server flash and showError.
function fadeOutAndRemove(el, delay) {
  setTimeout(() => {
    el.style.opacity = "0";
    setTimeout(() => el.remove(), 300);
  }, delay);
}

// Transient client-side error banner (server-rendered flashes use the same
// .toast markup from base.html).
function showError(text) {
  const el = document.createElement("div");
  el.className = "toast toast-error";
  el.setAttribute("role", "alert");
  el.textContent = text;
  const main = document.getElementById("main-content") || document.body;
  main.prepend(el);
  fadeOutAndRemove(el, 4000);
}

async function postForm(url, params) {
  const res = await fetch(url, { method: "POST", body: new URLSearchParams(params) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || MSG.requestFailed);
  return data;
}

// --- features -----------------------------------------------------------

function initToast() {
  const toast = document.getElementById("toast");
  if (!toast) return;
  const url = new URL(window.location.href);
  url.searchParams.delete("msg");
  window.history.replaceState({}, "", url);
  fadeOutAndRemove(toast, 3000);
}

function initThemeToggle() {
  const themeToggle = document.getElementById("theme-toggle");
  if (!themeToggle) return;
  const setIcon = () => {
    themeToggle.textContent =
      document.documentElement.getAttribute("data-theme") === "dark" ? "☀️" : "🌙";
  };
  setIcon();
  themeToggle.addEventListener("click", () => {
    const next =
      document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
    setIcon();
  });
}

function initTabs() {
  const tabButtons = document.querySelectorAll(".tab-btn[data-tab]");
  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabButtons.forEach((b) => {
        b.classList.remove("active");
        b.setAttribute("aria-selected", "false");
      });
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      btn.setAttribute("aria-selected", "true");
      document.getElementById(btn.dataset.tab).classList.add("active");
    });
  });
}

// Progressive enhancement for filter/status <select>s: submit on change so the
// paired submit button (kept in the markup for no-JS use) isn't needed.
function initAutoSubmit() {
  document.querySelectorAll("[data-autosubmit]").forEach((el) => {
    el.addEventListener("change", () => el.form && el.form.submit());
  });
}

function initConfirmForms() {
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });
}

function initSourceSiteGuess() {
  const urlEl = document.getElementById("url");
  const sourceSiteEl = document.getElementById("source_site");
  if (!urlEl || !sourceSiteEl) return;

  let sourceSiteTouched = false;
  sourceSiteEl.addEventListener("input", () => { sourceSiteTouched = true; });
  sourceSiteEl.addEventListener("change", () => { sourceSiteTouched = true; });

  const guessSource = async () => {
    if (sourceSiteTouched || !urlEl.value.trim()) return;
    try {
      const data = await postForm("/jobs/guess-source", { url: urlEl.value });
      if (!data.source_site) return;
      sourceSiteEl.value = data.source_site;
      sourceSiteEl.classList.add("field-flash");
      setTimeout(() => sourceSiteEl.classList.remove("field-flash"), 700);
    } catch (e) {
      // A failed source guess is a convenience miss, not worth interrupting the
      // user — they can still type the site in by hand.
    }
  };

  urlEl.addEventListener("change", guessSource);
  urlEl.addEventListener("blur", guessSource);
}

function initSkillPreview() {
  const previewBtn = document.getElementById("preview-btn");
  const rawTextEl = document.getElementById("raw_text");
  if (!previewBtn || !rawTextEl) return;

  // Fields the user has typed/selected into by hand are never overwritten by an
  // auto-guess, even if they later clear them back out.
  const autoFillIds = ["title", "company", "address", "position", "experience_level"];
  const touched = new Set();
  autoFillIds.forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener("input", () => touched.add(id));
    el.addEventListener("change", () => touched.add(id));
  });

  const previewBtnDefaultText = previewBtn.textContent;

  const runPreview = async () => {
    const rawText = rawTextEl.value;
    if (!rawText.trim() || previewBtn.disabled) return;
    previewBtn.disabled = true;
    previewBtn.textContent = MSG.analyzing;
    try {
      const data = await postForm("/jobs/preview", { raw_text: rawText });
      const required = data.required_skills || [];
      const preferred = data.preferred_skills || [];
      document.getElementById("preview-required").textContent =
        required.length ? required.join(", ") : MSG.noRequiredSkills;
      document.getElementById("preview-preferred").textContent =
        preferred.length ? preferred.join(", ") : MSG.noPreferredSkills;
      document.getElementById("preview-result").style.display = "block";

      autoFillIds.forEach((id) => {
        if (touched.has(id)) return;
        const value = data[id];
        if (!value) return;
        const el = document.getElementById(id);
        if (!el) return;
        if (el.tagName === "SELECT" && !Array.from(el.options).some((o) => o.value === value)) {
          // e.g. an experience range like "3년 이상" that isn't a preset option
          // — add it so the guess isn't silently dropped.
          el.add(new Option(value, value, true, true));
        }
        el.value = value;
      });
    } catch (e) {
      showError(e.message || MSG.requestFailed);
    } finally {
      previewBtn.disabled = false;
      previewBtn.textContent = previewBtnDefaultText;
    }
  };

  previewBtn.addEventListener("click", runPreview);
  // Exposed so OCR can re-run the preview after it appends extracted text.
  window.__jobfitRunPreview = runPreview;

  // Paste-and-go: auto-fill as soon as the posting text lands, no extra click.
  rawTextEl.addEventListener("paste", (event) => {
    const items = event.clipboardData ? Array.from(event.clipboardData.items) : [];
    const imageFiles = items
      .filter((item) => item.type.startsWith("image/"))
      .map((item) => item.getAsFile())
      .filter(Boolean);
    if (imageFiles.length) {
      // A pasted screenshot has no text payload to fall through to, so route it
      // to OCR instead of letting the browser paste it as an object/blob.
      event.preventDefault();
      runOcrFiles(imageFiles);
      return;
    }
    setTimeout(runPreview, 0);
  });
}

// Networking only — no DOM updates — so runOcrFiles can process a batch one at a
// time without each call fighting over the shared status text.
async function ocrOneFile(file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch("/jobs/ocr", { method: "POST", body: formData });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "텍스트 추출에 실패했습니다.");
  const extracted = (data.text || "").trim();
  if (!extracted) throw new Error("텍스트를 찾지 못했습니다.");
  return extracted;
}

async function runOcrFiles(files) {
  const rawTextEl = document.getElementById("raw_text");
  const ocrStatusEl = document.getElementById("ocr-status");
  const ocrBtn = document.getElementById("ocr-btn");
  if (!files.length || !rawTextEl || !ocrStatusEl) return;
  if (ocrBtn) ocrBtn.disabled = true;

  const extractedTexts = [];
  const failed = [];
  try {
    for (let i = 0; i < files.length; i++) {
      ocrStatusEl.textContent =
        files.length > 1 ? MSG.ocrBatch(i + 1, files.length) : MSG.ocrOne;
      try {
        extractedTexts.push(await ocrOneFile(files[i]));
      } catch (e) {
        failed.push(files[i].name || `이미지 ${i + 1}`);
      }
    }

    if (extractedTexts.length) {
      const combined = extractedTexts.join("\n\n");
      rawTextEl.value = rawTextEl.value.trim()
        ? `${rawTextEl.value}\n\n${combined}`
        : combined;
      rawTextEl.dispatchEvent(new Event("input"));
    }

    if (!failed.length) {
      ocrStatusEl.textContent =
        files.length > 1 ? MSG.ocrDoneBatch(files.length) : MSG.ocrDoneOne;
    } else if (extractedTexts.length) {
      ocrStatusEl.textContent =
        `${files.length}개 중 ${extractedTexts.length}개 완료 (실패: ${failed.join(", ")})`;
    } else {
      ocrStatusEl.textContent = `텍스트 추출에 실패했습니다 (${failed.join(", ")})`;
    }

    if (extractedTexts.length && window.__jobfitRunPreview) window.__jobfitRunPreview();
  } finally {
    if (ocrBtn) ocrBtn.disabled = false;
  }
}

function initOcr() {
  const ocrBtn = document.getElementById("ocr-btn");
  const ocrFileEl = document.getElementById("ocr-file");
  if (!ocrBtn || !ocrFileEl) return;
  ocrBtn.addEventListener("click", () => runOcrFiles(Array.from(ocrFileEl.files)));
}

function initRawTextCounter() {
  const rawTextEl = document.getElementById("raw_text");
  const rawTextCountEl = document.getElementById("raw-text-count");
  if (!rawTextEl || !rawTextCountEl) return;
  const updateCount = () => {
    rawTextCountEl.textContent = rawTextEl.value.length
      ? `${rawTextEl.value.length}자 입력됨`
      : "";
  };
  updateCount();
  rawTextEl.addEventListener("input", updateCount);
}

// Profile page: copy a generated section's text to the clipboard.
function initCopyButtons() {
  const buttons = document.querySelectorAll(".copy-btn[data-copy-target]");
  if (!buttons.length) return;
  buttons.forEach((btn) => {
    const defaultText = btn.textContent;
    btn.addEventListener("click", async () => {
      const target = document.getElementById(btn.dataset.copyTarget);
      if (!target) return;
      const text = target.textContent;
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(text);
        } else {
          // execCommand fallback for non-secure contexts (e.g. a LAN-IP http:// host).
          const range = document.createRange();
          range.selectNodeContents(target);
          const sel = window.getSelection();
          sel.removeAllRanges();
          sel.addRange(range);
          document.execCommand("copy");
          sel.removeAllRanges();
        }
        btn.textContent = "복사됨 ✓";
      } catch (e) {
        btn.textContent = "복사 실패";
      }
      setTimeout(() => { btn.textContent = defaultText; }, 1500);
    });
  });
}

// Tailor workspace: clicking a missing-skill chip adds it to the skills input.
function initGapChips() {
  const chips = document.querySelectorAll(".gap-chip");
  if (!chips.length) return;
  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const input = document.querySelector('input[name="skills_text"]');
      if (!input) return;
      const skill = chip.textContent.replace(/^\+\s*/, "").trim();
      const current = input.value.split(",").map((s) => s.trim()).filter(Boolean);
      if (!current.includes(skill)) current.push(skill);
      input.value = current.join(", ");
      input.focus();
    });
  });
}
