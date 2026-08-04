/* MiniWeb cross-site Share.
 * Opens a modal to share the current page to other MiniWeb sites — ForumHub,
 * PixShare (multimedia posting), and Messages — which actually create the
 * content there. Plus a copyable link.
 *
 * Usage:
 *   window.MiniWebShare.open({ title: '...', url: '...' })
 *   or add [data-miniweb-share] to any button (optionally data-share-title /
 *   data-share-url) and it opens automatically on click.
 */
(function () {
  'use strict';

  var TARGETS = [
    { label: 'ForumHub', sub: 'Post to a community', endpoint: '/sites/forums/api/share', icon: '💬', color: '#ff4500' },
    { label: 'PixShare', sub: 'Share to your feed', endpoint: '/sites/multimedia-posting/api/share', icon: '📷', color: '#8e44ad' },
    { label: 'Messages', sub: 'Send to your chat', endpoint: '/sites/instant-messaging/api/share', icon: '✉️', color: '#0b93f6' },
  ];

  var current = { title: '', url: '' };
  var overlay = null;

  function css() {
    if (document.getElementById('_mws-css')) return;
    var s = document.createElement('style'); s.id = '_mws-css';
    s.textContent =
      '._mws-ov{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:1000000;display:flex;align-items:center;justify-content:center;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}' +
      '._mws-win{background:#fff;color:#111;border-radius:12px;width:min(420px,92vw);box-shadow:0 16px 48px rgba(0,0,0,.3);overflow:hidden}' +
      '._mws-hd{display:flex;align-items:center;justify-content:space-between;padding:15px 18px;border-bottom:1px solid #eee}' +
      '._mws-hd b{font-size:15px}' +
      '._mws-x{border:none;background:none;font-size:22px;line-height:1;color:#888;cursor:pointer}' +
      '._mws-body{padding:14px 18px 18px}' +
      '._mws-tgt{display:flex;align-items:center;gap:12px;width:100%;text-align:left;background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:11px 14px;margin-bottom:9px;cursor:pointer;font-family:inherit}' +
      '._mws-tgt:hover{background:#f8fafc;border-color:#cbd5e1}' +
      '._mws-tgt:disabled{opacity:.65;cursor:default}' +
      '._mws-ic{width:38px;height:38px;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:18px;color:#fff;flex-shrink:0}' +
      '._mws-tt{flex:1;min-width:0}' +
      '._mws-tl{display:block;font-weight:700;font-size:.92rem;color:#111}' +
      '._mws-ts{display:block;font-size:.78rem;color:#6b7280}' +
      '._mws-st{font-size:.8rem;font-weight:700;color:#16a34a;white-space:nowrap}' +
      '._mws-st a{color:#2563eb}' +
      '._mws-link{display:flex;gap:8px;align-items:center;background:#f3f4f6;border:1px solid #e5e7eb;border-radius:8px;padding:5px 5px 5px 12px;margin-top:6px}' +
      '._mws-link input{flex:1;border:none;background:none;font-size:.82rem;color:#374151;outline:none;min-width:0}' +
      '._mws-copy{background:#111827;color:#fff;border:none;border-radius:6px;padding:7px 15px;font-weight:700;font-size:.8rem;cursor:pointer;white-space:nowrap}' +
      '._mws-lbl{font-size:.72rem;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:.03rem;margin:4px 0 6px}';
    document.head.appendChild(s);
  }

  function close() { if (overlay) { overlay.remove(); overlay = null; } }

  function shareTo(target, row) {
    var btn = row.querySelector('._mws-tgt');
    var status = row.querySelector('._mws-st');
    btn.disabled = true; status.textContent = 'Sharing…';
    fetch(target.endpoint, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: current.title, url: current.url })
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (d && d.ok) {
        status.innerHTML = '✓ Shared · <a href="' + d.view_url + '">View</a>';
      } else {
        status.textContent = (d && d.error) ? d.error : 'Failed';
        status.style.color = '#dc2626'; btn.disabled = false;
      }
    }).catch(function () {
      status.textContent = 'Failed'; status.style.color = '#dc2626'; btn.disabled = false;
    });
  }

  function open(opts) {
    opts = opts || {};
    current.title = opts.title || document.title || 'Shared link';
    current.url = opts.url || window.location.href;
    css(); close();

    overlay = document.createElement('div');
    overlay.className = '_mws-ov';
    overlay.addEventListener('click', function (e) { if (e.target === overlay) close(); });

    var win = document.createElement('div'); win.className = '_mws-win';
    var hd = document.createElement('div'); hd.className = '_mws-hd';
    hd.innerHTML = '<b>Share to MiniWeb</b>';
    var x = document.createElement('button'); x.className = '_mws-x'; x.innerHTML = '&times;'; x.onclick = close;
    hd.appendChild(x); win.appendChild(hd);

    var body = document.createElement('div'); body.className = '_mws-body';
    var lbl = document.createElement('div'); lbl.className = '_mws-lbl'; lbl.textContent = 'Share to a site'; body.appendChild(lbl);

    TARGETS.forEach(function (t) {
      var row = document.createElement('div');
      var b = document.createElement('button'); b.className = '_mws-tgt'; b.type = 'button';
      b.innerHTML = '<span class="_mws-ic" style="background:' + t.color + '">' + t.icon + '</span>' +
        '<span class="_mws-tt"><span class="_mws-tl">' + t.label + '</span><span class="_mws-ts">' + t.sub + '</span></span>' +
        '<span class="_mws-st"></span>';
      b.addEventListener('click', function () { shareTo(t, row); });
      row.appendChild(b); body.appendChild(row);
    });

    var lbl2 = document.createElement('div'); lbl2.className = '_mws-lbl'; lbl2.style.marginTop = '12px'; lbl2.textContent = 'Or copy link'; body.appendChild(lbl2);
    var link = document.createElement('div'); link.className = '_mws-link';
    var input = document.createElement('input'); input.readOnly = true; input.value = current.url;
    input.addEventListener('click', function () { this.select(); });
    var copy = document.createElement('button'); copy.className = '_mws-copy'; copy.textContent = 'Copy';
    copy.addEventListener('click', function () {
      navigator.clipboard.writeText(current.url).then(function () {
        copy.textContent = 'Copied!'; setTimeout(function () { copy.textContent = 'Copy'; }, 1500);
      }).catch(function () { input.select(); });
    });
    link.appendChild(input); link.appendChild(copy); body.appendChild(link);

    win.appendChild(body); overlay.appendChild(win); document.body.appendChild(overlay);
  }

  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
  // Auto-bind declarative triggers.
  document.addEventListener('click', function (e) {
    var t = e.target.closest('[data-miniweb-share]');
    if (!t) return;
    e.preventDefault();
    open({ title: t.getAttribute('data-share-title') || undefined,
           url: t.getAttribute('data-share-url') || undefined });
  });

  window.MiniWebShare = { open: open };
})();
