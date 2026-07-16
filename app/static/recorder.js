/**
 * MiniWeb Recorder — captures user interactions AND network activity.
 *
 * Like Chrome DevTools: every click, type, select is logged alongside
 * the HTTP requests they trigger and the responses that come back.
 *
 * Message types posted to parent via postMessage:
 *   {mw:'action',      action, target, selector, ...params, timestamp}
 *   {mw:'network',     method, url, status, requestBody, responseBody, duration, timestamp}
 *   {mw:'observation', url, title, timestamp}
 */
(function() {
    'use strict';
    if (window.__mw_recorder) return;
    window.__mw_recorder = true;

    var path = location.pathname;
    if (path === '/' || path.startsWith('/annotate') || path.startsWith('/_admin')) return;

    var TYPING_DEBOUNCE = 500;
    var typingTimer = null;
    var typingTarget = null;

    // ── Post to parent (annotation UI) or backend (agent runs) ─────────
    //
    // Human annotation runs inside an iframe, so messages go to the parent.
    // Browser-agent runs have no parent listening (no annotation UI), which
    // meant every observation was discarded. When there is no parent, ship
    // the same records to the backend collector instead, so agent runs
    // produce the identical action+observation stream a human does.

    var HAS_PARENT = (function () {
        try { return window.top !== window.self; } catch (e) { return true; }
    })();

    function postToBackend(msg) {
        try {
            var body = JSON.stringify(msg);
            // keepalive so records survive the navigation that follows a click
            fetch('/_admin/record', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: body,
                keepalive: true,
                credentials: 'same-origin',
            }).catch(function () {});
        } catch (e) {}
    }

    function post(msg) {
        if (HAS_PARENT) {
            try { window.top.postMessage(msg, '*'); } catch (e) {}
        } else {
            postToBackend(msg);
        }
    }

    // ── Human-readable element description ─────────────────────────────

    function describe(el) {
        if (!el || el === document.body || el === document.documentElement) return 'page';
        var tag = el.tagName.toLowerCase();
        var label = accessibleName(el);
        var trunc = label.length > 50 ? label.slice(0, 47) + '...' : label;

        if (tag === 'a') {
            var href = el.getAttribute('href') || '';
            return trunc ? "link '" + trunc + "' -> " + href : "link -> " + href;
        }
        if (tag === 'button' || el.type === 'submit' || (el.getAttribute('role') === 'button')) {
            return "button '" + (trunc || '(unnamed)') + "'";
        }
        if (tag === 'input') {
            var t = el.type || 'text';
            if (t === 'checkbox') return "checkbox '" + trunc + "'";
            if (t === 'radio') return "radio '" + trunc + "'";
            return "input[" + t + "] '" + (trunc || el.placeholder || el.name || '') + "'";
        }
        if (tag === 'textarea') return "textarea '" + (trunc || el.name || '') + "'";
        if (tag === 'select') {
            var opt = el.options[el.selectedIndex];
            return "select '" + (trunc || el.name || '') + "' = '" + (opt ? opt.text.trim() : '') + "'";
        }
        if (/^h[1-6]$/.test(tag)) return tag + " '" + trunc + "'";

        var desc = tag;
        if (el.className && typeof el.className === 'string') {
            var cls = el.className.split(/\s+/).filter(function(c) { return c.length > 0 && c.length < 30; }).slice(0, 2).join('.');
            if (cls) desc = tag + '.' + cls;
        }
        if (trunc) desc += " '" + trunc + "'";
        return desc;
    }

    function accessibleName(el) {
        var a = el.getAttribute('aria-label');
        if (a) return a.trim();
        var lb = el.getAttribute('aria-labelledby');
        if (lb) {
            var parts = lb.split(/\s+/).map(function(id) {
                var r = document.getElementById(id);
                return r ? r.textContent.trim() : '';
            }).filter(Boolean);
            if (parts.length) return parts.join(' ');
        }
        if (el.id) {
            var lbl = document.querySelector('label[for="' + el.id + '"]');
            if (lbl) return lbl.textContent.trim();
        }
        if (el.labels && el.labels.length) return el.labels[0].textContent.trim();
        if (el.title) return el.title.trim();
        if (el.alt) return el.alt.trim();
        if (el.placeholder) return el.placeholder.trim();
        var tag = el.tagName.toLowerCase();
        if (/^(button|a|h[1-6]|label|th|option|li)$/.test(tag)) {
            var text = el.textContent.trim().replace(/\s+/g, ' ');
            return text.length > 60 ? text.slice(0, 57) + '...' : text;
        }
        return '';
    }

    function selector(el) {
        if (!el || el === document.body) return 'body';
        if (el.id) return '#' + el.id;
        var tag = el.tagName.toLowerCase();
        if (el.className && typeof el.className === 'string') {
            var cls = el.className.trim().split(/\s+/).filter(function(c) {
                return c.length > 0 && c.length < 40 && !/^js-|^ng-|^v-|^\d/.test(c);
            }).slice(0, 3);
            if (cls.length) {
                var s = tag + '.' + cls.join('.');
                try { if (document.querySelectorAll(s).length === 1) return s; } catch(e) {}
            }
        }
        for (var attr of ['name', 'data-id', 'data-testid', 'aria-label', 'placeholder']) {
            var val = el.getAttribute(attr);
            if (val) {
                var s = tag + '[' + attr + '="' + val.replace(/"/g, '\\"') + '"]';
                try { if (document.querySelectorAll(s).length === 1) return s; } catch(e) {}
            }
        }
        return tag;
    }

    // ── Action posting ──────────────────────────────────────────────────

    function postAction(action, el, extra) {
        var msg = {
            mw: 'action',
            action: action,
            target: describe(el),
            selector: selector(el),
            url: location.pathname + location.search,
            timestamp: new Date().toISOString(),
        };
        if (extra) { for (var k in extra) msg[k] = extra[k]; }
        // Post to parent (annotation UI trajectory)
        post(msg);
        // Beacon to server (backend action log) — skip scroll
        if (action !== 'scroll') {
            var beacon = JSON.stringify(msg);
            try { navigator.sendBeacon('/_admin/beacon', new Blob([beacon], {type: 'application/json'})); }
            catch(e) { /* sendBeacon not available, silently skip */ }
        }
        // Post observation after every action (debounced to avoid flooding)
        clearTimeout(_obsTimer);
        _obsTimer = setTimeout(function() {
            post(makeObservation());
        }, 300);
    }
    var _obsTimer = null;

    // ── Network interception ────────────────────────────────────────────
    // Wraps fetch() and XMLHttpRequest to log all HTTP traffic

    // Skip noisy URLs from network logging
    function _isNoisy(url) {
        if (!url) return true;
        if (/\.(css|js|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|map)(\?|$)/i.test(url)) return true;
        if (url.indexOf('/_admin') !== -1) return true;
        if (url.indexOf('/annotate') !== -1) return true;
        if (url.indexOf('/static/') !== -1) return true;
        return false;
    }

    // -- fetch wrapper --
    var origFetch = window.fetch;
    window.fetch = function(input, init) {
        var method = (init && init.method) ? init.method.toUpperCase() : 'GET';
        var url = (typeof input === 'string') ? input : (input.url || '');
        if (_isNoisy(url)) return origFetch.apply(this, arguments);
        var reqBody = null;
        if (init && init.body) {
            try {
                reqBody = typeof init.body === 'string' ? init.body : null;
            } catch(e) {}
        }
        var t0 = performance.now();

        return origFetch.apply(this, arguments).then(function(response) {
            var duration = Math.round(performance.now() - t0);
            // Clone to read body without consuming it
            var clone = response.clone();
            clone.text().then(function(text) {
                var respBody = text.length > 500 ? text.slice(0, 500) + '...' : text;
                // Try to parse as JSON for cleaner display
                var respParsed = null;
                try { respParsed = JSON.parse(text); } catch(e) {}

                post({
                    mw: 'network',
                    method: method,
                    url: url,
                    status: response.status,
                    requestBody: reqBody ? (reqBody.length > 300 ? reqBody.slice(0, 300) + '...' : reqBody) : null,
                    responseBody: respParsed || respBody,
                    responseSize: text.length,
                    duration: duration,
                    timestamp: new Date().toISOString(),
                });
            }).catch(function() {
                post({
                    mw: 'network',
                    method: method, url: url, status: response.status,
                    duration: duration, timestamp: new Date().toISOString(),
                });
            });
            return response;
        }).catch(function(err) {
            post({
                mw: 'network',
                method: method, url: url, status: 0, error: err.message,
                duration: Math.round(performance.now() - t0),
                timestamp: new Date().toISOString(),
            });
            throw err;
        });
    };

    // -- XMLHttpRequest wrapper --
    var origXHROpen = XMLHttpRequest.prototype.open;
    var origXHRSend = XMLHttpRequest.prototype.send;

    XMLHttpRequest.prototype.open = function(method, url) {
        this._mw_method = method;
        this._mw_url = url;
        return origXHROpen.apply(this, arguments);
    };

    XMLHttpRequest.prototype.send = function(body) {
        var xhr = this;
        if (_isNoisy(xhr._mw_url)) return origXHRSend.apply(this, arguments);
        var t0 = performance.now();
        xhr._mw_body = body;

        xhr.addEventListener('loadend', function() {
            var respText = '';
            try { respText = xhr.responseText || ''; } catch(e) {}
            var respBody = respText.length > 500 ? respText.slice(0, 500) + '...' : respText;
            var respParsed = null;
            try { respParsed = JSON.parse(respText); } catch(e) {}

            post({
                mw: 'network',
                method: (xhr._mw_method || 'GET').toUpperCase(),
                url: xhr._mw_url || '',
                status: xhr.status,
                requestBody: body ? (String(body).slice(0, 300)) : null,
                responseBody: respParsed || respBody,
                responseSize: respText.length,
                duration: Math.round(performance.now() - t0),
                timestamp: new Date().toISOString(),
            });
        });

        return origXHRSend.apply(this, arguments);
    };

    // ── DOM Event Listeners ─────────────────────────────────────────────

    // ── Click — the primary signal. Logs everything on click. ──────────
    // Typing is only flushed on click/submit/navigation, not while typing.
    var isDragging = false;
    var pendingInput = null;  // {el, text} — buffered until next click

    function flushPendingInput() {
        if (pendingInput) {
            postAction('type', pendingInput.el, { text: pendingInput.text });
            pendingInput = null;
        }
    }

    document.addEventListener('click', function(e) {
        if (isDragging) return;
        var el = e.target;

        // Walk up to find the clickable ancestor
        var clickable = el;
        var depth = 0;
        while (clickable && clickable !== document.body && depth < 5) {
            if (clickable.tagName === 'A' || clickable.tagName === 'BUTTON' ||
                clickable.tagName === 'INPUT' || clickable.tagName === 'SELECT' ||
                clickable.tagName === 'TEXTAREA' ||
                clickable.getAttribute('role') === 'button' ||
                clickable.onclick || clickable.getAttribute('onclick')) break;
            clickable = clickable.parentElement;
            depth++;
        }
        var target = (clickable && clickable !== document.body) ? clickable : el;

        // Flush any buffered typing before logging the click
        flushPendingInput();

        var extra = { x: e.clientX, y: e.clientY, button: e.button };
        if (target.tagName === 'A' && target.getAttribute('href')) {
            extra.href = target.getAttribute('href');
        }
        // Capture current value for inputs/selects at click time
        if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
            extra.value = target.value || '';
        }
        if (target.tagName === 'SELECT') {
            var opt = target.options[target.selectedIndex];
            extra.value = target.value;
            extra.option_text = opt ? opt.text.trim() : '';
        }

        postAction('click', target, extra);
    }, true);

    // ── Input — buffer typing, only flush on next click/submit/nav ─────
    document.addEventListener('input', function(e) {
        var el = e.target;
        if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
            pendingInput = { el: el, text: el.value };
        }
    }, true);

    // ── Select/checkbox/range — log immediately (these are one-shot) ───
    document.addEventListener('change', function(e) {
        var el = e.target;
        if (el.tagName === 'SELECT') {
            var opt = el.options[el.selectedIndex];
            postAction('select', el, { value: el.value, option_text: opt ? opt.text.trim() : '' });
        } else if (el.type === 'checkbox' || el.type === 'radio') {
            postAction('check', el, { checked: el.checked });
        } else if (el.type === 'range' || el.type === 'date' || el.type === 'number') {
            postAction('change', el, { value: el.value });
        }
    }, true);

    // Keyboard (Enter, Escape, Tab) — flush pending input, then log key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' || e.key === 'Escape' || e.key === 'Tab') {
            flushPendingInput();
            postAction('keypress', e.target, { key: e.key });
        }
    }, true);

    // Scroll (debounced)
    var scrollTimer = null;
    document.addEventListener('scroll', function(e) {
        if (scrollTimer) clearTimeout(scrollTimer);
        scrollTimer = setTimeout(function() {
            var target = (e.target === document || e.target === document.documentElement) ? document.body : e.target;
            postAction('scroll', target, {
                scroll_top: (e.target === document ? document.documentElement.scrollTop : e.target.scrollTop) || 0,
            });
        }, 400);
    }, true);

    // Drag
    var dragStart = null;
    document.addEventListener('mousedown', function(e) {
        if (e.button !== 0) return;
        dragStart = { x: e.clientX, y: e.clientY, el: e.target };
        isDragging = false;
    }, true);
    document.addEventListener('mousemove', function(e) {
        if (!dragStart) return;
        var dx = e.clientX - dragStart.x, dy = e.clientY - dragStart.y;
        if (!isDragging && Math.sqrt(dx*dx + dy*dy) > 5) isDragging = true;
    }, true);
    document.addEventListener('mouseup', function(e) {
        if (dragStart && isDragging) {
            postAction('drag', dragStart.el, {
                from_x: dragStart.x, from_y: dragStart.y,
                to_x: e.clientX, to_y: e.clientY,
            });
        }
        dragStart = null;
        isDragging = false;
    }, true);

    // ── Navigation tracking ─────────────────────────────────────────────

    var navUrl = location.pathname + location.search;
    setInterval(function() {
        var url = location.pathname + location.search;
        if (url !== navUrl) {
            flushPendingInput();
            postAction('navigate', document.body, { url: url, from_url: navUrl });
            navUrl = url;
        }
    }, 300);

    // ── Form submission tracking ────────────────────────────────────────

    document.addEventListener('submit', function(e) {
        flushPendingInput();
        var form = e.target;
        var action = form.action || location.href;
        var method = (form.method || 'GET').toUpperCase();
        var data = {};
        try {
            var fd = new FormData(form);
            fd.forEach(function(v, k) { data[k] = typeof v === 'string' ? v.slice(0, 100) : '(file)'; });
        } catch(ex) {}
        postAction('submit', form, { url: action, method: method, formData: data });
    }, true);

    // ── Initial page load ───────────────────────────────────────────────

    function mirrorFormState() {
        // outerHTML serializes attributes, not live DOM properties — typed
        // text, checked radios, and selected options are invisible unless
        // mirrored into attributes first.
        try {
            document.querySelectorAll('input').forEach(function(el) {
                if (el.type === 'checkbox' || el.type === 'radio') {
                    if (el.checked) el.setAttribute('checked', '');
                    else el.removeAttribute('checked');
                } else if (el.type !== 'password' && el.type !== 'file') {
                    el.setAttribute('value', el.value);
                }
            });
            document.querySelectorAll('textarea').forEach(function(el) {
                el.textContent = el.value;
            });
            document.querySelectorAll('select').forEach(function(el) {
                for (var i = 0; i < el.options.length; i++) {
                    if (el.options[i].selected) el.options[i].setAttribute('selected', '');
                    else el.options[i].removeAttribute('selected');
                }
            });
        } catch(e) { /* never block the capture */ }
    }

    function captureSnapshot() {
        try {
            mirrorFormState();
            var html = document.documentElement.outerHTML;
            // 2MB cap: a truncated snapshot cannot be re-rendered for
            // axtree/screenshot derivation, so keep this generous.
            if (html.length > 2000000) {
                html = html.slice(0, 2000000) + '<!-- truncated -->';
            }
            return html;
        } catch(e) {
            return '';
        }
    }

    function buildAxtree(el, depth) {
        if (!el || depth > 6) return null;
        var tag = el.tagName ? el.tagName.toLowerCase() : '';
        if (!tag || tag === 'script' || tag === 'style' || tag === 'noscript') return null;
        var role = el.getAttribute('role') || '';
        var ariaLabel = el.getAttribute('aria-label') || '';
        var name = el.getAttribute('name') || '';
        var text = '';
        // Get direct text content (not children's)
        for (var i = 0; i < el.childNodes.length; i++) {
            if (el.childNodes[i].nodeType === 3) {
                var t = el.childNodes[i].textContent.trim();
                if (t) text += (text ? ' ' : '') + t;
            }
        }
        if (text.length > 100) text = text.slice(0, 97) + '...';
        var label = ariaLabel || el.title || '';
        var node = {};
        // Determine role
        if (role) node.role = role;
        else if (tag === 'a') node.role = 'link';
        else if (tag === 'button' || (tag === 'input' && el.type === 'submit')) node.role = 'button';
        else if (tag === 'input') node.role = 'input-' + (el.type || 'text');
        else if (tag === 'select') node.role = 'select';
        else if (tag === 'textarea') node.role = 'textarea';
        else if (tag === 'img') node.role = 'img';
        else if (/^h[1-6]$/.test(tag)) node.role = 'heading';
        else if (tag === 'nav') node.role = 'navigation';
        else if (tag === 'form') node.role = 'form';
        else if (tag === 'table') node.role = 'table';
        else node.role = tag;

        if (text) node.text = text;
        if (label) node.label = label;
        if (tag === 'a' && el.href) node.href = el.getAttribute('href');
        if (tag === 'input' || tag === 'textarea') node.value = (el.value || '').slice(0, 50);
        if (tag === 'select') node.value = el.value || '';

        // Children
        var kids = [];
        for (var j = 0; j < el.children.length; j++) {
            var child = buildAxtree(el.children[j], depth + 1);
            if (child) kids.push(child);
        }
        if (kids.length) node.children = kids;

        // Skip empty container divs/spans
        if (!text && !label && !role && !node.value && (tag === 'div' || tag === 'span')) {
            if (kids.length === 0) return null;
            if (kids.length === 1) return kids[0];
        }
        return node;
    }

    function captureAxtree() {
        try {
            var tree = buildAxtree(document.body, 0);
            var str = JSON.stringify(tree);
            if (str.length > 100000) str = str.slice(0, 100000) + '...';
            return str;
        } catch(e) {
            return '';
        }
    }

    function makeObservation() {
        // "axtree" (YAML aria-snapshot) and "screenshot" are derived
        // server-side at save time from the snapshot; the in-page JSON
        // walker is kept as axtree_json for backward compatibility.
        return {
            mw: 'observation',
            url: location.pathname + location.search,
            title: document.title || '',
            timestamp: new Date().toISOString(),
            snapshot: captureSnapshot(),
            axtree_json: captureAxtree(),
            scroll_top: window.scrollY || 0,
            viewport: {width: window.innerWidth, height: window.innerHeight},
        };
    }

    function postPageLoad() {
        post(makeObservation());
    }

    if (document.readyState === 'complete') {
        setTimeout(postPageLoad, 200);
    } else {
        window.addEventListener('load', function() { setTimeout(postPageLoad, 200); });
    }
})();
