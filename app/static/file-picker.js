/**
 * Simulated file picker — intercepts <input type="file"> clicks and shows
 * a centered window-like popup with fake file options.
 * Injected globally into all /sites/* pages via app/__init__.py.
 */
(function () {
  'use strict';

  var FILES = [
    { name: 'resume.pdf',      type: 'application/pdf',  ext: ['.pdf'],            content: '%PDF-1.4 simulated resume content' },
    { name: 'paper.pdf',       type: 'application/pdf',  ext: ['.pdf'],            content: '%PDF-1.4 simulated research paper' },
    { name: 'report.pdf',      type: 'application/pdf',  ext: ['.pdf'],            content: '%PDF-1.4 simulated report document' },
    { name: 'letter.docx',     type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', ext: ['.doc', '.docx'], content: 'PK simulated cover letter' },
    { name: 'document.docx',   type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', ext: ['.doc', '.docx'], content: 'PK simulated document' },
    { name: 'notes.txt',       type: 'text/plain',       ext: ['.txt'],            content: 'Meeting notes from project discussion.\n- Action items reviewed\n- Timeline updated' },
    { name: 'readme.txt',      type: 'text/plain',       ext: ['.txt'],            content: 'README\n\nProject overview and setup instructions.' },
    { name: 'data.csv',        type: 'text/csv',         ext: ['.csv'],            content: 'name,email,role\nAlice,alice@example.com,admin\nBob,bob@example.com,user\nCharlie,charlie@example.com,editor' },
    { name: 'contacts.csv',    type: 'text/csv',         ext: ['.csv'],            content: 'first,last,phone\nJohn,Doe,555-0101\nJane,Smith,555-0102' },
    { name: 'config.json',     type: 'application/json', ext: ['.json'],           content: '{"app": "MiniWeb", "version": "1.0", "debug": false}' },
    { name: 'export.json',     type: 'application/json', ext: ['.json'],           content: '[{"id": 1, "title": "Item 1"}, {"id": 2, "title": "Item 2"}]' },
    { name: 'paper.tex',       type: 'application/x-tex',ext: ['.tex'],            content: '\\documentclass{article}\n\\title{Research Paper}\n\\begin{document}\n\\maketitle\n\\end{document}' },
    { name: 'photo.jpg',       type: 'image/jpeg',       ext: ['.jpg', '.jpeg'],   content: 'JFIF simulated photo' },
    { name: 'screenshot.png',  type: 'image/png',        ext: ['.png'],            content: 'PNG simulated screenshot' },
    { name: 'profile.jpg',     type: 'image/jpeg',       ext: ['.jpg', '.jpeg'],   content: 'JFIF simulated profile picture' },
    { name: 'clip.mp4',        type: 'video/mp4',        ext: ['.mp4'],            content: 'ftyp simulated video clip' },
  ];

  var ICONS = {
    '.pdf': '\ud83d\udcc4', '.doc': '\ud83d\udcc3', '.docx': '\ud83d\udcc3',
    '.txt': '\ud83d\udcdd', '.csv': '\ud83d\udcca', '.json': '\u2699\ufe0f',
    '.tex': '\ud83d\udcdc', '.jpg': '\ud83d\uddbc\ufe0f', '.jpeg': '\ud83d\uddbc\ufe0f',
    '.png': '\ud83d\uddbc\ufe0f', '.mp4': '\ud83c\udfac',
  };

  var WILDCARD_MAP = {
    'image/*': ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'],
    'video/*': ['.mp4', '.webm', '.avi', '.mov'],
    'audio/*': ['.mp3', '.wav', '.ogg'],
  };

  // --- Downloaded files: files the user downloads are added to the simulated
  // explorer (persisted in localStorage) so they can be re-selected/uploaded. ---
  var STORE_KEY = '_miniweb_downloaded_files';
  var TYPE_BY_EXT = {
    '.pdf': 'application/pdf', '.csv': 'text/csv', '.json': 'application/json',
    '.txt': 'text/plain', '.doc': 'application/msword',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.mp4': 'video/mp4', '.zip': 'application/zip', '.tar': 'application/x-tar',
    '.gz': 'application/gzip', '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  };
  function extOf(name) { var m = /\.[a-z0-9]+$/i.exec(name || ''); return m ? m[0].toLowerCase() : ''; }
  function loadStored() { try { return JSON.parse(localStorage.getItem(STORE_KEY)) || []; } catch (e) { return []; } }
  function saveStored(a) { try { localStorage.setItem(STORE_KEY, JSON.stringify(a.slice(-40))); } catch (e) {} }
  function stubContent(ext, name) {
    if (ext === '.pdf') return '%PDF-1.4 simulated downloaded document: ' + name;
    if (ext === '.csv') return 'id,name,value\n1,sample,100\n2,sample,200';
    if (ext === '.json') return '{"downloaded": true, "name": "' + name + '"}';
    return 'Simulated downloaded file: ' + name;
  }
  function addDownloadedFile(name) {
    if (!name) return;
    var ext = extOf(name);
    var stored = loadStored();
    if (stored.some(function (f) { return f.name === name; })) return;  // dedupe
    stored.push({
      name: name, type: TYPE_BY_EXT[ext] || 'application/octet-stream',
      ext: [ext || '.bin'], content: stubContent(ext, name), downloaded: true,
    });
    saveStored(stored);
  }
  // Expose for pages that trigger downloads programmatically.
  window.MiniWebFiles = { add: addDownloadedFile, listDownloaded: loadStored };

  function parseAccept(accept) {
    if (!accept) return null;
    var parts = accept.split(',').map(function (s) { return s.trim().toLowerCase(); });
    var exts = new Set();
    parts.forEach(function (p) {
      if (WILDCARD_MAP[p]) { WILDCARD_MAP[p].forEach(function (e) { exts.add(e); }); }
      else if (p.startsWith('.')) { exts.add(p); }
      else if (p.includes('/')) {
        FILES.forEach(function (f) { if (f.type === p) f.ext.forEach(function (e) { exts.add(e); }); });
      }
    });
    return exts.size > 0 ? exts : null;
  }

  function allFiles() {
    // Downloaded files first so they're easy to find at the top.
    return loadStored().concat(FILES);
  }
  function getFilesForInput(input) {
    var all = allFiles();
    var allowed = parseAccept(input.getAttribute('accept'));
    if (!allowed) return all;
    return all.filter(function (f) { return f.ext.some(function (e) { return allowed.has(e); }); });
  }

  function selectFile(input, file) {
    var blob = new Blob([file.content], { type: file.type });
    var fileObj = new File([blob], file.name, { type: file.type });
    var dt = new DataTransfer();
    dt.items.add(fileObj);
    input.files = dt.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }

  // --- Dialog ---
  var overlay = null;

  function close() {
    if (overlay) { overlay.remove(); overlay = null; }
  }

  function show(input) {
    close();
    var files = getFilesForInput(input);
    if (!files.length) return;

    overlay = document.createElement('div');
    overlay.className = '_fp-overlay';

    var win = document.createElement('div');
    win.className = '_fp-win';

    // Title bar
    var bar = document.createElement('div');
    bar.className = '_fp-bar';
    bar.innerHTML = '<span>Open File</span>';
    var xBtn = document.createElement('button');
    xBtn.className = '_fp-x';
    xBtn.textContent = '\u00d7';
    xBtn.onclick = close;
    bar.appendChild(xBtn);
    win.appendChild(bar);

    // File list
    var list = document.createElement('div');
    list.className = '_fp-list';
    files.forEach(function (f) {
      var row = document.createElement('button');
      row.className = '_fp-row';
      row.type = 'button';
      var icon = ICONS[f.ext[0]] || '\ud83d\udcc1';
      row.innerHTML = '<span class="_fp-icon">' + icon + '</span><span class="_fp-name">' + f.name + '</span>';
      row.addEventListener('click', function () {
        selectFile(input, f);
        close();
      });
      list.appendChild(row);
    });
    win.appendChild(list);

    overlay.appendChild(win);
    document.body.appendChild(overlay);

    // Close on overlay click (not window)
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) close();
    });
  }

  // --- Styles ---
  var css = document.createElement('style');
  css.textContent =
    '._fp-overlay{position:fixed;inset:0;background:rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;z-index:999999;font-family:-apple-system,BlinkMacSystemFont,sans-serif}' +
    '._fp-win{background:#fff;border-radius:10px;box-shadow:0 8px 40px rgba(0,0,0,.25);width:300px;max-height:400px;display:flex;flex-direction:column;overflow:hidden}' +
    '._fp-bar{display:flex;align-items:center;justify-content:space-between;padding:.6rem 1rem;background:#f5f5f5;border-bottom:1px solid #e0e0e0}' +
    '._fp-bar span{font-size:.85rem;font-weight:600;color:#333}' +
    '._fp-x{border:none;background:none;font-size:1.2rem;color:#999;cursor:pointer;padding:0 .2rem;line-height:1}' +
    '._fp-x:hover{color:#333}' +
    '._fp-list{overflow-y:auto;padding:.4rem}' +
    '._fp-row{display:flex;align-items:center;gap:.6rem;width:100%;padding:.5rem .7rem;border:none;background:none;text-align:left;border-radius:6px;cursor:pointer;font-family:inherit;font-size:.85rem;color:#333}' +
    '._fp-row:hover{background:#e8f0fe}' +
    '._fp-icon{font-size:1.1rem;flex-shrink:0;width:1.4rem;text-align:center}' +
    '._fp-name{flex:1}';
  document.head.appendChild(css);

  // --- Intercept file inputs (upload picker) ---
  document.addEventListener('click', function (e) {
    var input = e.target.closest('input[type="file"]');
    if (input) {
      e.preventDefault();
      e.stopPropagation();
      show(input);
    }
  }, true);

  // --- Register downloads into the simulated explorer ---
  function savedToast(name) {
    var t = document.createElement('div');
    t.textContent = '✓ Saved ' + name + ' to Files';
    t.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#323232;color:#fff;padding:10px 18px;border-radius:8px;font:600 13px -apple-system,sans-serif;z-index:1000000;box-shadow:0 4px 16px rgba(0,0,0,.3)';
    document.body.appendChild(t);
    setTimeout(function () { t.style.opacity = '0'; t.style.transition = 'opacity .4s'; }, 1800);
    setTimeout(function () { t.remove(); }, 2400);
  }
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
    var name = a.getAttribute('download') || a.getAttribute('data-download-name');
    if (!name) name = filenameFromHref(a.getAttribute('href') || '');
    if (!name) {  // export links without a filename in the URL
      var href = a.getAttribute('href') || '';
      var fmt = (href.match(/format=([a-z0-9]+)/i) || [])[1];
      if (fmt) name = 'export.' + fmt;
    }
    if (name) { addDownloadedFile(name); savedToast(name); }
    // Do NOT preventDefault — let the real download proceed.
  }, false);

})();
