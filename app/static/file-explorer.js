/**
 * Universal simulated file explorer (macOS Finder / Windows Explorer style).
 *
 * Replaces the old flat file-picker. Talks to the server-backed virtual
 * filesystem at /_fs/*. Injected globally into every /sites/* page.
 *
 *  · Intercepts <input type="file"> clicks  → OPEN mode (pick a real seeded file,
 *    fetch its bytes, set input.files).
 *  · Intercepts download / export links     → SAVE-AS mode (choose folder + name,
 *    POST /_fs/save — the gradeable backend gate; the file then appears in the FS).
 *  · window.MiniWebFS.open({accept, onPick}) / .saveAs({name, content, origin})
 *    let pages (WebMail attach, dating photos) drive it programmatically.
 *  · window.MiniWebFiles kept as a thin back-compat alias.
 */
(function () {
  'use strict';

  var FS = '/_fs';

  // ── icons ──────────────────────────────────────────────────────────────
  var EXT_ICON = {
    '.pdf': '📄', '.doc': '📃', '.docx': '📃',
    '.txt': '📝', '.md': '📝', '.csv': '📊',
    '.xlsx': '📈', '.json': '⚙️', '.png': '🖼️',
    '.jpg': '🖼️', '.jpeg': '🖼️', '.gif': '🖼️',
    '.svg': '🖼️', '.mp4': '🎬', '.mp3': '🎵',
    '.zip': '🗜️', '.pptx': '📑',
  };
  var FAV_ICON = {
    desktop: '🖥️', documents: '📁', downloads: '⬇️',
    pictures: '🖼️', music: '🎵', movies: '🎬',
  };
  function iconFor(it) {
    if (it.kind === 'folder') return '📁';
    return EXT_ICON[it.ext] || '📄';
  }
  function fmtSize(n) {
    if (!n) return '--';
    if (n < 1024) return n + ' B';
    if (n < 1048576) return (n / 1024).toFixed(0) + ' KB';
    return (n / 1048576).toFixed(1) + ' MB';
  }
  function extOf(name) { var m = /\.[a-z0-9]+$/i.exec(name || ''); return m ? m[0].toLowerCase() : ''; }

  // ── styles ─────────────────────────────────────────────────────────────
  var css = document.createElement('style');
  css.textContent =
    // Defensive reset: the explorer is injected into arbitrary sites whose global
    // `button{}` / `input{}` rules (width:100%, margins, padding, transforms) would
    // otherwise bleed into these controls and break the layout. Neutralize them.
    '._fe-overlay button,._fe-overlay input{margin:0 !important;min-width:0 !important;min-height:0 !important;box-shadow:none !important;text-transform:none !important;letter-spacing:normal !important;line-height:normal !important;float:none !important;position:static !important;transform:none !important}' +
    '._fe-overlay *{box-sizing:border-box}' +
    '._fe-overlay{position:fixed;inset:0;background:rgba(0,0,0,.32);display:flex;align-items:center;justify-content:center;z-index:2147483000;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}' +
    '._fe-win{width:720px;max-width:94vw;height:480px;max-height:88vh;background:#f6f6f7;border-radius:12px;box-shadow:0 24px 70px rgba(0,0,0,.4);display:flex;flex-direction:column;overflow:hidden}' +
    '._fe-title{height:38px;flex:none;display:flex;align-items:center;gap:8px;padding:0 12px;background:linear-gradient(#ececee,#e2e2e5);border-bottom:1px solid #d0d0d4}' +
    '._fe-lights{display:flex;gap:7px}' +
    '._fe-light{width:12px;height:12px;border-radius:50%}' +
    '._fe-red{background:#ff5f57}._fe-yellow{background:#febc2e}._fe-green{background:#28c840}' +
    '._fe-title-txt{flex:1;text-align:center;font-size:13px;font-weight:600;color:#4a4a4f}' +
    '._fe-body{flex:1;display:flex;min-height:0}' +
    '._fe-side{width:168px;flex:none;background:#ececed;border-right:1px solid #dcdce0;padding:10px 8px;overflow-y:auto}' +
    '._fe-side-h{font-size:11px;font-weight:700;color:#9a9aa0;text-transform:uppercase;letter-spacing:.04em;padding:4px 8px}' +
    '._fe-fav{display:flex;align-items:center;gap:8px;padding:6px 8px;border-radius:6px;font-size:13px;color:#333;cursor:pointer}' +
    '._fe-fav:hover{background:#dedee2}._fe-fav.active{background:#d3e3fb;color:#1a5fd6}' +
    '._fe-main{flex:1;display:flex;flex-direction:column;min-width:0;background:#fff}' +
    '._fe-toolbar{height:40px;flex:none;display:flex;align-items:center;gap:8px;padding:0 12px;border-bottom:1px solid #ececec;background:#fafafa}' +
    '._fe-back{border:none;background:#eee;border-radius:6px;width:26px !important;height:26px !important;padding:0 !important;flex:none;cursor:pointer;font-size:14px;color:#555;display:flex;align-items:center;justify-content:center}' +
    '._fe-back:disabled{opacity:.4;cursor:default}' +
    '._fe-crumbs{flex:1;font-size:12.5px;color:#666;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}' +
    '._fe-crumbs b{color:#333}._fe-crumbs .c{cursor:pointer}._fe-crumbs .c:hover{text-decoration:underline}' +
    '._fe-list{flex:1;overflow-y:auto;padding:8px}' +
    '._fe-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:6px}' +
    '._fe-item{display:flex;flex-direction:column;align-items:center;gap:5px;padding:10px 6px;border-radius:8px;cursor:pointer;text-align:center;border:1.5px solid transparent}' +
    '._fe-item:hover{background:#f2f6fd}._fe-item.sel{background:#d3e3fb;border-color:#a9c9f5}' +
    '._fe-ic{font-size:30px;line-height:1}' +
    '._fe-nm{font-size:11.5px;color:#333;word-break:break-word;max-width:100%;line-height:1.25}' +
    '._fe-meta{font-size:10px;color:#999}' +
    '._fe-empty{color:#aaa;font-size:13px;text-align:center;padding:40px 0}' +
    '._fe-foot{height:52px;flex:none;display:flex;align-items:center;gap:8px;padding:0 14px;border-top:1px solid #e6e6e6;background:#f6f6f7}' +
    '._fe-fname{flex:1;width:auto !important;min-width:0;padding:7px 10px !important;border:1px solid #cfcfd4;border-radius:7px;font-size:13px}' +
    '._fe-sel-name{flex:1;font-size:12.5px;color:#666;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}' +
    '._fe-btn{border:none;border-radius:7px;padding:7px 16px !important;width:auto !important;flex:none;font-size:13px;font-weight:600;cursor:pointer}' +
    '._fe-btn-p{background:#2f7cf6;color:#fff}._fe-btn-p:disabled{background:#a9c3f0;cursor:default}' +
    '._fe-btn-s{background:#e6e6ea;color:#444}';
  (document.head || document.documentElement).appendChild(css);

  // ── dialog state ────────────────────────────────────────────────────────
  var overlay = null, st = null;

  function close() { if (overlay) { overlay.remove(); overlay = null; st = null; } }

  function acceptAllows(item, accept) {
    if (item.kind === 'folder') return true;
    if (!accept || !accept.length) return true;
    return accept.indexOf(item.ext) !== -1 ||
           accept.some(function (a) {
             if (a === 'image/*') return ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'].indexOf(item.ext) !== -1;
             if (a === 'video/*') return ['.mp4', '.webm', '.mov'].indexOf(item.ext) !== -1;
             if (a === 'audio/*') return ['.mp3', '.wav', '.ogg'].indexOf(item.ext) !== -1;
             return false;
           });
  }

  function parseAccept(raw) {
    if (!raw) return [];
    return raw.split(',').map(function (s) { return s.trim().toLowerCase(); }).filter(Boolean);
  }

  function render() {
    var b = overlay.querySelector('._fe-list');
    var items = st.items.filter(function (it) { return acceptAllows(it, st.accept); });
    if (!items.length) { b.innerHTML = '<div class="_fe-empty">This folder is empty</div>'; return; }
    var g = document.createElement('div'); g.className = '_fe-grid';
    items.forEach(function (it) {
      var el = document.createElement('div');
      el.className = '_fe-item' + (st.selected && st.selected.path === it.path ? ' sel' : '');
      el.innerHTML = '<div class="_fe-ic">' + iconFor(it) + '</div>' +
        '<div class="_fe-nm">' + it.name + '</div>' +
        '<div class="_fe-meta">' + (it.kind === 'folder' ? 'Folder' : fmtSize(it.size)) + '</div>';
      el.addEventListener('click', function () {
        if (it.kind === 'folder') { navigate(it.path); return; }
        st.selected = it;
        if (st.mode === 'save') { overlay.querySelector('._fe-fname').value = it.name; }
        render(); syncFooter();
      });
      el.addEventListener('dblclick', function () {
        if (it.kind === 'folder') { navigate(it.path); }
        else if (st.mode === 'open') { st.selected = it; confirmPick(); }
      });
      g.appendChild(el);
    });
    b.innerHTML = ''; b.appendChild(g);
  }

  function renderCrumbs() {
    var c = overlay.querySelector('._fe-crumbs');
    var parts = st.path === '/' ? [] : st.path.split('/').filter(Boolean);
    var html = '<span class="c" data-p="/">💻 Macintosh</span>';
    var acc = '';
    parts.forEach(function (p, i) {
      acc += '/' + p;
      var last = i === parts.length - 1;
      html += ' › ' + (last ? '<b>' + p + '</b>' : '<span class="c" data-p="' + acc + '">' + p + '</span>');
    });
    c.innerHTML = html;
    c.querySelectorAll('.c').forEach(function (s) {
      s.addEventListener('click', function () { navigate(s.getAttribute('data-p')); });
    });
    overlay.querySelector('._fe-back').disabled = st.path === '/';
  }

  function syncFooter() {
    if (st.mode === 'open') {
      overlay.querySelector('._fe-sel-name').textContent = st.selected ? st.selected.name : 'No file selected';
      overlay.querySelector('._fe-ok').disabled = !st.selected;
    }
  }

  function navigate(path) {
    st.path = path || '/';
    fetch(FS + '/list?path=' + encodeURIComponent(st.path))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        st.items = d.items || [];
        st.selected = null;
        // highlight matching favorite
        overlay.querySelectorAll('._fe-fav').forEach(function (f) {
          f.classList.toggle('active', st.path === f.getAttribute('data-p') ||
            st.path.indexOf(f.getAttribute('data-p') + '/') === 0);
        });
        renderCrumbs(); render(); syncFooter();
      });
  }

  function build(favorites) {
    close();
    overlay = document.createElement('div');
    overlay.className = '_fe-overlay';
    var favHtml = (favorites || []).map(function (f) {
      return '<div class="_fe-fav" data-p="' + f.path + '"><span>' +
        (FAV_ICON[f.icon] || '📁') + '</span><span>' + f.name + '</span></div>';
    }).join('');
    var footer = st.mode === 'save'
      ? '<span style="font-size:12.5px;color:#666">Save As:</span>' +
        '<input class="_fe-fname" value="' + (st.saveName || 'untitled') + '">' +
        '<button class="_fe-btn _fe-btn-s _fe-cancel">Cancel</button>' +
        '<button class="_fe-btn _fe-btn-p _fe-ok">Save</button>'
      : '<span class="_fe-sel-name">No file selected</span>' +
        '<button class="_fe-btn _fe-btn-s _fe-cancel">Cancel</button>' +
        '<button class="_fe-btn _fe-btn-p _fe-ok" disabled>Open</button>';
    overlay.innerHTML =
      '<div class="_fe-win">' +
        '<div class="_fe-title"><div class="_fe-lights"><span class="_fe-light _fe-red"></span>' +
          '<span class="_fe-light _fe-yellow"></span><span class="_fe-light _fe-green"></span></div>' +
          '<div class="_fe-title-txt">' + (st.mode === 'save' ? 'Save' : 'Open') + '</div>' +
          '<div style="width:52px"></div></div>' +
        '<div class="_fe-body">' +
          '<div class="_fe-side"><div class="_fe-side-h">Favorites</div>' + favHtml + '</div>' +
          '<div class="_fe-main">' +
            '<div class="_fe-toolbar"><button class="_fe-back">‹</button>' +
              '<div class="_fe-crumbs"></div></div>' +
            '<div class="_fe-list"></div>' +
            '<div class="_fe-foot">' + footer + '</div>' +
          '</div>' +
        '</div>' +
      '</div>';
    document.body.appendChild(overlay);
    overlay.querySelector('._fe-red').addEventListener('click', close);
    overlay.querySelector('._fe-cancel').addEventListener('click', close);
    overlay.querySelector('._fe-back').addEventListener('click', function () {
      var p = st.path.replace(/\/[^/]+$/, '') || '/'; navigate(p);
    });
    overlay.querySelectorAll('._fe-fav').forEach(function (f) {
      f.addEventListener('click', function () { navigate(f.getAttribute('data-p')); });
    });
    overlay.querySelector('._fe-ok').addEventListener('click', function () {
      if (st.mode === 'save') { confirmSave(); } else { confirmPick(); }
    });
    overlay.addEventListener('click', function (e) { if (e.target === overlay) close(); });
  }

  function openDialog(opts) {
    st = {
      mode: opts.mode || 'open', accept: opts.accept || [],
      saveName: opts.saveName || 'untitled', saveContent: opts.saveContent || '',
      saveOrigin: opts.saveOrigin || 'download', onPick: opts.onPick || null,
      onSave: opts.onSave || null, path: '/', items: [], selected: null,
    };
    fetch(FS + '/list?path=/')
      .then(function (r) { return r.json(); })
      .then(function (d) {
        build(d.favorites);
        navigate(opts.startPath || (st.mode === 'save' ? '/Downloads' : '/Documents'));
      });
  }

  function confirmPick() {
    if (!st.selected) return;
    var it = st.selected, cb = st.onPick, input = st.input;
    fetch(FS + '/file?path=' + encodeURIComponent(it.path))
      .then(function (r) { return r.json(); })
      .then(function (f) {
        // advisory server trail
        fetch(FS + '/upload', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: it.path }) }).catch(function () {});
        var finish = function (fileObj) {
          if (input && fileObj) {
            var dt = new DataTransfer(); dt.items.add(fileObj);
            try { input.files = dt.files; } catch (e) {}
            input.dispatchEvent(new Event('change', { bubbles: true }));
            input.dispatchEvent(new Event('input', { bubbles: true }));
          }
          if (cb) cb({ path: f.path, name: f.name, mime: f.mime, size: f.size, content: f.content || '' });
          close();
        };
        if (input) {
          // Fetch the real bytes so binary files (images, PDFs you drop in) attach
          // correctly — not just the text content.
          fetch(FS + '/download?path=' + encodeURIComponent(it.path))
            .then(function (r) { return r.blob(); })
            .then(function (blob) { finish(new File([blob], f.name, { type: f.mime || blob.type || 'application/octet-stream' })); })
            .catch(function () { finish(new File([f.content || ''], f.name, { type: f.mime || 'application/octet-stream' })); });
        } else {
          finish(null);
        }
      });
  }

  function confirmSave() {
    var name = overlay.querySelector('._fe-fname').value.trim() || 'untitled';
    var folder = st.path;
    fetch(FS + '/save', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name, folder: folder, content: st.saveContent,
        origin: st.saveOrigin }) })
      .then(function (r) { return r.json(); })
      .then(function (res) {
        toast('✓ Saved “' + name + '” to ' + (folder.split('/').pop() || 'Macintosh'));
        if (st.onSave) st.onSave(res.file || { name: name, folder: folder });
        close();
      })
      .catch(function () { close(); });
  }

  function toast(msg) {
    var t = document.createElement('div');
    t.textContent = msg;
    t.style.cssText = 'position:fixed;bottom:22px;left:50%;transform:translateX(-50%);background:#323232;color:#fff;padding:10px 18px;border-radius:8px;font:600 13px -apple-system,sans-serif;z-index:2147483001;box-shadow:0 4px 16px rgba(0,0,0,.3)';
    document.body.appendChild(t);
    setTimeout(function () { t.style.opacity = '0'; t.style.transition = 'opacity .4s'; }, 1900);
    setTimeout(function () { t.remove(); }, 2500);
  }

  // ── public API ──────────────────────────────────────────────────────────
  window.MiniWebFS = {
    open: function (o) {
      o = o || {};
      openDialog({ mode: 'open', accept: parseAccept(o.accept), onPick: o.onPick,
        startPath: o.startPath });
    },
    saveAs: function (o) {
      o = o || {};
      st = null;
      openDialog({ mode: 'save', saveName: o.name || 'untitled', saveContent: o.content || '',
        saveOrigin: o.origin || 'download', onSave: o.onSave, startPath: o.startPath });
    },
  };
  // back-compat shim for pages that referenced the old picker.
  window.MiniWebFiles = {
    add: function (name) {
      if (name) fetch(FS + '/save', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name, folder: '/Downloads', origin: 'legacy' }) }).catch(function () {});
    },
  };

  // ── intercept <input type=file> → OPEN ───────────────────────────────────
  // Open the picker where the requested files actually live, so a media picker
  // doesn't strand the user in Documents. Mixed media (image+video) → root, so
  // every folder is one click away and you're never "stuck".
  function startPathForAccept(accept) {
    if (!accept || !accept.length) return null;  // general files → default (Documents)
    var img = accept.some(function (a) { return a === 'image/*' || ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.heic'].indexOf(a) >= 0; });
    var vid = accept.some(function (a) { return a === 'video/*' || ['.mp4', '.webm', '.mov', '.avi', '.mkv', '.m4v'].indexOf(a) >= 0; });
    var aud = accept.some(function (a) { return a === 'audio/*' || ['.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac'].indexOf(a) >= 0; });
    if ((img ? 1 : 0) + (vid ? 1 : 0) + (aud ? 1 : 0) > 1) return '/';  // mixed → root
    if (img) return '/Pictures';
    if (vid) return '/Movies';
    if (aud) return '/Music';
    return null;
  }
  document.addEventListener('click', function (e) {
    var input = e.target.closest('input[type="file"]');
    if (!input) return;
    e.preventDefault(); e.stopPropagation();
    var accept = parseAccept(input.getAttribute('accept'));
    openDialog({ mode: 'open', accept: accept, startPath: startPathForAccept(accept) });
    // stash the input so confirmPick can set its files
    var poll = setInterval(function () { if (st) { st.input = input; clearInterval(poll); } }, 10);
    setTimeout(function () { clearInterval(poll); }, 2000);
  }, true);

  // ── intercept download / export links → SAVE-AS ──────────────────────────
  function filenameFromHref(href) {
    try {
      var path = href.split('?')[0].split('#')[0];
      var last = path.split('/').filter(Boolean).pop() || '';
      return /\.[a-z0-9]+$/i.test(last) ? decodeURIComponent(last) : '';
    } catch (e) { return ''; }
  }
  document.addEventListener('click', function (e) {
    var a = e.target.closest('a[download], a[href*="/download"], a[href*="export"][href*="format="], [data-download-name]');
    if (!a) return;
    var name = a.getAttribute('download') || a.getAttribute('data-download-name') || '';
    var href = a.getAttribute('href') || '';
    if (!name) name = filenameFromHref(href);
    if (!name) {
      var fmt = (href.match(/format=([a-z0-9]+)/i) || [])[1];
      if (fmt) name = 'export.' + fmt;
    }
    if (!name) return;  // not a recognizable file download — let it proceed
    e.preventDefault(); e.stopPropagation();
    var origin = (location.pathname.split('/')[2] || 'download');
    var chip = downloadChip(name);
    // Realistic browser download: fetch the real bytes (binary-safe) and save to
    // Downloads, with a progress chip. Text stays text; binary rides base64.
    var save = function (body) {
      body.name = name; body.folder = '/Downloads'; body.origin = origin;
      fetch(FS + '/save', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body) })
        .then(function (r) { return r.json(); })
        .then(function () { chip.done(); })
        .catch(function () { chip.fail(); });
    };
    if (href && href.indexOf('javascript:') !== 0) {
      fetch(href, { credentials: 'same-origin' })
        .then(function (r) { return r.blob(); })
        .then(function (blob) {
          var mime = blob.type || '';
          var textish = (/^text\/|json|csv|xml|svg|javascript|x-www-form/.test(mime) || mime === '');
          if (textish && blob.size < 500000) {
            blob.text().then(function (t) { save({ content: t, mime: mime }); });
          } else {
            blobToB64(blob).then(function (b64) { save({ content_b64: b64, mime: mime }); });
          }
        })
        .catch(function () { save({ content: '' }); });
    } else { save({ content: '' }); }
  }, true);

  function blobToB64(blob) {
    return new Promise(function (resolve) {
      var r = new FileReader();
      r.onload = function () { resolve((r.result.split(',')[1]) || ''); };
      r.onerror = function () { resolve(''); };
      r.readAsDataURL(blob);
    });
  }

  // Browser-style download shelf chip (bottom-left), with a progress sweep.
  function downloadChip(name) {
    var el = document.createElement('div');
    el.style.cssText = 'position:fixed;bottom:18px;left:18px;min-width:220px;max-width:300px;background:#fff;color:#1f2937;border:1px solid #e2e6ea;border-radius:8px;box-shadow:0 6px 24px rgba(0,0,0,.18);padding:10px 12px;font:500 12.5px -apple-system,BlinkMacSystemFont,sans-serif;z-index:2147483002;';
    el.innerHTML =
      '<div style="display:flex;align-items:center;gap:8px;"><span class="_dc-ic" style="font-size:16px;">⬇️</span>' +
      '<div style="flex:1;min-width:0;"><div style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + name + '</div>' +
      '<div class="_dc-status" style="font-size:11px;color:#6b7280;">Downloading…</div></div></div>' +
      '<div style="height:3px;background:#eef1f4;border-radius:2px;margin-top:8px;overflow:hidden;">' +
      '<div class="_dc-bar" style="height:100%;width:15%;background:#2f7cf6;border-radius:2px;transition:width .25s ease;"></div></div>';
    document.body.appendChild(el);
    var bar = el.querySelector('._dc-bar');
    var w = 15;
    var iv = setInterval(function () { w = Math.min(w + 12, 90); bar.style.width = w + '%'; }, 180);
    function remove(delay) { setTimeout(function () { el.style.transition = 'opacity .4s'; el.style.opacity = '0'; }, delay); setTimeout(function () { if (el.parentNode) el.remove(); }, delay + 500); }
    return {
      done: function () {
        clearInterval(iv); bar.style.width = '100%'; bar.style.background = '#22a06b';
        el.querySelector('._dc-ic').textContent = '✅';
        el.querySelector('._dc-status').textContent = 'Saved to Downloads';
        remove(2600);
      },
      fail: function () {
        clearInterval(iv); bar.style.background = '#e5484d';
        el.querySelector('._dc-ic').textContent = '⚠️';
        el.querySelector('._dc-status').textContent = 'Download failed';
        remove(2600);
      }
    };
  }

})();
