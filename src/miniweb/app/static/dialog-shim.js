/**
 * Native dialog shim.
 *
 * MiniWeb pages render inside a sandboxed iframe in the annotation UI WITHOUT
 * `allow-modals`, so window.alert / confirm / prompt are silently suppressed —
 * a click that relies on them appears to "do nothing" (no feedback, and
 * confirm-gated actions like "Cancel booking?" never proceed because confirm()
 * returns false).
 *
 * Replace them with in-page equivalents so behaviour is consistent inside and
 * outside the iframe:
 *   - alert()   -> an in-page toast (the feedback the user expects)
 *   - confirm() -> proceeds (returns true); the action's own result is the
 *                  feedback. confirm() is synchronous and can't await an in-page
 *                  modal, and neither an agent nor the sandboxed iframe can use a
 *                  native confirm, so auto-proceed is the correct behaviour here.
 *   - prompt()  -> returns the supplied default (or "")
 *
 * Injected globally into every /sites/* page.
 */
(function () {
  'use strict';

  function toast(msg, kind) {
    try {
      var t = document.createElement('div');
      t.className = '_mw-toast';
      t.textContent = String(msg == null ? '' : msg);
      t.style.cssText =
        'position:fixed;top:18px;left:50%;transform:translateX(-50%);' +
        'background:' + (kind === 'error' ? '#c0392b' : '#2b2b32') + ';color:#fff;' +
        'padding:11px 18px;border-radius:8px;font:600 13px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;' +
        'z-index:2147483600;box-shadow:0 8px 28px rgba(0,0,0,.32);max-width:82vw;text-align:center;' +
        'white-space:pre-wrap;line-height:1.35;';
      (document.body || document.documentElement).appendChild(t);
      setTimeout(function () { t.style.transition = 'opacity .4s'; t.style.opacity = '0'; }, 2600);
      setTimeout(function () { if (t.parentNode) t.remove(); }, 3100);
    } catch (e) { /* no-op */ }
  }

  window.alert = function (msg) { toast(msg); };
  window.confirm = function (msg) { return true; };
  window.prompt = function (msg, def) { return def == null ? '' : String(def); };

  // Reusable by pages that want an in-page notification.
  window.__miniwebToast = toast;
})();
