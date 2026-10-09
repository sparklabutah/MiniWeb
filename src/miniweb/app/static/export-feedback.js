/**
 * Export button feedback — intercepts export link clicks and shows
 * proper download confirmation instead of the flaky setTimeout reset.
 * Injected globally into all /sites/* pages via app/__init__.py.
 */
(function () {
  'use strict';

  // Style for the toast notification
  var css = document.createElement('style');
  css.textContent =
    '._ef-toast{position:fixed;bottom:1.5rem;right:1.5rem;background:#1a7f37;color:#fff;' +
    'padding:.7rem 1.2rem;border-radius:8px;font-size:.88rem;font-weight:600;z-index:999999;' +
    'box-shadow:0 4px 16px rgba(0,0,0,.2);display:flex;align-items:center;gap:.5rem;' +
    'animation:_ef-slide .3s ease}' +
    '@keyframes _ef-slide{from{transform:translateY(20px);opacity:0}to{transform:translateY(0);opacity:1}}';
  document.head.appendChild(css);

  function showToast(filename) {
    // Remove existing toast
    var old = document.querySelector('._ef-toast');
    if (old) old.remove();

    var toast = document.createElement('div');
    toast.className = '_ef-toast';
    toast.innerHTML = '\u2713 Downloaded ' + filename;
    document.body.appendChild(toast);
    setTimeout(function () { toast.remove(); }, 3000);
  }

  document.addEventListener('click', function (e) {
    var link = e.target.closest('a[href*="export"][href*="format="]');
    if (!link) link = e.target.closest('a[href*="export"][href*="csv"]');
    if (!link) link = e.target.closest('a[href*="export"][href*="json"]');
    if (!link) return;

    // Determine filename from URL
    var href = link.getAttribute('href') || '';
    var format = 'csv';
    if (href.indexOf('format=json') !== -1) format = 'json';
    else if (href.indexOf('format=bibtex') !== -1) format = 'bib';

    var type = '';
    var m = href.match(/type=(\w+)/);
    if (m) type = m[1] + '.';

    var filename = 'export_' + type + format;

    // Update button text
    var original = link.textContent;
    link.textContent = 'Downloading...';
    link.style.opacity = '0.7';
    link.style.pointerEvents = 'none';

    // Let the default <a> behavior handle the actual download,
    // then show feedback after a short delay
    setTimeout(function () {
      link.textContent = '\u2713 Downloaded';
      link.style.opacity = '1';
      showToast(filename);
      setTimeout(function () {
        link.textContent = original;
        link.style.pointerEvents = '';
      }, 2000);
    }, 500);
  });

})();
