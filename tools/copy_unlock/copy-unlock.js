/**
 * 복사 잠금 해제 (copy-unlock)
 *
 * 사람인/잡코리아처럼 텍스트 선택·복사를 CSS/JS로 막아둔 페이지에서,
 * "사용자가 그 페이지를 직접 보고 있을 때" 선택·복사만 다시 가능하게
 * 만들어 주는 순수 클라이언트 스크립트입니다.
 *
 * 이 스크립트는 페이지를 자동으로 가져오거나 서버에 요청을 보내지
 * 않습니다 — 사용자가 이미 열어 둔 브라우저 탭 안에서만 동작하며,
 * 복사한 원문은 여전히 사용자가 직접 JobFit의 /jobs/new 폼에
 * 붙여넣어야 합니다. 이 파일이 bookmarklet(copy-unlock.bookmarklet.txt)과
 * Tampermonkey 유저스크립트(copy-unlock.user.js) 양쪽의 원본 로직입니다.
 *
 * 무력화 대상:
 *  1) CSS user-select:none
 *  2) document/body/개별 엘리먼트에 걸린 oncopy/oncut/oncontextmenu/
 *     onselectstart/ondragstart/onmousedown 인라인 핸들러
 *  3) addEventListener로 등록된 동일 계열 핸들러
 *     (body.outerHTML 재대입으로 DOM을 강제 재파싱해 통째로 제거)
 *  4) 위 방법으로도 못 잡는 경우를 위한 capture 단계 stopImmediatePropagation
 */
(function applyCopyUnlock() {
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

  function stripAddedListeners() {
    if (!document.body) return;
    try {
      // eslint-disable-next-line no-self-assign
      document.body.outerHTML = document.body.outerHTML;
    } catch (e) {
      // 일부 사이트는 이 트릭에서 예외를 던질 수 있음 — 무시하고 나머지 방어선에 의존
    }
  }

  function installCaptureGuards() {
    BLOCKED_EVENTS.forEach(function (type) {
      document.addEventListener(
        type,
        function (evt) {
          evt.stopImmediatePropagation();
        },
        true
      );
    });
  }

  function run() {
    injectSelectableStyle();
    clearInlineHandlers();
    stripAddedListeners();
    // outerHTML 재대입 이후에도 남아있을 수 있는 핸들러를 한 번 더 정리
    clearInlineHandlers();
    installCaptureGuards();
  }

  run();
  window.__copyUnlockRun = run; // MutationObserver 등에서 재호출할 수 있도록 노출
})();
