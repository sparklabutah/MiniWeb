"""Privileged site map: which listing controls each TRAIN site has and how the backend
sees them. Drives parameter sampling (stage 2) and the suggester's context (stage 3);
never reaches the training set.

    crawl   BFS over same-site links (read-only DOM reads; risky paths skipped) and
            collect listing controls on every page:
              select  a visible <select> outside POST forms (≥2 options)
              link    a group of links that set the same sort/order query key
    probe   apply one option per control in a throw-away session (privileged
            select_option / locator click) and read the session request log: the
            request that carries the option's value is the control's backend
            signature {method, path, param}; `apply` records whether the control
            submits itself ("auto") or needs its form's button ("button").
            Controls with no request carrying the value (client-side only) are
            kept but marked unusable — there would be no backend check.

Output: data/datagen/sitemap/<site>.json (cached; --force recrawls).
"""
from __future__ import annotations

import json
import re
import time
from collections import deque
from urllib.parse import urlsplit

from datagen import browser as B
from datagen import config, kinds

SKIP = re.compile(
    r"(logout|log-out|signout|sign-out|delete|remove|destroy|cancel|unsubscribe|reset|clear|"
    r"download|export|print|/api/|/static/|/_|\badd\b|toggle|/like|/follow|/vote|/join|/leave|"
    r"accept|decline|approve|reject|archive|/mark|/star|/pin|/mute|/block|checkout|/pay(/|$)|"
    r"\.(json|csv|pdf|zip|png|jpe?g|gif|svg|ics|txt|xml|mp3|mp4|wav)$)", re.I)
SORT_WORDS = re.compile(r"(^|[^a-z])(sort|order|orderby|sort_by|sortby|ordering)([^a-z]|$)", re.I)
NOT_FILTER = re.compile(r"(per_page|perpage|page_size|pagesize|limit|lang|language|locale|currency|theme|"
                        r"view|layout|density|quantity|qty|timezone)", re.I)

# Read-only DOM scan (no writes, no focus, no scrolling).
_SCAN_JS = r"""
(site) => {
  const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 2 && r.height > 2 && s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity || '1') > 0.05; };
  const txt = s => (s || '').replace(/\s+/g, ' ').trim();
  const uniq = css => { try { return document.querySelectorAll(css).length === 1; } catch (e) { return false; } };
  // form.action is shadowed by a field named "action" (DOM clobbering): read the attribute
  const actionOf = f => { const a = f.getAttribute('action'); try { return new URL(a || location.href, location.href).href; } catch (e) { return location.href; } };
  const cssOf = el => {
    const tag = el.tagName.toLowerCase();
    if (el.id && uniq('#' + CSS.escape(el.id))) return '#' + CSS.escape(el.id);
    const nm = el.getAttribute('name');
    if (nm) { const c = `${tag}[name="${nm}"]`; if (uniq(c)) return c;
      if (el.form && el.form.id) { const c2 = `#${CSS.escape(el.form.id)} ${c}`; if (uniq(c2)) return c2; } }
    const parts = []; let n = el;
    while (n && n.nodeType === 1 && n !== document.body) {
      let p = n.tagName.toLowerCase(); const par = n.parentElement;
      if (par) { const sib = [...par.children].filter(c => c.tagName === n.tagName);
        if (sib.length > 1) p += `:nth-of-type(${sib.indexOf(n) + 1})`; }
      parts.unshift(p); if (n.id) { parts[0] = '#' + CSS.escape(n.id); break; } n = par;
    }
    return parts.join(' > ');
  };
  const labelOf = el => {
    if (el.labels && el.labels.length) { const c = el.labels[0].cloneNode(true);   // detached copy: no page mutation
      c.querySelectorAll('select, option, input, textarea, button').forEach(n => n.remove()); if (txt(c.textContent)) return txt(c.textContent); }
    if (el.getAttribute('aria-label')) return txt(el.getAttribute('aria-label'));
    if (el.title) return txt(el.title);
    let p = el.previousElementSibling;
    if (p && ['LABEL','SPAN','STRONG','B','P','H3','H4','H5','H6','SMALL','DIV'].includes(p.tagName)
        && !p.querySelector('a,button,input,select') && txt(p.innerText).length < 40) return txt(p.innerText);
    const par = el.parentElement;
    if (par) { const clone = [...par.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(' ');
      if (txt(clone) && txt(clone).length < 40) return txt(clone); }
    return '';
  };
  const submitOf = form => {
    if (!form) return null;
    const outside = form.id ? [...document.querySelectorAll(`button[form="${form.id}"], input[type=submit][form="${form.id}"]`)] : [];
    const cands = [...form.querySelectorAll('button, input[type=submit], input[type=image]'), ...outside]
      .filter(b => vis(b) && (b.tagName !== 'BUTTON' || (b.getAttribute('type') || 'submit') === 'submit'));
    const b = cands[0]; if (!b) return null;
    return {css: cssOf(b), text: txt(b.innerText || b.value || b.getAttribute('aria-label') || '')};
  };
  const r2 = el => { const r = el.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y + window.scrollY), Math.round(r.width), Math.round(r.height)]; };
  // a scripted filter panel's own Apply button (inputs outside any form)
  const applyHint = el => {
    let n = el.parentElement;
    for (let i = 0; n && i < 5; i++, n = n.parentElement) {
      const b = [...n.querySelectorAll('button, input[type=button], input[type=submit], a[role=button]')].find(x => vis(x) &&
        /^(apply|filter|search|go|update|show|refresh|submit|get directions|directions|route|translate|join|send|sign|adopt|continue|next|convert|calculate)\b|apply|filter/i.test(txt(x.innerText || x.value || x.getAttribute('aria-label') || '')));
      if (b) return {css: cssOf(b), text: txt(b.innerText || b.value || b.getAttribute('aria-label') || '')};
    }
    return null;
  };
  const selects = [...document.querySelectorAll('select')].filter(vis).map(el => {
    const form = el.form;
    return {kind: 'select', css: cssOf(el), name: el.getAttribute('name') || '', id: el.id || '',
      label: labelOf(el), placeholder: txt(([...el.options].find(o => o.value === '') || {}).text || ''), onchange: !!el.getAttribute('onchange') || !!el.onchange, multiple: el.multiple,
      options: [...el.options].map((o, i) => ({index: i, value: o.value, text: txt(o.text), disabled: o.disabled})),
      selected_index: el.selectedIndex,
      form: form ? {method: (form.getAttribute('method') || 'get').toLowerCase(), action: actionOf(form),
                    css: cssOf(form), submit: submitOf(form)} : null,
      label_css: el.labels && el.labels.length ? cssOf(el.labels[0]) : null, apply_hint: form ? null : applyHint(el),
      box: r2(el)};
  });
  const groups = {};
  for (const a of document.querySelectorAll('a[href]')) {
    if (!vis(a)) continue;
    let u; try { u = new URL(a.href, location.href); } catch (e) { continue; }
    if (u.origin !== location.origin || !u.pathname.startsWith('/sites/' + site + '/')) continue;
    for (const [k, v] of u.searchParams) {
      if (!/^(sort|order|orderby|sort_by|sortby|ordering)$/i.test(k)) continue;
      const g = (groups[u.pathname + '|' + k] = groups[u.pathname + '|' + k] || {path: u.pathname, key: k, options: []});
      if (!g.options.some(o => o.value === v))
        g.options.push({value: v, text: txt(a.innerText || a.getAttribute('aria-label') || v), href: u.pathname + u.search, css: cssOf(a), box: r2(a),
                        active: /(^|[\s_-])(active|selected|current|is-active)([\s_-]|$)/i.test(a.className || '') || a.getAttribute('aria-current') !== null || a.getAttribute('aria-selected') === 'true'});
    }
  }
  const links = Object.values(groups).filter(g => g.options.length >= 2);
  // every same-listing query-key link group (filter chips as well as sort links)
  const anyGroups = {};
  for (const a of document.querySelectorAll('a[href]')) {
    if (!vis(a)) continue;
    let u; try { u = new URL(a.href, location.href); } catch (e) { continue; }
    if (u.origin !== location.origin || u.pathname !== location.pathname) continue;
    for (const [k, v] of u.searchParams) {
      if (!v || /^(page|p|offset|start|limit|per_page|tab|view|lang|ref|next)$/i.test(k)) continue;
      const g = (anyGroups[k] = anyGroups[k] || {path: u.pathname, key: k, options: []});
      if (!g.options.some(o => o.value === v))
        g.options.push({value: v, text: txt(a.innerText || a.getAttribute('aria-label') || v), href: u.pathname + u.search, css: cssOf(a), box: r2(a),
                        active: /(^|[\s_-])(active|selected|current|is-active)([\s_-]|$)/i.test(a.className || '') || a.getAttribute('aria-current') !== null || a.getAttribute('aria-selected') === 'true'});
    }
  }
  const linkgroups = Object.values(anyGroups).filter(g => g.options.length >= 2);
  const formOf = el => { const f = el.form; if (!f) return null;
    return {method: (f.getAttribute('method') || 'get').toLowerCase(), action: actionOf(f), css: cssOf(f), submit: submitOf(f)}; };
  const groupLabel = el => {
    const fs = el.closest('fieldset'); if (fs) { const lg = fs.querySelector('legend'); if (lg && txt(lg.innerText)) return txt(lg.innerText); }
    let n = el.parentElement;
    for (let i = 0; n && i < 4; i++, n = n.parentElement) {
      let p = n.previousElementSibling;
      if (p && /^(H[1-6]|LABEL|STRONG|B|P|SPAN|DIV|LEGEND)$/.test(p.tagName) && !p.querySelector('input,select,button,a') && txt(p.innerText).length && txt(p.innerText).length < 40) return txt(p.innerText);
    }
    return '';
  };
  const boxVis = el => vis(el) || (el.labels && el.labels.length && vis(el.labels[0]));

  const triggerOf = el => {       // what a person clicks to open a (hidden) file input's dialog
    if (vis(el)) return {css: cssOf(el), text: 'file input'};
    if (el.labels && el.labels.length && vis(el.labels[0])) return {css: cssOf(el.labels[0]), text: txt(el.labels[0].innerText)};
    let n = el.parentElement;
    for (let i = 0; n && i < 5; i++, n = n.parentElement) {
      const b = [...n.querySelectorAll('button, label, a[role=button], [role=button], [class*=upload], [class*=drop]')].find(x => vis(x) &&
        /(upload|choose|browse|select (a )?file|add (a )?(photo|file|image|picture|attachment)|attach|drag|drop)/i.test(txt(x.innerText || x.getAttribute('aria-label') || '')));
      if (b) return {css: cssOf(b), text: txt(b.innerText || b.getAttribute('aria-label') || '')};
    }
    return null;
  };
  const inputs = [...document.querySelectorAll('input, textarea')].filter(el => el.type !== 'hidden' && (el.type === 'file' || boxVis(el))).slice(0, 200).map(el => {
    const type = el.tagName === 'TEXTAREA' ? 'textarea' : (el.getAttribute('type') || 'text').toLowerCase();
    const lab = el.labels && el.labels.length ? el.labels[0] : null;
    return {tag: el.tagName.toLowerCase(), type, css: cssOf(el), name: el.getAttribute('name') || '', id: el.id || '',
      label: labelOf(el), placeholder: el.getAttribute('placeholder') || '', value: el.value || '', checked: !!el.checked,
      min: el.getAttribute('min'), max: el.getAttribute('max'), step: el.getAttribute('step'),
      visible: vis(el), label_css: lab ? cssOf(lab) : null, option_text: txt((lab ? lab.innerText : '') || el.getAttribute('aria-label') || ''),
      group_label: groupLabel(el), onchange: !!el.getAttribute('onchange') || !!el.onchange || !!el.oninput || !!el.getAttribute('oninput'),
      form: formOf(el), apply_hint: el.form ? null : applyHint(el), box: r2(el),
      accept: el.getAttribute('accept') || '', trigger: el.type === 'file' ? triggerOf(el) : null};
  });
  // draggable lists (reorder by drag): containers with >= 3 draggable children
  const dragLists = [];
  for (const c of new Set([...document.querySelectorAll('[draggable=true]')].filter(vis).map(e => e.parentElement))) {
    const kids = [...c.children].filter(k => vis(k) && (k.getAttribute('draggable') === 'true' || k.querySelector('[draggable=true]')));
    if (kids.length >= 3) dragLists.push({css: cssOf(c), items: kids.slice(0, 30).map(k => ({css: cssOf(k), text: txt(k.innerText).slice(0, 80), box: r2(k)})),
      save: (() => { const h = applyHint(kids[0]); return h && /save|update|apply|submit|done/i.test(h.text) ? h : null; })()});
  }
  // drawing canvases with the button that keeps the drawing
  const canvases = [...document.querySelectorAll('canvas')].filter(c => vis(c) && c.getBoundingClientRect().width >= 120 && c.getBoundingClientRect().height >= 50).map(c => {
    let save = null, n = c.parentElement;
    for (let i = 0; n && i < 6 && !save; i++, n = n.parentElement) {
      const b = [...n.querySelectorAll('button, input[type=submit], [role=button]')].find(x => vis(x) &&
        /(save|sign|submit|done|adopt|apply|finish|confirm|use)/i.test(txt(x.innerText || x.value || x.getAttribute('aria-label') || '')) &&
        !/(clear|undo|reset|cancel|erase)/i.test(txt(x.innerText || x.value || '')));
      if (b) save = {css: cssOf(b), text: txt(b.innerText || b.value || '')};
    }
    return {css: cssOf(c), box: r2(c), save};
  });
  // editable grid cells (spreadsheets)
  const cells = [...document.querySelectorAll('td[contenteditable=true], td[contenteditable=""], [role=gridcell], td[data-cell], td[data-row], .cell[contenteditable], td input[type=text], td input:not([type])')]
    .filter(vis).slice(0, 80).map(el => {
      const td = el.closest('td, [role=gridcell]') || el; const tr = td.closest('tr');
      const table = td.closest('table'); const idx = td.cellIndex;
      const head = table && idx >= 0 && table.querySelector('thead tr') ? txt((table.querySelector('thead tr').cells[idx] || {}).innerText || '') : '';
      return {css: cssOf(el), text: txt(el.value !== undefined && el.tagName === 'INPUT' ? el.value : el.innerText).slice(0, 60),
              row: tr ? txt((tr.cells[0] || {}).innerText || '').slice(0, 40) : '', col: head.slice(0, 40), input: el.tagName === 'INPUT', box: r2(el)};
    });
  // listing item texts (search-term material): table cells and item links in the main content
  const items = [...new Set([
    ...[...document.querySelectorAll('tbody tr')].slice(0, 60).flatMap(tr => [...tr.cells].slice(0, 4).map(td => txt(td.innerText))),
    ...[...document.querySelectorAll('main a, article a, li a, .card a, [class*=card] a, [class*=item] a, h2 a, h3 a')]
       .filter(a => vis(a) && !a.closest('nav, header, footer')).map(a => txt(a.innerText)),
  ])].filter(t => t.length >= 4 && t.length <= 90 && /[a-z]{3}/i.test(t)).slice(0, 150);
  const region = a => { const r = a.closest('nav, header, aside, footer'); return r ? r.tagName.toLowerCase() : 'main'; };
  const anchors = [...document.querySelectorAll('a[href]')].filter(vis).map(a => { let u; try { u = new URL(a.href, location.href); } catch (e) { return null; }
      if (u.origin !== location.origin || !u.pathname.startsWith('/sites/' + site + '/') || u.pathname === location.pathname) return null;
      return {text: txt(a.innerText || a.getAttribute('aria-label') || a.title || ''), path: u.pathname, search: u.search, css: cssOf(a), box: r2(a), region: region(a)}; })
    .filter(a => a && a.text.length >= 3 && a.text.length <= 80).slice(0, 250);
  // buttons, with the item they act on (the card / row / list item they sit in, else the page's h1)
  const itemOf = el => {
    const box = el.closest('tr, li, article, [class*=card], [class*=item], [class*=post], [class*=row], [class*=entry], [class*=result], [class*=message], [class*=comment]');
    if (box) {
      // the item's name: a heading, a title/name element, a real link, a bold label — not an
      // avatar initial or a vote count; else the first line of the card with some words in it
      const good = t => t.length >= 3 && (t.match(/[A-Za-z]/g) || []).length >= 3;
      for (const sel of ['h1,h2,h3,h4,h5', '[class*=title],[class*=subject]', 'a[href]:not([role=button])', '[class*=name],[class*=author],[class*=user]', 'strong,b']) {
        const hits = [...box.querySelectorAll(sel)].map(n => txt(n.innerText)).filter(good);
        if (hits.length) return hits.sort((x, y) => (sel.startsWith('a[') ? y.length - x.length : 0))[0].slice(0, 90);
      }
      const line = (box.innerText || '').split('\n').map(txt).find(good);
      if (line) return line.slice(0, 90);
    }
    const h1 = document.querySelector('main h1, h1'); return h1 ? txt(h1.innerText).slice(0, 90) : '';
  };
  const fieldsIn = f => f ? [...f.querySelectorAll('input:not([type=hidden]):not([type=submit]):not([type=button]), textarea, select')].filter(vis).length : 0;
  const buttons = [...document.querySelectorAll('button, input[type=submit], input[type=button], a[role=button], [role=button]:not(a):not(button), [onclick]:not(a):not(button):not(input), a[download], a[href*="export"], a[href*="download"], a[href$=".csv"], a[href*="format="]')]
    .filter(vis).slice(0, 400).map(el => {
      const f = el.form || el.closest('form');
      return {text: txt(el.innerText || el.value || ''), aria: txt(el.getAttribute('aria-label') || el.title || ''), css: cssOf(el),
        tag: el.tagName.toLowerCase(), region: region(el), item: itemOf(el), pressed: el.getAttribute('aria-pressed'),
        form: f ? {method: (f.getAttribute('method') || 'get').toLowerCase(), action: actionOf(f), fields: fieldsIn(f)} : null,
        box: r2(el)};
    }).filter(b => b.text || b.aria);
  // question material (report_information / count_entries): data tables and groups of repeated cards
  const cellText = c => txt(c.innerText).slice(0, 120);
  const headingBefore = el => { for (let e = el, i = 0; e && i < 5; e = e.parentElement, i++) {
      for (let p = e.previousElementSibling; p; p = p.previousElementSibling) {
        const h = p.matches('h1,h2,h3,h4') ? p : p.querySelector('h1,h2,h3,h4'); if (h && vis(h)) return txt(h.innerText).slice(0, 80); } }
    return ''; };
  const tables = [...document.querySelectorAll('table')].filter(vis).slice(0, 6).map(t => {
    const headRow = t.querySelector('thead tr') || [...t.rows].find(r => r.querySelector('th') && !r.querySelector('td'));
    const headers = headRow ? [...headRow.cells].map(cellText) : [];
    const rows = [...t.rows].filter(r => r !== headRow && !r.closest('thead') && r.cells.length === headers.length && vis(r));
    return {css: cssOf(t), caption: t.caption ? txt(t.caption.innerText).slice(0, 80) : headingBefore(t), headers,
            n_rows: rows.length, rows: rows.slice(0, 60).map(r => [...r.cells].map(cellText))};
  }).filter(t => t.headers.length >= 2 && t.n_rows >= 3);
  const cardGroups = [];
  for (const p of document.querySelectorAll('main *, body > *, body > * > *, body > * > * > *')) {
    if (p.children.length < 3 || p.closest('nav, header, footer, table, select, [role=menu], [role=listbox]')) continue;
    const by = {};
    for (const c of p.children) { const k = c.tagName.toLowerCase() + (c.classList[0] ? '.' + c.classList[0] : ''); (by[k] = by[k] || []).push(c); }
    for (const [k, els] of Object.entries(by)) {
      const ok = els.filter(e => { const t = (e.innerText || '').trim(); return vis(e) && t.length >= 15 && t.length <= 1200 && t.includes('\n'); });
      if (ok.length >= 3 && ok.length >= 0.6 * els.length) cardGroups.push({p, k, els: ok});
    }
  }
  const cards = cardGroups.filter(g => !cardGroups.some(o => o !== g && o.els.some(e => e !== g.p && e.contains(g.p))))
    .filter((g, i, all) => all.findIndex(o => o.p === g.p && o.k === g.k) === i)
    .sort((a, b) => b.els.length - a.els.length).slice(0, 3)
    .map(g => ({css: cssOf(g.p), item: g.k, heading: headingBefore(g.p), n: g.els.length,
                cards: g.els.slice(0, 40).map(e => e.innerText.split('\n').map(txt).filter(Boolean).slice(0, 14))}));
  // shared mini-players (search_by_playback): the timeline key the player fetches with, and its length
  const players = [...document.querySelectorAll('[data-mini-player]')].filter(vis).slice(0, 4).map(el => {
    const d = el.dataset; const seek = el.querySelector('.mp-seek');
    return {css: cssOf(el), seek_css: seek ? cssOf(seek) : null, screen_css: el.querySelector('.mp-screen') ? cssOf(el.querySelector('.mp-screen')) : null,
            key: d.streamKey || (location.pathname + '|' + (d.title || d.badge || '')), duration: parseFloat(d.duration || '0') || 0,
            title: d.title || '', badge: d.badge || 'Video', stream: d.stream || '', play_url: d.playUrl || ''};
  });
  // on-page tools (compute_by_tool): a Convert/Calculate/Compute button with the inputs around it,
  // outside any form that saves; the element that will show the result
  const toolFields = box => [...box.querySelectorAll('input:not([type=hidden]):not([type=submit]):not([type=button]), select, textarea')]
    .filter(vis).slice(0, 10).map(el => { const sib = el.previousElementSibling && el.previousElementSibling.tagName === 'LABEL' ? el.previousElementSibling : null;
      const lab = (el.labels && el.labels[0]) ? txt(el.labels[0].innerText) : (el.getAttribute('aria-label') || (sib ? txt(sib.innerText) : '') || el.placeholder || '');
      return {css: cssOf(el), type: el.tagName === 'SELECT' ? 'select' : (el.getAttribute('type') || 'text').toLowerCase(), name: el.getAttribute('name') || el.id || '',
              label: txt(lab).slice(0, 60), placeholder: el.placeholder || '', value: el.value || '', min: el.getAttribute('min'), max: el.getAttribute('max'),
              step: el.getAttribute('step'), required: el.required,
              options: el.tagName === 'SELECT' ? [...el.options].slice(0, 60).map(o => ({value: o.value, text: txt(o.text)})) : null}; });
  const tools = [...document.querySelectorAll('button, input[type=button], [role=button]')].filter(vis)
    .filter(b => /^\W*(convert|calculate|compute|estimate|get (quote|estimate|rate))\b/i.test(txt(b.innerText || b.value || '')) && !(b.closest('form') && (b.closest('form').getAttribute('method') || 'get').toLowerCase() === 'post'))
    .slice(0, 6).map(b => { let box = b.parentElement;
      for (let i = 0; i < 5 && box && toolFields(box).length === 0; i++) box = box.parentElement;
      if (!box) return null;
      const RES = '[id*=result i], [class*=result i], output, [id*=output i], [id*=answer i], [id*=total i]';
      let res = null;                        // the result element nearest the tool's own button
      for (let e = b.parentElement, i = 0; e && i < 6 && !res; e = e.parentElement, i++) res = e.querySelector(RES);
      return {css: cssOf(b), text: txt(b.innerText || b.value || ''), box: cssOf(box), fields: toolFields(box), result_css: res ? cssOf(res) : null,
              heading: headingBefore(b)}; }).filter(t => t && t.fields.length);
  // image operations (edit_by_image): Apply crop / resize / contrast … buttons with their inputs, on a page
  // showing an image
  const bigImg = [...document.querySelectorAll('main img, img, canvas')].some(i => vis(i) && i.getBoundingClientRect().width >= 150);
  const imgops = !bigImg ? [] : [...document.querySelectorAll('button, [role=button]')].filter(vis)
    .filter(b => b.dataset.op || /^\W*(apply|crop|resize|rotate|flip|adjust)\b/i.test(txt(b.innerText || '')))
    .filter(b => /(crop|resize|rotat|flip|contrast|bright|vibran|saturat|blur|sharpen|filter|scale|exposure)/i.test((b.dataset.op || '') + ' ' + txt(b.innerText || '')))
    .slice(0, 8).map(b => { let box = b.parentElement;
      for (let i = 0; i < 3 && box && toolFields(box).length === 0; i++) box = box.parentElement;
      return box ? {css: cssOf(b), text: txt(b.innerText || ''), op: b.dataset.op || '', fields: toolFields(box), heading: headingBefore(b)} : null; })
    .filter(t => t && t.fields.length && t.fields.length <= 6);
  // Save-As exports (save_by_form): links that open the file system's Save dialog
  const saveas = [...document.querySelectorAll('[data-save-as]')].filter(vis).slice(0, 8)
    .map(a => ({css: cssOf(a), text: txt(a.innerText || a.getAttribute('title') || ''), href: a.getAttribute('href') || ''}));
  // a Leaflet map with its place data (search_by_pan_zoom): the view, and every place with whether
  // it is on screen now or listed beside the map
  let leaflet = null;
  try {
    if (window.L && window.map && window.map.getBounds && Array.isArray(window.locations)) {
      const m = window.map, b = m.getBounds(), el = m.getContainer();
      const listed = new Set([...document.querySelectorAll('[data-id]')].filter(vis).map(e => String(e.dataset.id)));
      leaflet = {css: el.id ? '#' + el.id : cssOf(el), zoom: m.getZoom(), box: r2(el),
        zoom_in_css: document.querySelector('.leaflet-control-zoom-in') ? '.leaflet-control-zoom-in' : null,
        places: window.locations.filter(l => l && l.lat && l.lng && l.name).slice(0, 400).map(l => ({
          id: String(l.id), name: String(l.name), lat: +l.lat, lng: +l.lng, address: l.address || '', category: l.category || '',
          in_view: b.contains([l.lat, l.lng]), listed: listed.has(String(l.id))}))};
    }
  } catch (e) { leaflet = null; }
  // freeform boards (reposition_by_drag): absolutely placed elements (stickies, labels) in one container
  const boards = [];
  for (const c of new Set([...document.querySelectorAll('[style*="left"][style*="top"]')].filter(vis).map(e => e.parentElement))) {
    if (!c) continue;
    const kids = [...c.children].filter(k => vis(k) && k.style.left && k.style.top && getComputedStyle(k).position === 'absolute');
    if (kids.length < 3) continue;
    const cb = c.getBoundingClientRect();
    boards.push({css: cssOf(c), box: r2(c), items: kids.slice(0, 60).map(k => ({css: cssOf(k), text: txt((k.innerText || '').split('\n')[0]).slice(0, 60),
      cls: k.className || '', x: parseFloat(k.style.left), y: parseFloat(k.style.top), w: k.offsetWidth, h: k.offsetHeight,
      bold: parseInt(getComputedStyle(k).fontWeight) >= 600}))});
  }
  // masked values (reveal_by_2fa): leaf elements showing dots/asterisks in place of characters
  const masked = [...document.querySelectorAll('main *, body *')]
    .filter(e => e.children.length === 0 && vis(e) && /[•●*]{3,}/.test(e.textContent) && e.textContent.trim().length <= 60)
    .slice(0, 30).map(e => ({css: cssOf(e), text: txt(e.textContent), item: itemOf(e)}));
  const pager = !!document.querySelector('.pagination, [class*=pager], nav[aria-label*=agination], a[href*="page="], a[rel=next]');
  const body = txt(document.body.innerText).slice(0, 200000);
  const dates = [...new Set([...body.matchAll(/\b(20[0-3][0-9])-([01][0-9])-([0-3][0-9])\b/g)].map(m => m[0]))].slice(0, 400);
  const mon = {jan:1,feb:2,mar:3,apr:4,may:5,jun:6,jul:7,aug:8,sep:9,oct:10,nov:11,dec:12};
  for (const m of body.matchAll(/\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? ([0-3]?[0-9]), (20[0-3][0-9])\b/g)) {
    const d = `${m[3]}-${String(mon[m[1].toLowerCase()]).padStart(2, '0')}-${String(m[2]).padStart(2, '0')}`;
    if (dates.length < 400 && !dates.includes(d)) dates.push(d);
  }
  const headings = [...document.querySelectorAll('main h1, main h2, main h3, main h4, h2, h3, h4, article a, .card a, li a, td a')]
    .filter(vis).map(h => txt(h.innerText)).filter(t => t.length >= 4 && t.length <= 90);
  const hrefs = [...new Set([...document.querySelectorAll('a[href]')].map(a => { try { const u = new URL(a.href, location.href);
      return u.origin === location.origin ? u.pathname : null; } catch (e) { return null; } }).filter(Boolean))];
  const h1 = document.querySelector('main h1, h1');
  return {title: document.title, h1: h1 ? txt(h1.innerText).slice(0, 90) : '', selects, links, linkgroups, inputs, anchors, dates, items, buttons,
          dragLists, canvases, cells, tables, cards, pager, players, masked, tools, imgops, saveas, leaflet, boards, headings: [...new Set(headings)].slice(0, 120),
          hrefs, page_height: document.documentElement.scrollHeight};
}
"""


def _pattern(path):
    """Collapse ids so /item/12 and /item/13 count as one page type."""
    segs = []
    for s in path.rstrip("/").split("/"):
        segs.append("{id}" if re.fullmatch(r"[0-9]+|[0-9a-f-]{8,}|[a-z]+-?[0-9]{2,}[a-z0-9-]*", s, re.I) else s)
    return "/".join(segs)


def _route_seeds(site):
    """The site's own static GET pages (routes without parameters) — pages no link on the first
    levels may lead to (a Join page, the cart)."""
    p = config.ROOT / "sites" / site / "routes.py"
    try:
        src = p.read_text()
    except OSError:
        return []
    out = []
    for m in re.finditer(r'@\w+\.route\(\s*["\'](/[^"\'<]*)["\']\s*(?:,\s*methods\s*=\s*\[([^\]]*)\])?', src):
        path, methods = m.group(1), m.group(2) or "'GET'"
        if "GET" not in methods or re.search(r"(^/api/|/api/|export|download|logout|reset|delete|\.(json|csv|xml|txt)$)", path):
            continue
        out.append(f"/sites/{site}{path}")
    return list(dict.fromkeys(out))[:40]


def _seed_paths(site):
    """Paths humans visited on this site (their recordings), as extra crawl seeds."""
    from annotation.storage import ANNOTATIONS_DIR
    out = []
    for p in sorted(ANNOTATIONS_DIR.glob("*/*/trajectory.json")):
        if "/." in p.as_posix():
            continue
        try:
            head = p.read_text()[:400000]
        except OSError:
            continue
        for m in re.finditer(r'"url":\s*"[^"]*?(/sites/' + re.escape(site) + r'/[^"?#]*)', head):
            out.append(m.group(1))
    return list(dict.fromkeys(out))[:60]


def _role(ctrl):
    blob = " ".join(str(ctrl.get(k) or "") for k in ("name", "id", "label", "css", "key"))
    return "sort" if SORT_WORDS.search(blob) else "filter"


OPENER = re.compile(r"^(share|cancel\b|reply|edit|compose|new\b|add (a )?(comment|review|note|contact|member|item|task|event|card)|"
                    r"invite|write( a)? review|leave a review|review|report|type|sign\b|comment|message|contact|book|"
                    r"reserve|join|transfer|pay\b|rate|rsvp|apply|send|redeem|buy)", re.I)
REVEAL_PER_SITE = 120
REVEAL_PER_PAGE = 4


def reveal(site, base, b, page_path, scan, keys, only=None, budget=None):
    """Controls behind an opener (a Share dialog, a Type tab, a cancel-reason form): click each
    likely opener in a throw-away session, scan again, keep what a kind finds that was not there
    before, tagged with the opener to click first. Returns [(key, ctrl)]."""
    before = {k for kind in kinds.all_kinds() if not only or kind.name in only
              for k, _c in kind.discover(scan, page_path, site)}
    openers, seen = [], set()
    for btn in scan.get("buttons") or []:
        label = re.sub(r"^[\W_]+", "", btn["text"] or btn["aria"] or "")          # "🔗 Share" -> "Share"
        if btn["region"] in ("nav", "header", "footer") or not OPENER.match(label) or btn["tag"] == "a" and "download" in label.lower():
            continue
        fam = re.sub(r"[^a-z ]", "", (label or "").lower()).strip()[:30]
        if fam not in seen:
            seen.add(fam)
            openers.append(btn)
    out = []
    for btn in openers[: (budget if budget is not None else REVEAL_PER_SITE)]:
        ctx = B.new_context(b)
        pg = ctx.new_page()
        try:
            pg.once("dialog", lambda d: d.dismiss())
            B.goto_start(pg, base + page_path)
            pg.locator(btn["css"]).first.click(timeout=4000)
            B.settle(pg)
            if urlsplit(pg.url).path.rstrip("/") != page_path.rstrip("/"):
                continue                       # it navigated: the crawl reaches that page itself
            scan2 = pg.evaluate(_SCAN_JS, site)
        except Exception:
            continue
        finally:
            ctx.close()
        for kind in kinds.all_kinds():
            if only and kind.name not in only:
                continue
            for key, ctrl in kind.discover(scan2, page_path, site):
                if key in before or key in keys:
                    continue
                ctrl["opener"] = {"css": btn["css"], "text": btn["text"] or btn["aria"]}
                out.append((key + ("opener", btn["text"] or btn["aria"]), ctrl))
    return out


PAGE_ROUTE = re.compile(r"/(join|checkout|cart)$", re.I)
ADD_CART = re.compile(r"^\W*(add to (cart|bag|basket)|buy now|add item)\b", re.I)
CART_PATH = re.compile(r"/(cart|checkout|basket|bag)(/|$)", re.I)


def add_to_cart(ctx, base, prep):
    """Privileged session preparation: put one item in the cart (a checkout needs one)."""
    page = ctx.new_page()
    try:
        page.goto(base + prep["page"], wait_until="load", timeout=20000)
        loc = page.locator(prep["css"])
        if prep.get("text"):
            loc = loc.filter(has_text=prep["text"])
        loc.first.click(timeout=5000)
        B.settle(page)
    finally:
        page.close()


def stocked(site, base, b, cart_btn, cart_links, keys, only=None):
    """Controls on the cart / checkout pages of a session with one item in its cart; each carries
    the preparation (`prep`) that sessions replay before starting there."""
    out = []
    ctx = B.new_context(b)
    try:
        add_to_cart(ctx, base, cart_btn)
        page = ctx.new_page()
        todo = list(dict.fromkeys([f"/sites/{site}/cart", f"/sites/{site}/checkout"] + cart_links))[:8]
        seen = set()
        while todo and len(seen) < 8:
            path = todo.pop(0)
            if path in seen:
                continue
            seen.add(path)
            try:
                resp = page.goto(base + path, wait_until="load", timeout=20000)
                if resp is None or resp.status >= 400:
                    continue
                time.sleep(0.15)
                scan = page.evaluate(_SCAN_JS, site)
            except Exception:
                continue
            final_path = urlsplit(page.url).path
            for kind in kinds.all_kinds():
                if only and kind.name not in only:
                    continue
                for key, ctrl in kind.discover(scan, final_path, site):
                    if key not in keys:
                        keys.add(key)
                        ctrl["prep"] = {"add_to_cart": cart_btn}
                        out.append(ctrl)
            todo += [h for h in scan["hrefs"] if CART_PATH.search(h) and h not in seen and h.startswith(f"/sites/{site}/")]
    finally:
        ctx.close()
    return out


def crawl(site, base, max_pages=30, max_depth=2, per_pattern=2, b=None, only=None, reveal_budget=REVEAL_PER_SITE):
    """{site, pages: [{path, title}], controls: [...]} — unprobed."""
    own = b is None
    cm = B.browser() if own else None
    b = cm.__enter__() if own else b
    try:
        ctx = B.new_context(b)
        page = ctx.new_page()
        root = f"/sites/{site}/"
        routes = set(_route_seeds(site))
        queue = deque([(root, 0)] + [(p, 1) for p in dict.fromkeys(list(routes) + _seed_paths(site))])
        seen_paths, seen_patterns, pages, controls, keys = set(), {}, [], [], set()
        cart_btn, cart_links, revealed = None, [], set()
        while queue and len(pages) < max_pages:
            path, depth = queue.popleft()
            # a static page route (/join, /checkout) is a page, not a link that acts
            if path in seen_paths or (SKIP.search(path) and not (path in routes and PAGE_ROUTE.search(path))):
                continue
            pat = _pattern(path)
            if seen_patterns.get(pat, 0) >= per_pattern:
                continue
            seen_paths.add(path)
            seen_patterns[pat] = seen_patterns.get(pat, 0) + 1
            try:
                resp = page.goto(base + path, wait_until="load", timeout=20000)
                if resp is None or resp.status >= 400:
                    continue
                time.sleep(0.15)
                scan = page.evaluate(_SCAN_JS, site)
            except Exception:
                continue
            final_path = urlsplit(page.url).path
            if not final_path.startswith(root):
                continue
            pages.append({"path": final_path, "title": scan["title"]})
            if cart_btn is None:
                b0 = next((x for x in scan.get("buttons") or [] if ADD_CART.search(x["text"] or x["aria"] or "")), None)
                cart_btn = {"page": final_path, "css": b0["css"], "text": b0["text"] or b0["aria"]} if b0 else None
            cart_links += [h for h in scan["hrefs"] if h.startswith(root) and CART_PATH.search(h) and h not in cart_links]
            for kind in kinds.all_kinds():
                if only and kind.name not in only:
                    continue
                for key, ctrl in kind.discover(scan, final_path, site):
                    if key not in keys:
                        keys.add(key)
                        controls.append(ctrl)
            if reveal_budget > 0 and _pattern(final_path) not in revealed:     # once per kind of page
                revealed.add(_pattern(final_path))
                found = reveal(site, base, b, final_path, scan, keys, only=only, budget=min(REVEAL_PER_PAGE, reveal_budget))
                reveal_budget -= min(REVEAL_PER_PAGE, reveal_budget)
                for key, ctrl in found:
                    if key not in keys:
                        keys.add(key)
                        controls.append(ctrl)
            if depth < max_depth:
                for h in scan["hrefs"]:
                    if h.startswith(root) and h not in seen_paths and not SKIP.search(h):
                        queue.append((h, depth + 1))
        ctx.close()
        if cart_btn:                      # checkout pages only show their forms with something in the cart
            controls += stocked(site, base, b, cart_btn, cart_links, keys, only)
    finally:
        if own:
            cm.__exit__(None, None, None)
    for i, c in enumerate(controls):
        c["control_id"] = f"{site}:{c['kind']}:{c['role']}:{i}"
    return {"site": site, "name": B.site_name(site), "pages": pages, "controls": controls}


# ── probing: what request does the control produce? ───────────────────────────

def _norm(v):
    return re.sub(r"\s+", " ", str(v if v is not None else "")).strip().casefold()


def find_carrier(entries, value, prefer_key=""):
    """The first accepted request whose query/body carries `value`: (entry, key) or (None, None)."""
    want = _norm(value)
    if not want:
        return None, None
    for e in entries:
        if not isinstance(e.get("status"), int) or not 200 <= e["status"] < 400:
            continue
        fields = {}
        fields.update(e.get("query") or {})
        if isinstance(e.get("body"), dict):
            fields.update({k: v for k, v in e["body"].items() if not isinstance(v, dict)})
        hits = [k for k, v in fields.items() if (want in map(_norm, v) if isinstance(v, list) else _norm(v) == want)]
        if hits:
            return e, (prefer_key if prefer_key in hits else hits[0])
    return None, None


def apply_privileged(page, ctrl, option, base, ctx, log_before):
    """Set `option` on `ctrl` with privileged Playwright calls (NOT a training action).
    Returns (carrier_entry, param, apply_mode, new_entries). A control behind an opener (a dialog,
    a tab) is revealed first."""
    if ctrl.get("opener"):
        page.locator(ctrl["opener"]["css"]).first.click(timeout=5000)
        B.settle(page)
    return kinds.of(ctrl).apply(page, ctrl, option, base, ctx, log_before)


def probe(site_map, base, b=None):
    """Attach a backend signature to every control (in place). One non-default option each."""
    own = b is None
    cm = B.browser() if own else None
    b = cm.__enter__() if own else b
    try:
        for ctrl in site_map["controls"]:
            if not kinds.of(ctrl).needs_probe:
                kinds.of(ctrl).static_probe(ctrl)
                continue
            opt = kinds.of(ctrl).probe_argument(ctrl)
            if not opt:
                ctrl["usable"], ctrl["why"] = False, "no non-default option"
                continue
            ctx = B.new_context(b)
            page = ctx.new_page()
            try:
                kinds.of(ctrl).setup(ctx, base, ctrl, opt)
                B.goto_start(page, base + ctrl["page"])
                n0 = len(B.session_log(ctx, base))
                e, key, mode, _new = apply_privileged(page, ctrl, opt, base, ctx, n0)
                if not e and ctrl.get("kind") == "form" and ctrl["role"] != "authenticate_by_form" and not ctrl.get("grounded"):
                    # invented values the site rejects (a meeting code that does not exist): once more with
                    # value sets grounded in the site's own records
                    ctx.close()
                    ctx = B.new_context(b)
                    page = ctx.new_page()
                    from datagen import formvalues as FV
                    ctrl["value_sets"] = FV.value_sets(ctrl, site_map["site"], force=True, grounded=True)
                    ctrl["grounded"] = True
                    opt = kinds.of(ctrl).probe_argument(ctrl)
                    if opt:
                        kinds.of(ctrl).setup(ctx, base, ctrl, opt)
                        B.goto_start(page, base + ctrl["page"])
                        n0 = len(B.session_log(ctx, base))
                        e, key, mode, _new = apply_privileged(page, ctrl, opt, base, ctx, n0)
                if e:
                    ctrl["signature"] = {"method": e["method"], "path": e["path"], "param": key,
                                         "probe_value": opt.get("value")}
                    ctrl["apply"] = mode
                    ctrl["usable"] = True
                else:
                    ctrl["usable"], ctrl["why"] = False, "no request carries the option value (client-side only?)"
            except Exception as exc:
                ctrl["usable"], ctrl["why"] = False, f"probe error: {type(exc).__name__}: {str(exc)[:120]}"
            finally:
                ctx.close()
    finally:
        if own:
            cm.__exit__(None, None, None)
    return site_map


NOT_LISTING_PAGE = re.compile(r"/(settings|preferences|profile|account|compare|edit|new|create)(/|$)", re.I)
NOT_LISTING_PATH = re.compile(r"/(api/)?(export|download|settings)(/|$)", re.I)
SIBLING_CAP = 2


def refine(site_map):
    """Post-probe cleanup (idempotent; applied on build and on load):
      * role from the probed param / option texts too ("Sort: Recent" is a sort control);
      * only GET listing controls count — settings forms, exports and compare pickers are
        other macros (their selects submit edits or pick records, not narrow a listing);
      * at most SIBLING_CAP controls per (kind, role, param, parent page) so 30 category
        pages with the same sort select don't dominate a site."""
    groups = {}
    for c in site_map.get("controls", []):
        if not c.get("signature") or not kinds.of(c).listing:
            continue
        sig = c["signature"]
        blob = " ".join([sig.get("param", "")] + [o.get("text", "") for o in c.get("options", [])[:2]])
        if c["role"] == "filter" and (SORT_WORDS.search(sig.get("param", "")) or
                                      re.match(r"\s*sort\b", c["options"][0].get("text", "") if c.get("options") else "", re.I)):
            c["role"] = "sort"
        if c.get("usable") is False and c.get("why", "").startswith(("not a listing", "sibling")):
            c["usable"] = True
            c.pop("why", None)
        if not c.get("usable"):
            continue
        if sig.get("method") != "GET":
            c["usable"], c["why"] = False, "not a listing control (submits with POST)"
        elif NOT_LISTING_PATH.search(sig.get("path", "")) or NOT_LISTING_PAGE.search(c.get("page", "")):
            c["usable"], c["why"] = False, "not a listing control (settings/export/compare page)"
        else:
            parent = c["page"].rstrip("/").rsplit("/", 1)[0]
            g = (c["kind"], c["role"], sig.get("param"), parent if parent.count("/") > 2 else c["page"])
            groups[g] = groups.get(g, 0) + 1
            if groups[g] > SIBLING_CAP:
                c["usable"], c["why"] = False, "sibling page control (capped)"
    return site_map


def path_for(site):
    return config.SITEMAP_DIR / f"{site}.json"


def load(site):
    p = path_for(site)
    return refine(json.loads(p.read_text())) if p.exists() else None


def build(site, base, force=False, b=None, only=None, depth=None):
    """Crawl + probe one site, cached in data/datagen/sitemap/<site>.json. With `only` (kind
    names), re-discover and probe just those kinds and merge them into the existing map."""
    from datagen.split import assert_train
    assert_train(site)
    if not force and not only and path_for(site).exists():
        return load(site)
    sm = refine(probe(crawl(site, base, b=b, only=only, **(depth or {})), base, b=b))
    if only and path_for(site).exists():
        old = json.loads(path_for(site).read_text())
        keep = [c for c in old.get("controls", []) if c.get("kind") not in only]
        sm["controls"] = keep + sm["controls"]
        sm["pages"] = old.get("pages") or sm["pages"]
        for i, c in enumerate(sm["controls"]):
            c["control_id"] = f"{site}:{c['kind']}:{c.get('role')}:{i}"
    sm["built_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    config.SITEMAP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path_for(site).with_suffix(".json.tmp")          # atomic: a running sampler never reads half a map
    tmp.write_text(json.dumps(sm, indent=1, ensure_ascii=False))
    tmp.replace(path_for(site))
    return sm


def usable_controls(site_map, role):
    return [c for c in (site_map or {}).get("controls", []) if c.get("usable") and c.get("role") == role]


def usable_for(site_map, macro):
    """Usable controls that can be the target of `macro` (their kind serves it in their role)."""
    return [c for c in (site_map or {}).get("controls", []) if c.get("usable") and kinds.serves(c, macro)]


def build_many(sites, bases, workers=4, force=False, log=print, only=None, depth=None):
    """Build site maps for many sites: `workers` threads, each with its own browser
    (Playwright's sync API is per-thread), servers round-robin."""
    import queue
    import threading
    todo = queue.Queue()
    for item in enumerate(sites):
        todo.put(item)
    out = {}

    def worker():
        with B.browser() as b:
            while True:
                try:
                    i, site = todo.get_nowait()
                except queue.Empty:
                    return
                t0 = time.time()
                try:
                    sm = build(site, bases[i % len(bases)], force=force, b=b, only=only, depth=depth)
                    n = sum(1 for c in sm["controls"] if c.get("usable"))
                    log(f"sitemap {site}: {len(sm['pages'])} pages, {n}/{len(sm['controls'])} usable controls "
                        f"({time.time() - t0:.0f}s)", flush=True) if log is print else \
                        log(f"sitemap {site}: {len(sm['pages'])} pages, {n}/{len(sm['controls'])} usable controls "
                            f"({time.time() - t0:.0f}s)")
                    out[site] = sm
                except Exception as exc:
                    log(f"sitemap {site}: FAILED {type(exc).__name__}: {exc}")
                    out[site] = None

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(max(1, workers))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return out
