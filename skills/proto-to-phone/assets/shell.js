/* proto-to-phone: page side of the native shell. Injected by adapt.py right
 * before </body>, after window.__shellConfig. Nothing here knows the
 * prototype: everything specific comes from that config. */
(function () {
  'use strict';
  var cfg = window.__shellConfig || {};
  var root = document.documentElement;
  root.classList.add('app-shell');

  var bridge = window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.shell;
  function post(msg) { if (bridge) bridge.postMessage(msg); }

  function all(selector) {
    try { return Array.prototype.slice.call(document.querySelectorAll(selector)); } catch (e) { return []; }
  }
  function isEditable(el) {
    return !!el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));
  }

  /* ── keyboard ─────────────────────────────────────────────────────────
   * The native keyboard shrinks the web view, so nothing has to be lifted:
   * --kbh stays 0. The class tells the design the keyboard is up, which is
   * what mockups use to collapse a tab bar or reveal a composer. */
  window.__shell = {
    keyboard: function (open) {
      var nodes = [root];
      (cfg.keyboardTargets || []).forEach(function (s) { nodes = nodes.concat(all(s)); });
      nodes.forEach(function (n) {
        n.style.setProperty('--kbh', '0px');
        n.classList.toggle('kb-open', !!open);
      });
    }
  };

  /* A programmatic focus move (a sheet closing and handing focus back to its
   * button) does not dismiss the real keyboard: ask the shell to. */
  document.addEventListener('focusout', function () {
    setTimeout(function () {
      if (!isEditable(document.activeElement)) post({ endEditing: true });
    }, 120);
  }, true);

  /* ── theme: status bar, keyboard appearance and the strip uncovered by
   * the keyboard follow the page background ───────────────────────────── */
  var cv = document.createElement('canvas');
  cv.width = cv.height = 1;
  var cx = cv.getContext('2d', { willReadFrequently: true });
  var last = '';

  /* oklch()/color-mix() are not parsed by getComputedStyle consumers, so the
   * color is painted and read back as a pixel. Transparent layers defer to
   * their parent. */
  function paintedBackground(el) {
    for (; el; el = el.parentElement) {
      cx.clearRect(0, 0, 1, 1);
      cx.fillStyle = '#fff';
      cx.fillStyle = getComputedStyle(el).backgroundColor;
      cx.clearRect(0, 0, 1, 1);
      cx.fillRect(0, 0, 1, 1);
      var d = cx.getImageData(0, 0, 1, 1).data;
      if (d[3] > 250) return d;
    }
    return [255, 255, 255, 255];
  }
  function report() {
    var el = (cfg.themeSource && document.querySelector(cfg.themeSource)) || document.body;
    var d = paintedBackground(el);
    var dark = (0.299 * d[0] + 0.587 * d[1] + 0.114 * d[2]) < 128;
    var msg = { r: d[0], g: d[1], b: d[2], dark: dark };
    var key = JSON.stringify(msg);
    if (key === last) return;
    last = key;
    post(msg);
  }
  function watchTheme() {
    var again = function () { requestAnimationFrame(report); };
    var mo = new MutationObserver(again);
    [root, document.body, cfg.themeSource && document.querySelector(cfg.themeSource)].forEach(function (n) {
      if (n) mo.observe(n, { attributes: true, attributeFilter: ['class', 'style', 'data-theme'] });
    });
    document.addEventListener('transitionend', again, true);
    report();
    setTimeout(report, 400);
  }
  watchTheme();

  /* ── optional: drag a bottom sheet down to close it, like a native one.
   * cfg.sheetDrag = { sheet, scrim, openClass?, skip? }. Claims the finger
   * only when it moves down, more vertically than sideways, with the scroller
   * underneath at its top. Closes past 26% of the height or at 0.55 px/ms by
   * clicking the scrim. ─────────────────────────────────────────────── */
  var sd = cfg.sheetDrag;
  var sheet = sd && document.querySelector(sd.sheet);
  var scrim = sd && document.querySelector(sd.scrim);
  if (sheet && scrim) {
    var openClass = sd.openClass || 'on';
    var SKIP = sd.skip || 'input,textarea,select,canvas,[contenteditable],[data-nodrag]';
    var y0 = 0, x0 = 0, lastY = 0, lastT = 0, vel = 0, armed = false, claimed = false;

    var scrollerAtTop = function (el) {
      for (; el && el !== sheet; el = el.parentElement) {
        var s = getComputedStyle(el);
        var scrolls = (s.overflowY === 'auto' || s.overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 1;
        if (scrolls && el.scrollTop > 0) return false;
      }
      return true;
    };

    sheet.addEventListener('touchstart', function (e) {
      claimed = false;
      armed = sheet.classList.contains(openClass) && e.touches.length === 1 &&
              !(e.target.closest && e.target.closest(SKIP)) && scrollerAtTop(e.target);
      if (!armed) return;
      var t = e.touches[0];
      x0 = t.clientX; y0 = lastY = t.clientY; lastT = e.timeStamp; vel = 0;
    }, { passive: true });

    sheet.addEventListener('touchmove', function (e) {
      if (!armed) return;
      var t = e.touches[0], dy = t.clientY - y0, dx = t.clientX - x0;
      if (!claimed) {
        if (dy > 0 && dy >= Math.abs(dx)) {
          claimed = true;
          sheet.style.transition = 'none';
          scrim.style.transition = 'none';
        } else if (Math.abs(dx) > 0 || dy < 0) {
          armed = false;
          return;
        } else return;
      }
      e.preventDefault();
      var dt = e.timeStamp - lastT;
      if (dt > 0) vel = (t.clientY - lastY) / dt;
      lastY = t.clientY; lastT = e.timeStamp;
      var y = Math.max(0, dy);
      sheet.style.transform = 'translateY(' + y + 'px)';
      scrim.style.opacity = String(Math.max(0, 1 - y / (sheet.offsetHeight || 1)));
    }, { passive: false });

    var release = function () {
      armed = false;
      if (!claimed) return;
      claimed = false;
      var dy = lastY - y0;
      var close = dy > sheet.offsetHeight * 0.26 || vel > 0.55;
      sheet.style.transition = ''; scrim.style.transition = '';
      sheet.style.transform = ''; scrim.style.opacity = '';
      if (close) scrim.click();
    };
    sheet.addEventListener('touchend', release);
    sheet.addEventListener('touchcancel', release);
  }
})();
