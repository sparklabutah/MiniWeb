/* MiniWeb shared video player.
 * Enhances any element with [data-mini-player] into a realistic player:
 *   framed video box, real-time click/drag seek bar with chapter ticks,
 *   play/pause, CC (captions) toggle, and a settings menu (quality + speed).
 *
 * Data attributes on the container:
 *   data-title, data-subtitle          text shown in the "now playing" overlay
 *   data-duration                      length in SECONDS (may be filled by data-play-url)
 *   data-accent                        theme color (e.g. #3ea6ff)
 *   data-qualities                     comma list, e.g. "auto,1080p,720p,480p"
 *   data-captions="true"               show the CC button
 *   data-badge                         badge label (default "Video")
 *   data-play-url                      POST once on first play -> {chapters,[start_sec],exact_duration,stream_quality}
 *   data-seek-url                      POST {position, position_pct} on every scrub
 *   data-playback-url                  POST {speed, quality} when changed
 *
 * Call window.MiniPlayer.scan() after inserting players dynamically.
 */
(function () {
  function fmt(s) { s = Math.max(0, Math.floor(s || 0)); return Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2); }
  function esc(t) { var d = document.createElement('div'); d.textContent = t == null ? '' : t; return d.innerHTML; }
  function post(url, body, cb) {
    if (!url) return;
    fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) })
      .then(function (r) { return r.json(); }).then(function (d) { if (cb) cb(d); }).catch(function () {});
  }

  function enhance(el) {
    if (el.__mp) return; el.__mp = true;
    var d = el.dataset;
    var accent = d.accent || '#3ea6ff';
    var qualities = (d.qualities || 'auto,1080p,720p,480p,360p').split(',').map(function (s) { return s.trim(); }).filter(Boolean);
    var speeds = ['0.5', '0.75', '1', '1.25', '1.5', '2'];
    var duration = parseFloat(d.duration || '0') || 0;

    el.classList.add('mp-root');
    el.style.setProperty('--mp-accent', accent);
    if (d.bg) el.style.setProperty('--mp-bg', d.bg);

    var qOpts = qualities.map(function (q, i) {
      return '<div class="mp-opt mp-q' + (i === 0 ? ' mp-sel' : '') + '" data-q="' + esc(q) + '"><span class="mp-check">✓</span>' + esc(q) + '</div>';
    }).join('');
    var sOpts = speeds.map(function (s) {
      return '<div class="mp-opt mp-s' + (s === '1' ? ' mp-sel' : '') + '" data-s="' + s + '"><span class="mp-check">✓</span>' + (s === '1' ? 'Normal' : s + '×') + '</div>';
    }).join('');
    var ccBtn = (d.captions === 'true' || d.captions === '1')
      ? '<button class="mp-btn mp-cc-btn" title="Subtitles/CC">CC</button>' : '';

    el.innerHTML =
      '<div class="mp-badge">▶ ' + esc(d.badge || 'Video') + '</div>' +
      '<div class="mp-screen">' +
        '<div class="mp-bigplay">▶</div>' +
        '<div class="mp-hint">Video plays here — click to play</div>' +
        '<div class="mp-nowplaying"><div class="mp-np-title">' + esc(d.title || '') + '</div>' +
          '<div class="mp-np-sub">' + esc(d.subtitle || '') + '</div></div>' +
      '</div>' +
      '<div class="mp-cc-overlay">' + esc(d.subtitleText || 'Subtitles on') + '</div>' +
      '<div class="mp-controls">' +
        '<div class="mp-seek" role="slider" tabindex="0" aria-label="Seek" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">' +
          '<div class="mp-played"></div><div class="mp-knob"></div></div>' +
        '<div class="mp-row">' +
          '<button class="mp-btn mp-skip mp-back" title="Back 10s" aria-label="Skip back 10 seconds">⏪</button>' +
          '<button class="mp-btn mp-pp" title="Play/pause">❚❚</button>' +
          '<button class="mp-btn mp-skip mp-fwd" title="Forward 10s" aria-label="Skip forward 10 seconds">⏩</button>' +
          '<span class="mp-time"><span class="mp-cur">0:00</span> / <span class="mp-tot">' + fmt(duration) + '</span></span>' +
          '<span class="mp-spacer"></span>' + ccBtn +
          '<div class="mp-gear"><button class="mp-btn mp-gear-btn" title="Settings" aria-label="Settings">⚙</button>' +
            '<div class="mp-menu"><div class="mp-menu-h">Quality</div>' + qOpts +
              '<div class="mp-sep"></div><div class="mp-menu-h">Speed</div>' + sOpts + '</div></div>' +
        '</div>' +
      '</div>';

    // ---- refs ----
    var q = function (s) { return el.querySelector(s); };
    var screen = q('.mp-screen'), controls = q('.mp-controls'), seek = q('.mp-seek'),
        played = q('.mp-played'), knob = q('.mp-knob'), pp = q('.mp-pp'),
        curEl = q('.mp-cur'), totEl = q('.mp-tot'), gear = q('.mp-gear'),
        gearBtn = q('.mp-gear-btn'), ccBtnEl = q('.mp-cc-btn'),
        backBtn = q('.mp-back'), fwdBtn = q('.mp-fwd');

    var t = 0, playing = false, started = false, chapters = [], lastTs = null, rafOn = false;
    var speed = 1;

    function render() {
      var frac = duration > 0 ? t / duration : 0;
      played.style.width = (frac * 100) + '%'; knob.style.left = (frac * 100) + '%';
      curEl.textContent = fmt(t); seek.setAttribute('aria-valuenow', Math.round(frac * 100));
    }
    function loop(ts) {
      if (playing) {
        if (lastTs != null) { t += (ts - lastTs) / 1000 * speed; if (t >= duration) { t = duration; pause(); } render(); }
        lastTs = ts;
      } else { lastTs = null; }
      requestAnimationFrame(loop);
    }
    function play() { if (t >= duration && duration > 0) { t = 0; postSeek(); } playing = true; pp.innerHTML = '❚❚'; if (!rafOn) { rafOn = true; requestAnimationFrame(loop); } }
    function pause() { playing = false; pp.innerHTML = '▶'; }

    var seekTimer = null;
    function postSeek() {
      if (!d.seekUrl || duration <= 0) return;
      clearTimeout(seekTimer);
      seekTimer = setTimeout(function () {
        post(d.seekUrl, { position: Math.round(t), position_pct: +(t / duration * 100).toFixed(1) },
          function (r) { if (r && r.position_label) curEl.textContent = r.position_label; });
      }, 90);
    }
    function scrub(clientX) {
      var r = seek.getBoundingClientRect();
      t = Math.min(1, Math.max(0, (clientX - r.left) / r.width)) * duration; render();
    }
    seek.addEventListener('mousedown', function (e) {
      seek.classList.add('mp-drag'); scrub(e.clientX); e.preventDefault();
      function mm(ev) { scrub(ev.clientX); }
      function mu() { seek.classList.remove('mp-drag'); document.removeEventListener('mousemove', mm); document.removeEventListener('mouseup', mu); postSeek(); }
      document.addEventListener('mousemove', mm); document.addEventListener('mouseup', mu);
    });
    seek.addEventListener('touchstart', function (e) { seek.classList.add('mp-drag'); scrub(e.touches[0].clientX); e.preventDefault(); }, { passive: false });
    seek.addEventListener('touchmove', function (e) { scrub(e.touches[0].clientX); e.preventDefault(); }, { passive: false });
    seek.addEventListener('touchend', function () { seek.classList.remove('mp-drag'); postSeek(); });
    seek.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowRight') { t = Math.min(duration, t + 5); render(); postSeek(); e.preventDefault(); }
      else if (e.key === 'ArrowLeft') { t = Math.max(0, t - 5); render(); postSeek(); e.preventDefault(); }
    });
    pp.addEventListener('click', function () { playing ? pause() : play(); });
    // Skip back / forward 10s — jump to an earlier/later timestamp.
    function skip(delta) {
      if (duration <= 0) return;
      t = Math.min(duration, Math.max(0, t + delta)); render(); postSeek();
    }
    if (backBtn) backBtn.addEventListener('click', function () { skip(-10); });
    if (fwdBtn) fwdBtn.addEventListener('click', function () { skip(10); });

    function addTicks() {
      el.querySelectorAll('.mp-tick').forEach(function (x) { x.remove(); });
      if (duration <= 0) return;
      chapters.forEach(function (c) {
        var sec = c.start_sec != null ? c.start_sec
                : (c.start_min != null ? c.start_min * 60 : c.start);
        if (sec == null || isNaN(sec)) return;
        var tick = document.createElement('div'); tick.className = 'mp-tick';
        tick.style.left = (sec / duration * 100) + '%'; tick.title = c.title || ''; seek.appendChild(tick);
      });
    }

    function start() {
      el.classList.add('mp-active', 'mp-playing');
      var go = function () { if (!started) { started = true; t = 0; play(); render(); postSeek(); } };
      if (d.playUrl) {
        post(d.playUrl, {}, function (r) {
          if (r) {
            if (!duration && r.exact_duration) { var p = ('' + r.exact_duration).split(':'); duration = (+p[0]) * 60 + (+p[1]); totEl.textContent = fmt(duration); }
            if (r.chapters) { chapters = r.chapters; addTicks(); }
            if (r.stream_quality) { selectQuality(r.stream_quality, true); }
          }
          go();
        });
      } else { go(); }
    }
    screen.addEventListener('click', start);

    // ---- settings menu ----
    gearBtn.addEventListener('click', function (e) { e.stopPropagation(); gear.classList.toggle('mp-open'); });
    document.addEventListener('click', function (e) { if (!gear.contains(e.target)) gear.classList.remove('mp-open'); });
    function selectQuality(qv, silent) {
      var opts = el.querySelectorAll('.mp-q'); var found = false;
      opts.forEach(function (o) { var on = o.dataset.q === qv; o.classList.toggle('mp-sel', on); if (on) found = true; });
      if (!found) {  // quality reported by backend but not in the list — add it
        var menu = el.querySelector('.mp-menu'); var sep = el.querySelector('.mp-sep');
        var o = document.createElement('div'); o.className = 'mp-opt mp-q mp-sel'; o.dataset.q = qv;
        o.innerHTML = '<span class="mp-check">✓</span>' + esc(qv); o.addEventListener('click', function () { selectQuality(qv); });
        menu.insertBefore(o, sep);
        el.querySelectorAll('.mp-q').forEach(function (x) { if (x !== o) x.classList.remove('mp-sel'); });
      }
      if (!silent && d.playbackUrl) post(d.playbackUrl, { quality: qv });
    }
    el.querySelectorAll('.mp-q').forEach(function (o) { o.addEventListener('click', function () { selectQuality(o.dataset.q); }); });
    el.querySelectorAll('.mp-s').forEach(function (o) {
      o.addEventListener('click', function () {
        el.querySelectorAll('.mp-s').forEach(function (x) { x.classList.remove('mp-sel'); });
        o.classList.add('mp-sel'); speed = parseFloat(o.dataset.s);
        if (d.playbackUrl) post(d.playbackUrl, { speed: speed });
      });
    });

    // ---- captions ----
    if (ccBtnEl) ccBtnEl.addEventListener('click', function () {
      var on = el.classList.toggle('mp-cc'); ccBtnEl.classList.toggle('mp-on', on);
    });
  }

  function scan(root) { (root || document).querySelectorAll('[data-mini-player]').forEach(enhance); }
  // Reconfigure an already-enhanced player with new data (e.g. a new lecture).
  function load(el, opts) {
    opts = opts || {};
    Object.keys(opts).forEach(function (k) { if (opts[k] != null) el.dataset[k] = opts[k]; });
    el.__mp = false;
    el.className = el.className.split(/\s+/).filter(function (c) { return c.indexOf('mp-') !== 0; }).join(' ');
    el.style.removeProperty('--mp-bg');
    el.innerHTML = '';
    enhance(el);
  }
  window.MiniPlayer = { scan: scan, enhance: enhance, load: load };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { scan(); });
  else scan();
})();
