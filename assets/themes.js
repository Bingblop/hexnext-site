/* #Hex Next website: the theme pack gallery.
 * A rolling tab strip of every pack and, for the chosen one, all of its art laid out the way the
 * app's press-and-hold sheet shows it. The tabs and the manifest (#themes-data) are written into
 * index.html by tools/build_themes.py; a panel and its pictures are only built when it is chosen. */
(function () {
  'use strict';
  var dataEl = document.getElementById('themes-data');
  var rail = document.getElementById('theme-rail');
  var panel = document.getElementById('theme-panel');
  if (!dataEl || !rail || !panel) return;
  var data;
  try { data = JSON.parse(dataEl.textContent); } catch (e) { return; }
  var themes = data.themes || [];
  if (!themes.length) return;

  var strip = rail.querySelector('.tabs');
  var tabs = Array.prototype.slice.call(strip.querySelectorAll('[role="tab"]'));
  var prevBtn = rail.querySelector('.rail-btn.prev');
  var nextBtn = rail.querySelector('.rail-btn.next');
  var section = document.getElementById('themes');
  var calm = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var LIST_ROWS = 9;
  var current = -1;
  var lookKey = null;       // the icon look stays chosen from pack to pack
  var near = false;         // the gallery is close to the screen: pictures may load
  var pending = [];         // work waiting for that

  /* ---------- small helpers ---------- */
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function lum(hex) {
    var c = [1, 3, 5].map(function (i) {
      var v = parseInt(hex.substr(i, 2), 16) / 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  }
  function inkOn(hex) { return lum(hex) > 0.4 ? '#10141C' : '#FFFFFF'; }
  function src(theme, file) { return data.base + theme.id + '/' + file + '?v=' + theme.v; }
  function cssUrl(theme, file) { return 'url("' + new URL(src(theme, file), document.baseURI).href + '")'; }
  function whenNear(fn) { if (near) fn(); else pending.push(fn); }
  function pct(v) { return (Math.round(v * 1000) / 1000) + '%'; }

  /** A square (or [span] tiles wide) window onto one tile of a sprite sheet [w] x [h] px. */
  function sprite(x, y, tile, w, h, span) {
    var s = el('i', 'sp');
    var tw = tile * (span || 1);
    s.style.backgroundSize = pct(w / tw * 100) + ' ' + pct(h / tile * 100);
    s.style.backgroundPosition = pct(w > tw ? x / (w - tw) * 100 : 0) + ' ' + pct(h > tile ? y / (h - tile) * 100 : 0);
    return s;
  }
  function picture(theme, file, alt, w, h) {
    var img = new Image();
    img.alt = alt;
    img.width = w; img.height = h;
    img.decoding = 'async';
    img.loading = 'lazy';
    whenNear(function () { img.src = src(theme, file); });
    return img;
  }
  /** Sets a sprite sheet on [node] as --sheet once it has loaded, so tiles never show half a picture. */
  function sheet(node, theme, file) {
    whenNear(function () {
      var probe = new Image();
      var url = src(theme, file);
      node.dataset.sheet = url;
      probe.onload = probe.onerror = function () {
        if (node.dataset.sheet !== url) return;   // a newer look was chosen meanwhile
        node.style.setProperty('--sheet', cssUrl(theme, file));
        node.classList.add('ready');
      };
      probe.src = url;
    });
  }
  function card(title, sub, wide) {
    var c = el('section', 'art' + (wide ? ' wide' : ''));
    var head = el('div', 'art-head');
    head.appendChild(el('h4', null, title));
    var s = el('p', 'art-sub', sub);
    head.appendChild(s);
    c.appendChild(head);
    c.sub = s;
    return c;
  }

  /* ---------- one pack ---------- */
  function build(index) {
    var theme = themes[index];
    var layout = data.layouts[theme.l];
    var c = theme.c;
    var root = el('div', 'pack-body');
    var vars = {
      '--p-bg': c.bg, '--p-card': c.card, '--p-ink': inkOn(c.bg), '--p-card-ink': inkOn(c.card),
      '--p-accent': c.accent, '--p-page': c.page, '--p-page-ink': inkOn(c.page)
    };
    Object.keys(vars).forEach(function (k) { root.style.setProperty(k, vars[k]); });

    /* heading: name, colours, previous and next */
    var head = el('header', 'pack-head');
    var title = el('div', 'pack-title');
    title.appendChild(el('span', 'eyebrow', 'Pack ' + (index + 1) + ' of ' + themes.length));
    title.appendChild(el('h3', null, theme.name));
    title.appendChild(el('p', null, 'All art · every look'));
    head.appendChild(title);
    var sw = el('div', 'swatches');
    sw.setAttribute('role', 'img');
    sw.setAttribute('aria-label', theme.name + ' colours');
    [c.bg, c.card, c.accent, c.second, c.page, c.pageAccent].forEach(function (hex) {
      var i = el('i'); i.style.background = hex; i.title = hex; sw.appendChild(i);
    });
    head.appendChild(sw);
    head.appendChild(stepper(index, false));
    root.appendChild(head);

    /* wallpaper and notification cards, side by side as in the app */
    if (layout.pics && layout.pics.length) {
      var pics = el('div', 'pics');
      pics.tabIndex = 0;
      pics.setAttribute('role', 'group');
      pics.setAttribute('aria-label', theme.name + ' wallpaper and notification cards');
      layout.pics.forEach(function (p) {
        var fig = el('figure', p[2]);
        var wall = p[2] === 'wall';
        fig.appendChild(picture(theme, p[0], theme.name + ': ' + p[1].toLowerCase(), wall ? 540 : 720, wall ? 1170 : 320));
        fig.appendChild(el('figcaption', null, p[1]));
        pics.appendChild(fig);
      });
      root.appendChild(pics);
    }

    var arts = el('div', 'arts');

    /* the icon parts, in the chosen look */
    var looks = layout.looks || [];
    if (looks.length && layout.parts.length) {
      var chosen = Math.max(0, looks.map(function (l) { return l.k; }).indexOf(lookKey));
      var bar = el('div', 'looks');
      bar.appendChild(el('span', 'looks-label', 'Icon colours'));
      var group = el('div', 'seg');
      group.setAttribute('role', 'radiogroup');
      group.setAttribute('aria-label', 'Icon colours');
      var note = el('p', 'looks-note');
      var cards = [];
      var buttons = looks.map(function (look, i) {
        var b = el('button', null, look.label);
        b.type = 'button';
        b.setAttribute('role', 'radio');
        b.addEventListener('click', function () { pick(i, true); });
        b.addEventListener('keydown', function (e) {
          var d = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0;
          if (!d) return;
          e.preventDefault();
          var n = (i + d + looks.length) % looks.length;
          pick(n, true);
          buttons[n].focus();
        });
        group.appendChild(b);
        return b;
      });
      var pick = function (i, remember) {
        if (remember) lookKey = looks[i].k;
        buttons.forEach(function (b, n) {
          b.setAttribute('aria-checked', n === i ? 'true' : 'false');
          b.tabIndex = n === i ? 0 : -1;
        });
        note.textContent = looks[i].k === 'accent'
          ? 'Accent tint follows your own accent colour in the app. Shown here in the pack’s accent.'
          : looks.length > 1 ? 'Every pack comes in ' + looks.length + ' icon looks. Pick one to see all of its art.' : '';
        cards.forEach(function (cd) { cd.card.sub.textContent = looks[i].label + ' · ' + cd.count; });
        sheet(arts, theme, looks[i].file);
      };
      if (looks.length > 1) bar.appendChild(group);
      bar.appendChild(note);
      root.appendChild(bar);

      var W = layout.atlas[0], H = layout.atlas[1];
      layout.parts.forEach(function (part) {
        var cd = card(part.label, '', part.kind === 'round');
        var cols = Math.floor(W / part.t);
        var tile = function (i) { return sprite((i % cols) * part.t, part.y + Math.floor(i / cols) * part.t, part.t, W, H); };
        var listed = part.kind === 'list' ? Math.min(LIST_ROWS, part.names.length) : 0;
        if (listed) {
          var rows = el('ul', 'rows');
          for (var i = 0; i < listed; i++) {
            var li = el('li');
            li.appendChild(tile(i));
            li.appendChild(el('span', null, part.names[i]));
            rows.appendChild(li);
          }
          cd.appendChild(rows);
        }
        if (part.names.length > listed) {
          var grid = el('div', 'grid ' + part.kind + ' g-' + part.k);
          grid.setAttribute('role', 'img');
          grid.setAttribute('aria-label', part.label + ': ' + part.names.slice(listed).join(', '));
          for (var j = listed; j < part.names.length; j++) {
            var cell = el('span', 'cell');
            cell.title = part.names[j];
            cell.appendChild(tile(j));
            grid.appendChild(cell);
          }
          cd.appendChild(grid);
        }
        cards.push({ card: cd, count: part.names.length });
        arts.appendChild(cd);
      });
      pick(chosen, false);
    }

    /* switches, checkboxes, radios and the dialer, by day and by night */
    var ps = layout.sheet;
    var modes = layout.modes || [];
    if (ps && modes.length) {
      var PW = ps[1] * 96, PH = ps[2] * 96;
      var at = function (cellInfo, span) { return sprite(cellInfo[1] * 96, cellInfo[2] * 96, 96, PW, PH, span); };
      var parts = el('div', 'arts-parts');
      parts.style.display = 'contents';
      modes.forEach(function (mode) {
        if (!mode.switches.length && !mode.controls.length) return;
        var cd = card('Switches, checkboxes and radios', mode.label + ' · ' + (mode.switches.length + mode.controls.length));
        var surface = el('div', 'surface ' + mode.k);
        if (mode.switches.length) {
          var rows = el('ul', 'rows switches');
          mode.switches.forEach(function (s) {
            var li = el('li');
            li.appendChild(el('span', null, s[0]));
            var pic = at(s, 2);
            pic.classList.add('switch');
            pic.setAttribute('role', 'img');
            pic.setAttribute('aria-label', 'Switch, ' + s[0].toLowerCase());
            li.appendChild(pic);
            rows.appendChild(li);
          });
          surface.appendChild(rows);
        }
        if (mode.controls.length) {
          var grid = el('div', 'grid plain');
          grid.setAttribute('role', 'img');
          grid.setAttribute('aria-label', 'Checkbox and radio button art, ' + mode.label.toLowerCase());
          mode.controls.forEach(function (p) {
            var cell = el('span', 'cell'); cell.title = p[0]; cell.appendChild(at(p)); grid.appendChild(cell);
          });
          surface.appendChild(grid);
        }
        cd.appendChild(surface);
        parts.appendChild(cd);
      });
      modes.forEach(function (mode) {
        if (!mode.panel && !mode.dial.length) return;
        var cd = card('Phone dialer art', mode.label + ' · ' + (mode.dial.length + (mode.panel ? 1 : 0)));
        var box = el('div', 'dial');
        if (mode.panel) {
          var fig = el('figure', 'keypad ' + mode.k);
          fig.appendChild(picture(theme, mode.panel, theme.name + ': picture behind the keypad, ' + mode.label.toLowerCase(), 480, 604));
          box.appendChild(fig);
        }
        if (mode.dial.length) {
          var grid = el('div', 'grid g-dial');
          grid.setAttribute('role', 'img');
          grid.setAttribute('aria-label', 'Dialer buttons: ' + mode.dial.map(function (p) { return p[0]; }).join(', '));
          mode.dial.forEach(function (p) {
            var cell = el('span', 'cell'); cell.title = p[0]; cell.appendChild(at(p)); grid.appendChild(cell);
          });
          box.appendChild(grid);
        }
        cd.appendChild(box);
        parts.appendChild(cd);
      });
      sheet(parts, theme, ps[0]);
      arts.appendChild(parts);
    }
    root.appendChild(arts);

    var foot = el('footer', 'pack-foot');
    foot.appendChild(stepper(index, true));
    root.appendChild(foot);
    return root;
  }

  /** Previous / next pack buttons; the ones under a pack name the packs and jump back to its top. */
  function stepper(index, named) {
    var box = el('div', 'stepper' + (named ? ' named' : ''));
    [-1, 1].forEach(function (d) {
      var to = (index + d + themes.length) % themes.length;
      var b = el('button', d < 0 ? 'prev' : 'next');
      b.type = 'button';
      var arrow = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="' + (d < 0 ? 'M15 5l-7 7 7 7' : 'M9 5l7 7-7 7') + '"/></svg>';
      b.innerHTML = arrow;
      if (named) {
        var label = el('span', null, themes[to].name);
        if (d < 0) b.appendChild(label); else b.insertBefore(label, b.firstChild);
      }
      b.setAttribute('aria-label', (d < 0 ? 'Previous pack: ' : 'Next pack: ') + themes[to].name);
      b.addEventListener('click', function () {
        select(to, { top: named });
      });
      box.appendChild(b);
    });
    return box;
  }

  /* ---------- choosing a pack ---------- */
  function select(index, opts) {
    opts = opts || {};
    if (index === current) return;
    current = index;
    var theme = themes[index];
    tabs.forEach(function (t, i) {
      t.setAttribute('aria-selected', i === index ? 'true' : 'false');
      t.tabIndex = i === index ? 0 : -1;
    });
    panel.setAttribute('aria-labelledby', tabs[index].id);
    var body = build(index);
    var old = panel.querySelector('.pack-body');
    if (old) panel.replaceChild(body, old); else panel.appendChild(body);
    if (!calm && old) { body.classList.add('in'); }
    reveal(tabs[index], opts.instant);
    if (opts.focus) tabs[index].focus({ preventScroll: true });
    if (opts.top) {
      var y = panel.getBoundingClientRect().top + window.pageYOffset - 64 - rail.offsetHeight - 8;
      window.scrollTo({ top: y, behavior: calm ? 'auto' : 'smooth' });
    }
    if (opts.hash !== false && window.history && history.replaceState) {
      try { history.replaceState(null, '', '#theme-' + theme.id); } catch (e) { /* file: pages */ }
    }
  }

  /** Scrolls the strip, never the page, so that [tab] is in view with some room around it. */
  function reveal(tab, instant) {
    var room = 56;
    var left = tab.offsetLeft - room;
    var right = tab.offsetLeft + tab.offsetWidth + room;
    var to = strip.scrollLeft;
    if (left < strip.scrollLeft) to = left;
    else if (right > strip.scrollLeft + strip.clientWidth) to = right - strip.clientWidth;
    if (to !== strip.scrollLeft) strip.scrollTo({ left: Math.max(0, to), behavior: instant || calm ? 'auto' : 'smooth' });
  }

  tabs.forEach(function (tab, i) {
    tab.addEventListener('click', function (e) {
      if (dragged) { e.preventDefault(); return; }
      select(i);
    });
  });
  strip.addEventListener('keydown', function (e) {
    var i = tabs.indexOf(document.activeElement);
    if (i < 0) return;
    var n = e.key === 'ArrowRight' ? i + 1 : e.key === 'ArrowLeft' ? i - 1 : e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length - 1 : null;
    if (n === null) return;
    e.preventDefault();
    n = (n + tabs.length) % tabs.length;
    select(n, { focus: true });
  });

  /* ---------- the rolling strip: arrows, wheel, drag ---------- */
  function edges() {
    var max = strip.scrollWidth - strip.clientWidth;
    var start = strip.scrollLeft <= 2, end = strip.scrollLeft >= max - 2;
    prevBtn.hidden = max <= 4 || start;
    nextBtn.hidden = max <= 4 || end;
    rail.classList.toggle('at-start', start);
    rail.classList.toggle('at-end', end);
  }
  function page(dir) {
    strip.scrollBy({ left: dir * Math.max(160, strip.clientWidth * 0.8), behavior: calm ? 'auto' : 'smooth' });
  }
  prevBtn.addEventListener('click', function () { page(-1); });
  nextBtn.addEventListener('click', function () { page(1); });
  strip.addEventListener('scroll', edges, { passive: true });
  window.addEventListener('resize', edges);

  strip.addEventListener('wheel', function (e) {
    if (e.ctrlKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) return;   // a sideways wheel scrolls it already
    var max = strip.scrollWidth - strip.clientWidth;
    var d = e.deltaY * (e.deltaMode === 1 ? 32 : 1);
    if ((d < 0 && strip.scrollLeft <= 0) || (d > 0 && strip.scrollLeft >= max - 1)) return;   // at an end the page scrolls on
    e.preventDefault();
    strip.scrollBy({ left: d, behavior: 'auto' });
  }, { passive: false });

  var dragged = false;
  var drag = null;
  strip.addEventListener('pointerdown', function (e) {
    if (e.pointerType !== 'mouse' || e.button !== 0) return;   // touch scrolls natively
    drag = { x: e.clientX, left: strip.scrollLeft, moved: false };
    dragged = false;
  });
  window.addEventListener('pointermove', function (e) {
    if (!drag) return;
    var dx = e.clientX - drag.x;
    if (!drag.moved && Math.abs(dx) < 6) return;
    drag.moved = true;
    dragged = true;
    rail.classList.add('dragging');
    strip.scrollLeft = drag.left - dx;
  });
  function drop() {
    if (!drag) return;
    drag = null;
    rail.classList.remove('dragging');
    setTimeout(function () { dragged = false; }, 0);   // after the click that ends the drag
  }
  window.addEventListener('pointerup', drop);
  window.addEventListener('pointercancel', drop);
  strip.addEventListener('dragstart', function (e) { e.preventDefault(); });

  /* ---------- pictures load when the gallery comes near ---------- */
  function arrive() {
    if (near) return;
    near = true;
    pending.splice(0).forEach(function (fn) { fn(); });
  }
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      if (entries.some(function (en) { return en.isIntersecting; })) { io.disconnect(); arrive(); }
    }, { rootMargin: '900px 0px' });
    io.observe(section || panel);
  } else {
    arrive();
  }

  /* ---------- start: the pack named in the address, else the first ---------- */
  function fromHash() {
    var m = /^#theme-([a-z0-9_-]+)$/.exec(location.hash);
    if (!m) return -1;
    for (var i = 0; i < themes.length; i++) if (themes[i].id === m[1]) return i;
    return -1;
  }
  var first = fromHash();
  select(first < 0 ? 0 : first, { instant: true, hash: false });
  edges();
  if (first >= 0 && section) {
    arrive();
    window.addEventListener('load', function () { section.scrollIntoView(); });
  }
  window.addEventListener('hashchange', function () {
    var i = fromHash();
    if (i >= 0) { select(i, { hash: false }); section.scrollIntoView(); }
  });
})();
