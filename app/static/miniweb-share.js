/* MiniWeb cross-site Share.
 * Opens a modal to share the current page to other MiniWeb sites — ForumHub,
 * PixShare (multimedia posting), and Messages — which actually create the
 * content there. The user picks a target, then edits the post before sending
 * (and, for Messages, chooses which chat to send it to). Plus a copyable link.
 *
 * Usage:
 *   window.MiniWebShare.open({ title: '...', url: '...' })
 *   or add [data-miniweb-share] to any button (optionally data-share-title /
 *   data-share-url) and it opens automatically on click.
 */
(function () {
  'use strict';

  var TARGETS = [
    { key: 'forum', label: 'ForumHub', sub: 'Post to a community', endpoint: '/sites/forums/api/share', icon: '💬', color: '#ff4500' },
    { key: 'pix', label: 'PixShare', sub: 'Share to your feed', endpoint: '/sites/multimedia-posting/api/share', icon: '📷', color: '#8e44ad' },
    { key: 'msg', label: 'Messages', sub: 'Send to a chat', endpoint: '/sites/instant-messaging/api/share', icon: '✉️', color: '#0b93f6', recipients: '/sites/instant-messaging/api/share_targets' },
  ];

  var current = { title: '', url: '' };
  var overlay = null;

  function css() {
    if (document.getElementById('_mws-css')) return;
    var s = document.createElement('style'); s.id = '_mws-css';
    s.textContent =
      '._mws-ov{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:1000000;display:flex;align-items:center;justify-content:center;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}' +
      '._mws-win{background:#fff;color:#111;border-radius:12px;width:min(430px,92vw);box-shadow:0 16px 48px rgba(0,0,0,.3);overflow:hidden}' +
      '._mws-hd{display:flex;align-items:center;gap:10px;padding:15px 18px;border-bottom:1px solid #eee}' +
      '._mws-hd b{font-size:15px;flex:1}' +
      '._mws-x{border:none;background:none;font-size:22px;line-height:1;color:#888;cursor:pointer;padding:0}' +
      '._mws-back{border:none;background:none;font-size:20px;line-height:1;color:#555;cursor:pointer;padding:0 2px}' +
      '._mws-body{padding:14px 18px 18px}' +
      '._mws-tgt{display:flex;align-items:center;gap:12px;width:100%;text-align:left;background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:11px 14px;margin-bottom:9px;cursor:pointer;font-family:inherit}' +
      '._mws-tgt:hover{background:#f8fafc;border-color:#cbd5e1}' +
      '._mws-ic{width:38px;height:38px;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:18px;color:#fff;flex-shrink:0}' +
      '._mws-tt{flex:1;min-width:0}' +
      '._mws-tl{display:block;font-weight:700;font-size:.92rem;color:#111}' +
      '._mws-ts{display:block;font-size:.78rem;color:#6b7280}' +
      '._mws-chev{color:#9ca3af;font-size:18px}' +
      '._mws-lbl{font-size:.72rem;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:.03rem;margin:4px 0 6px}' +
      '._mws-field{margin-bottom:11px}' +
      '._mws-field label{display:block;font-size:.74rem;font-weight:700;color:#6b7280;margin-bottom:4px}' +
      '._mws-in,._mws-ta,._mws-sel{width:100%;border:1px solid #d1d5db;border-radius:8px;padding:9px 11px;font-size:.9rem;font-family:inherit;color:#111;background:#fff;outline:none}' +
      '._mws-in:focus,._mws-ta:focus,._mws-sel:focus{border-color:#2563eb;box-shadow:0 0 0 3px rgba(37,99,235,.12)}' +
      '._mws-ta{resize:vertical;min-height:74px;line-height:1.45}' +
      '._mws-linkrow{display:flex;align-items:center;gap:7px;font-size:.78rem;color:#6b7280;background:#f3f4f6;border-radius:8px;padding:8px 11px;margin-bottom:12px;overflow:hidden}' +
      '._mws-linkrow span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}' +
      '._mws-go{width:100%;background:#111827;color:#fff;border:none;border-radius:9px;padding:11px;font-weight:700;font-size:.92rem;cursor:pointer;font-family:inherit}' +
      '._mws-go:hover{background:#000}' +
      '._mws-go:disabled{opacity:.6;cursor:default}' +
      '._mws-st{font-size:.82rem;font-weight:700;text-align:center;margin-top:11px;color:#16a34a}' +
      '._mws-st a{color:#2563eb}' +
      '._mws-link{display:flex;gap:8px;align-items:center;background:#f3f4f6;border:1px solid #e5e7eb;border-radius:8px;padding:5px 5px 5px 12px;margin-top:6px}' +
      '._mws-link input{flex:1;border:none;background:none;font-size:.82rem;color:#374151;outline:none;min-width:0}' +
      '._mws-copy{background:#111827;color:#fff;border:none;border-radius:6px;padding:7px 15px;font-weight:700;font-size:.8rem;cursor:pointer;white-space:nowrap}';
    document.head.appendChild(s);
  }

  function close() { if (overlay) { overlay.remove(); overlay = null; } }

  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }

  function shortUrl(u) {
    try { var a = document.createElement('a'); a.href = u; return a.host + a.pathname; }
    catch (e) { return u; }
  }

  // ---- Screen 1: pick a target ------------------------------------------
  function renderPicker(hd, body) {
    hd.innerHTML = '';
    hd.appendChild(el('b', null, 'Share to MiniWeb'));
    var x = el('button', '_mws-x', '&times;'); x.onclick = close; hd.appendChild(x);

    body.innerHTML = '';
    body.appendChild(el('div', '_mws-lbl', 'Share to a site'));
    TARGETS.forEach(function (t) {
      var b = el('button', '_mws-tgt');
      b.type = 'button';
      b.innerHTML = '<span class="_mws-ic" style="background:' + t.color + '">' + t.icon + '</span>' +
        '<span class="_mws-tt"><span class="_mws-tl">' + t.label + '</span><span class="_mws-ts">' + t.sub + '</span></span>' +
        '<span class="_mws-chev">&rsaquo;</span>';
      b.addEventListener('click', function () { renderCompose(hd, body, t); });
      body.appendChild(b);
    });

    body.appendChild(el('div', '_mws-lbl', 'Or copy link')).style.marginTop = '12px';
    var link = el('div', '_mws-link');
    var input = el('input'); input.readOnly = true; input.value = current.url;
    input.addEventListener('click', function () { this.select(); });
    var copy = el('button', '_mws-copy', 'Copy');
    copy.addEventListener('click', function () {
      navigator.clipboard.writeText(current.url).then(function () {
        copy.textContent = 'Copied!'; setTimeout(function () { copy.textContent = 'Copy'; }, 1500);
      }).catch(function () { input.select(); });
    });
    link.appendChild(input); link.appendChild(copy); body.appendChild(link);
  }

  // ---- Screen 2: edit + send --------------------------------------------
  function renderCompose(hd, body, t) {
    hd.innerHTML = '';
    var back = el('button', '_mws-back', '&larr;');
    back.title = 'Back';
    back.onclick = function () { renderPicker(hd, body); };
    hd.appendChild(back);
    hd.appendChild(el('b', null, 'Share to ' + t.label));
    var x = el('button', '_mws-x', '&times;'); x.onclick = close; hd.appendChild(x);

    body.innerHTML = '';
    var fields = {};   // key -> input element

    function addField(key, label, kind, value) {
      var wrap = el('div', '_mws-field');
      wrap.appendChild(el('label', null, label));
      var inp;
      if (kind === 'textarea') { inp = el('textarea', '_mws-ta'); inp.value = value || ''; }
      else if (kind === 'select') { inp = el('select', '_mws-sel'); }
      else { inp = el('input', '_mws-in'); inp.type = 'text'; inp.value = value || ''; }
      wrap.appendChild(inp); body.appendChild(wrap);
      fields[key] = inp;
      return inp;
    }

    if (t.key === 'forum') {
      addField('title', 'Title', 'text', current.title);
      addField('text', 'Add text (optional)', 'textarea', '');
    } else if (t.key === 'pix') {
      addField('title', 'Caption', 'textarea', current.title);
    } else if (t.key === 'msg') {
      var sel = addField('conversation_id', 'To', 'select');
      sel.innerHTML = '<option>Loading chats…</option>'; sel.disabled = true;
      addField('text', 'Message', 'textarea', current.title + '\n' + current.url);
      fetch(t.recipients).then(function (r) { return r.json(); }).then(function (d) {
        sel.innerHTML = '';
        var list = (d && d.targets) || [];
        if (!list.length) { sel.innerHTML = '<option value="">No chats available</option>'; return; }
        list.forEach(function (c) {
          var o = document.createElement('option'); o.value = c.id; o.textContent = c.name; sel.appendChild(o);
        });
        sel.disabled = false;
      }).catch(function () { sel.innerHTML = '<option value="">Could not load chats</option>'; });
    }

    // Link line (read-only context)
    var lr = el('div', '_mws-linkrow', '🔗 <span>' + shortUrl(current.url) + '</span>');
    body.appendChild(lr);

    var status = el('div', '_mws-st'); status.style.display = 'none';
    var go = el('button', '_mws-go', 'Share to ' + t.label);
    go.addEventListener('click', function () {
      var payload = { title: current.title, url: current.url, text: '' };
      Object.keys(fields).forEach(function (k) { payload[k] = fields[k].value; });
      go.disabled = true; status.style.display = 'block'; status.style.color = '#6b7280'; status.textContent = 'Sharing…';
      fetch(t.endpoint, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      }).then(function (r) { return r.json(); }).then(function (d) {
        if (d && d.ok) {
          status.style.color = '#16a34a';
          status.innerHTML = '✓ Shared to ' + t.label + ' · <a href="' + d.view_url + '">View</a>';
          go.textContent = 'Shared';
        } else {
          status.style.color = '#dc2626';
          status.textContent = (d && d.error) ? d.error : 'Failed to share';
          go.disabled = false;
        }
      }).catch(function () {
        status.style.color = '#dc2626'; status.textContent = 'Failed to share'; go.disabled = false;
      });
    });
    body.appendChild(go);
    body.appendChild(status);

    // Focus the first editable field.
    var first = fields.title || fields.text;
    if (first) { first.focus(); if (first.select) first.select(); }
  }

  function open(opts) {
    opts = opts || {};
    current.title = opts.title || document.title || 'Shared link';
    current.url = opts.url || window.location.href;
    css(); close();

    overlay = el('div', '_mws-ov');
    overlay.addEventListener('click', function (e) { if (e.target === overlay) close(); });
    var win = el('div', '_mws-win');
    var hd = el('div', '_mws-hd');
    var body = el('div', '_mws-body');
    win.appendChild(hd); win.appendChild(body); overlay.appendChild(win);
    document.body.appendChild(overlay);
    renderPicker(hd, body);
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
