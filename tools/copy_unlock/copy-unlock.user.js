// ==UserScript==
// @name         JobFit 복사 잠금 해제 (사람인/잡코리아)
// @namespace    jobfit.copy-unlock
// @version      1.0.0
// @description  사람인/잡코리아 공고 페이지의 텍스트 선택·복사 차단을 풀어줍니다. 복사한 원문은 JobFit /jobs/new 폼에 직접 붙여넣어 사용하세요. 자동으로 페이지를 가져오거나 서버에 요청을 보내지 않습니다.
// @match        *://*.saramin.co.kr/*
// @match        *://*.jobkorea.co.kr/*
// @run-at       document-idle
// @grant        none
// ==/UserScript==

(function () {
  "use strict";

  var BLOCKED_ATTRS = ["oncopy", "oncut", "oncontextmenu", "onselectstart", "ondragstart", "onmousedown"];
  var BLOCKED_EVENTS = ["copy", "cut", "contextmenu", "selectstart", "dragstart"];

  function injectSelectableStyle() {
    if (document.getElementById("__copy_unlock_style__")) return;
    var style = document.createElement("style");
    style.id = "__copy_unlock_style__";
    style.textContent =
      "* { -webkit-user-select: text !important; -moz-user-select: text !important; " +
      "-ms-user-select: text !important; user-select: text !important; }";
    (document.head || document.documentElement).appendChild(style);
  }

  function clearInlineHandlers() {
    [document, document.documentElement, document.body].forEach(function (node) {
      if (!node) return;
      BLOCKED_ATTRS.forEach(function (attr) {
        try {
          node[attr] = null;
        } catch (e) {}
      });
    });
    document.querySelectorAll("*").forEach(function (el) {
      BLOCKED_ATTRS.forEach(function (attr) {
        if (el.hasAttribute(attr)) el.removeAttribute(attr);
      });
    });
  }

  var didStripListeners = false;
  function stripAddedListenersOnce() {
    // outerHTML 재대입은 페이지 상호작용을 깨뜨릴 수 있으므로 최초 1회만 수행.
    // 이후 지연 렌더링되는 콘텐츠는 clearInlineHandlers()만으로 충분한 경우가 대부분.
    if (didStripListeners || !document.body) return;
    try {
      // eslint-disable-next-line no-self-assign
      document.body.outerHTML = document.body.outerHTML;
      didStripListeners = true;
    } catch (e) {}
  }

  function installCaptureGuards() {
    if (window.__copyUnlockGuardsInstalled) return;
    BLOCKED_EVENTS.forEach(function (type) {
      document.addEventListener(
        type,
        function (evt) {
          evt.stopImmediatePropagation();
        },
        true
      );
    });
    window.__copyUnlockGuardsInstalled = true;
  }

  function run() {
    injectSelectableStyle();
    clearInlineHandlers();
    stripAddedListenersOnce();
    clearInlineHandlers();
    installCaptureGuards();
  }

  run();

  // 사람인/잡코리아 공고 본문은 AJAX로 늦게 채워지는 경우가 있어,
  // 새 노드가 추가될 때마다 다시 한번 잠금 해제를 적용한다.
  var observer = new MutationObserver(function () {
    injectSelectableStyle();
    clearInlineHandlers();
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });
})();
