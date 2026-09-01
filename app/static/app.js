document.addEventListener("DOMContentLoaded", () => {
  const toast = document.getElementById("toast");
  if (toast) {
    const url = new URL(window.location.href);
    url.searchParams.delete("msg");
    window.history.replaceState({}, "", url);
    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  const themeToggle = document.getElementById("theme-toggle");
  if (themeToggle) {
    const setIcon = () => {
      themeToggle.textContent = document.documentElement.getAttribute("data-theme") === "dark" ? "☀️" : "🌙";
    };
    setIcon();
    themeToggle.addEventListener("click", () => {
      const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("theme", next);
      setIcon();
    });
  }

  document.querySelectorAll(".tab-btn[data-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn[data-tab]").forEach((b) => {
        b.classList.remove("active");
        b.setAttribute("aria-selected", "false");
      });
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      btn.setAttribute("aria-selected", "true");
      document.getElementById(btn.dataset.tab).classList.add("active");
    });
  });

  const urlEl = document.getElementById("url");
  const sourceSiteEl = document.getElementById("source_site");
  if (urlEl && sourceSiteEl) {
    let sourceSiteTouched = false;
    sourceSiteEl.addEventListener("input", () => { sourceSiteTouched = true; });
    sourceSiteEl.addEventListener("change", () => { sourceSiteTouched = true; });

    const guessSource = async () => {
      if (sourceSiteTouched || !urlEl.value.trim()) return;
      const body = new URLSearchParams({ url: urlEl.value });
      const res = await fetch("/jobs/guess-source", { method: "POST", body });
      const data = await res.json();
      if (data.source_site) {
        sourceSiteEl.value = data.source_site;
        sourceSiteEl.classList.add("field-flash");
        setTimeout(() => sourceSiteEl.classList.remove("field-flash"), 700);
      }
    };

    urlEl.addEventListener("change", guessSource);
    urlEl.addEventListener("blur", guessSource);
  }

  const previewBtn = document.getElementById("preview-btn");
  const rawTextEl = document.getElementById("raw_text");
  if (previewBtn && rawTextEl) {
    // Fields the user has typed/selected into by hand are never overwritten
    // by an auto-guess, even if they later clear them back out.
    const autoFillIds = ["title", "company", "address", "position", "experience_level"];
    const touched = new Set();
    autoFillIds.forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener("input", () => touched.add(id));
      if (el) el.addEventListener("change", () => touched.add(id));
    });

    const previewBtnDefaultText = previewBtn.textContent;

    const runPreview = async () => {
      const rawText = rawTextEl.value;
      if (!rawText.trim() || previewBtn.disabled) return;
      previewBtn.disabled = true;
      previewBtn.textContent = "분석 중...";
      try {
        const body = new URLSearchParams({ raw_text: rawText });
        const res = await fetch("/jobs/preview", { method: "POST", body });
        const data = await res.json();

        document.getElementById("preview-required").textContent =
          data.required_skills.length ? data.required_skills.join(", ") : "인식된 스킬 없음";
        document.getElementById("preview-preferred").textContent =
          data.preferred_skills.length ? data.preferred_skills.join(", ") : "인식된 스킬 없음";
        document.getElementById("preview-result").style.display = "block";

        autoFillIds.forEach((id) => {
          if (touched.has(id)) return;
          const value = data[id];
          if (!value) return;
          const el = document.getElementById(id);
          if (!el) return;
          if (el.tagName === "SELECT" && !Array.from(el.options).some((o) => o.value === value)) {
            // e.g. an experience range like "3년 이상" that isn't one of the
            // preset options — add it so the guess isn't silently dropped.
            el.add(new Option(value, value, true, true));
          }
          el.value = value;
        });
      } finally {
        previewBtn.disabled = false;
        previewBtn.textContent = previewBtnDefaultText;
      }
    };

    previewBtn.addEventListener("click", runPreview);
    // Paste-and-go: auto-fill as soon as the posting text lands, no extra click needed.
    rawTextEl.addEventListener("paste", (event) => {
      const items = event.clipboardData ? Array.from(event.clipboardData.items) : [];
      const imageFiles = items
        .filter((item) => item.type.startsWith("image/"))
        .map((item) => item.getAsFile())
        .filter(Boolean);
      if (imageFiles.length) {
        // A pasted screenshot has no text payload to fall through to, so route
        // it to OCR instead of letting the browser paste it as an object/blob.
        event.preventDefault();
        runOcrFiles(imageFiles);
        return;
      }
      setTimeout(runPreview, 0);
    });
  }

  const ocrBtn = document.getElementById("ocr-btn");
  const ocrFileEl = document.getElementById("ocr-file");
  const ocrStatusEl = document.getElementById("ocr-status");

  // Networking only — no DOM updates — so runOcrFiles can process a batch
  // one at a time without each call fighting over the shared status text.
  async function ocrOneFile(file) {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch("/jobs/ocr", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "텍스트 추출에 실패했습니다.");
    const extracted = (data.text || "").trim();
    if (!extracted) throw new Error("텍스트를 찾지 못했습니다.");
    return extracted;
  }

  async function runOcrFiles(files) {
    if (!files.length || !rawTextEl || !ocrStatusEl) return;
    if (ocrBtn) ocrBtn.disabled = true;
    const extractedTexts = [];
    const failed = [];
    try {
      for (let i = 0; i < files.length; i++) {
        ocrStatusEl.textContent = files.length > 1
          ? `이미지 ${i + 1}/${files.length} 처리 중...`
          : "인식 중...";
        try {
          extractedTexts.push(await ocrOneFile(files[i]));
        } catch (e) {
          failed.push(files[i].name || `이미지 ${i + 1}`);
        }
      }

      if (extractedTexts.length) {
        const combined = extractedTexts.join("\n\n");
        rawTextEl.value = rawTextEl.value.trim() ? `${rawTextEl.value}\n\n${combined}` : combined;
        rawTextEl.dispatchEvent(new Event("input"));
      }

      if (!failed.length) {
        ocrStatusEl.textContent = files.length > 1
          ? `${files.length}개 이미지 텍스트 추출 완료`
          : "텍스트 추출 완료";
      } else if (extractedTexts.length) {
        ocrStatusEl.textContent = `${files.length}개 중 ${extractedTexts.length}개 완료 (실패: ${failed.join(", ")})`;
      } else {
        ocrStatusEl.textContent = `텍스트 추출에 실패했습니다 (${failed.join(", ")})`;
      }

      if (extractedTexts.length) runPreviewIfAvailable();
    } finally {
      if (ocrBtn) ocrBtn.disabled = false;
    }
  }

  function runPreviewIfAvailable() {
    const btn = document.getElementById("preview-btn");
    if (btn) btn.click();
  }

  if (ocrBtn && ocrFileEl) {
    ocrBtn.addEventListener("click", () => runOcrFiles(Array.from(ocrFileEl.files)));
  }

  const rawTextCountEl = document.getElementById("raw-text-count");
  if (rawTextEl && rawTextCountEl) {
    const updateCount = () => {
      rawTextCountEl.textContent = rawTextEl.value.length ? `${rawTextEl.value.length}자 입력됨` : "";
    };
    updateCount();
    rawTextEl.addEventListener("input", updateCount);
  }
});
