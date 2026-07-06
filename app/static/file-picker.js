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

  function getFilesForInput(input) {
    var allowed = parseAccept(input.getAttribute('accept'));
    if (!allowed) return FILES;
    return FILES.filter(function (f) { return f.ext.some(function (e) { return allowed.has(e); }); });
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

  // --- Intercept ---
  document.addEventListener('click', function (e) {
    var input = e.target.closest('input[type="file"]');
    if (input) {
      e.preventDefault();
      e.stopPropagation();
      show(input);
    }
  }, true);

})();
