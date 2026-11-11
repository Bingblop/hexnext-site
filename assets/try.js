/* #Hex Next website demo: a free AI theme generator.
 * Asks a free, keyless, open-source model (GPT-OSS 20B served by Pollinations) for a theme,
 * then paints it onto mock One UI screens. If the free model is busy or slow, a small local
 * generator makes a theme from the words in the prompt, so the demo always shows a result. */
(function () {
  'use strict';
  var root = document.getElementById('try');
  if (!root) return;
  var form = root.querySelector('form');
  var input = root.querySelector('#try-input');
  var button = root.querySelector('#try-go');
  var status = root.querySelector('#try-status');
  var stage = root.querySelector('.try-stage');
  var nameEl = root.querySelector('#try-name');
  var tagEl = root.querySelector('#try-tag');
  var swatchEl = root.querySelector('#try-swatches');
  var wallImgs = root.querySelectorAll('.t-wall');

  var SYSTEM = 'You design Samsung One UI phone themes. Reply with ONLY a JSON object, no prose: ' +
    '{"name":string (2-3 words),"tagline":string (under 8 words),' +
    '"colors":{"background":hex,"surface":hex,"primary":hex,"secondary":hex,"accent":hex,"text":hex,"muted":hex},' +
    '"iconShape":"circle"|"squircle"|"square","iconStyle":"3d"|"filled"|"outline" (use "3d", multicolour glossy icons, unless the user asks for flat or outline icons),"font":"rounded"|"sharp"|"classic",' +
    '"wallpaper":string (a short visual description of a phone wallpaper scene, no URL, no text in the picture)}. ' +
    'Use rich, harmonious colours that fit the mood; text must be readable on background.';

  /* ---------- colour helpers ---------- */
  function hex(c) {
    if (typeof c !== 'string') return null;
    var m = c.trim().match(/^#?([0-9a-f]{3}|[0-9a-f]{6})$/i);
    if (!m) return null;
    var h = m[1];
    if (h.length === 3) h = h.replace(/./g, function (x) { return x + x; });
    return '#' + h.toUpperCase();
  }
  function rgb(h) { return [1, 3, 5].map(function (i) { return parseInt(h.substr(i, 2), 16); }); }
  function lum(h) {
    var c = rgb(h).map(function (v) { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  }
  function contrast(a, b) { var x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); }
  function hsl(h, s, l) {
    s /= 100; l /= 100;
    var k = function (n) { return (n + h / 30) % 12; };
    var a = s * Math.min(l, 1 - l);
    var f = function (n) { return l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1))); };
    return '#' + [f(0), f(8), f(4)].map(function (v) { return ('0' + Math.round(v * 255).toString(16)).slice(-2); }).join('').toUpperCase();
  }
  function mix(a, b, t) {
    var x = rgb(a), y = rgb(b);
    return '#' + x.map(function (v, i) { return ('0' + Math.round(v + (y[i] - v) * t).toString(16)).slice(-2); }).join('').toUpperCase();
  }

  /* ---------- local generator (always works) ---------- */
  var MOODS = [
    [/ocean|sea|wave|deep|aqua|water|night/, 205], [/sunset|dusk|peach|warm|autumn|fall|cozy/, 22],
    [/forest|nature|jungle|moss|leaf|green|matcha/, 140], [/neon|cyber|synth|retro|80s|vapor/, 300],
    [/gold|luxury|royal|honey|amber/, 45], [/rose|love|pink|blossom|sakura|cherry/, 335],
    [/fire|lava|ember|volcano|red|dragon/, 6], [/ice|snow|frost|winter|arctic|glacier/, 192],
    [/space|galaxy|cosmic|star|nebula|purple|violet/, 265], [/coffee|chocolate|wood|earth|cabin/, 28],
    [/mint|fresh|spring|lime/, 160], [/storm|steel|grey|gray|minimal|mono/, 220]
  ];
  function seed(text) { var h = 0; for (var i = 0; i < text.length; i++) h = (h * 31 + text.charCodeAt(i)) >>> 0; return h; }
  function localTheme(prompt) {
    var p = prompt.toLowerCase(), s = seed(p), hue = s % 360;
    for (var i = 0; i < MOODS.length; i++) if (MOODS[i][0].test(p)) { hue = (MOODS[i][1] + (s % 16) - 8 + 360) % 360; break; }
    var light = /light|pastel|white|bright|day|cloud/.test(p);
    var mono = /minimal|mono|grey|gray/.test(p);
    var sat = mono ? 12 : 72;
    var STOP = /^(a|an|the|and|or|of|in|on|at|with|for|to|over|under|by|my|very|bit|little|some)$/i;
    var words = prompt.replace(/[^\w\s'-]/g, '').trim().split(/\s+/).filter(function (w) { return !STOP.test(w); }).slice(0, 2)
      .map(function (w) { return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase(); }).join(' ');
    return {
      name: words || 'My Theme',
      tagline: 'A quick local take on your idea',
      colors: light ? {
        background: hsl(hue, 30, 96), surface: hsl(hue, 35, 99), primary: hsl(hue, sat, 44),
        secondary: hsl((hue + 40) % 360, sat - 10, 48), accent: hsl((hue + 180) % 360, sat, 50),
        text: hsl(hue, 30, 12), muted: hsl(hue, 12, 42)
      } : {
        background: hsl(hue, 40, 7), surface: hsl(hue, 34, 13), primary: hsl(hue, sat + 10, 60),
        secondary: hsl((hue + 40) % 360, sat, 62), accent: hsl((hue + 180) % 360, sat + 15, 64),
        text: hsl(hue, 20, 95), muted: hsl(hue, 14, 66)
      },
      iconShape: ['circle', 'squircle', 'square'][s % 3],
      font: /elegant|vintage|classic|royal|luxury|book|paper/.test(p) ? 'classic' : /tech|cyber|neon|city|minimal|modern|glass/.test(p) ? 'sharp' : 'rounded',
      iconStyle: /\bflat\b/.test(p) ? 'filled' : /outline|line icons/.test(p) ? 'outline' : '3d',
      wallpaper: prompt
    };
  }

  /* ---------- tidy any theme so every screen stays readable ---------- */
  function tidy(t, prompt) {
    var base = localTheme(prompt), c = (t && t.colors) || {}, out = {};
    ['background', 'surface', 'primary', 'secondary', 'accent', 'text', 'muted'].forEach(function (k) {
      out[k] = hex(c[k]) || base.colors[k];
    });
    var dark = lum(out.background) < 0.35;
    if (contrast(out.text, out.background) < 4.5) out.text = dark ? '#F4F6FB' : '#111318';
    if (contrast(out.surface, out.background) < 1.08) out.surface = mix(out.background, out.text, 0.07);
    if (contrast(out.muted, out.surface) < 3) out.muted = mix(out.text, out.surface, 0.38);
    ['primary', 'secondary', 'accent'].forEach(function (k) {
      if (contrast(out[k], out.surface) < 2.2) out[k] = mix(out[k], out.text, 0.45);
    });
    return {
      name: (t && typeof t.name === 'string' && t.name.trim().slice(0, 32)) || base.name,
      tagline: (t && typeof t.tagline === 'string' && t.tagline.trim().slice(0, 60)) || base.tagline,
      colors: out,
      iconShape: ['circle', 'squircle', 'square'].indexOf(t && t.iconShape) >= 0 ? t.iconShape : base.iconShape,
      font: ['rounded', 'sharp', 'classic'].indexOf(t && t.font) >= 0 ? t.font : base.font,
      iconStyle: ['3d', 'filled', 'outline'].indexOf(t && t.iconStyle) >= 0 ? t.iconStyle : base.iconStyle,
      wallpaper: (t && typeof t.wallpaper === 'string' && !/https?:/.test(t.wallpaper) && t.wallpaper.slice(0, 220)) || prompt
    };
  }

  /* ---------- paint ---------- */
  var FONTS = {
    rounded: '"Nunito","Varela Round",ui-rounded,system-ui,sans-serif',
    sharp: '"Space Grotesk",Inter,system-ui,sans-serif',
    classic: 'Georgia,"Times New Roman",serif'
  };
  var RADII = { circle: '50%', squircle: '32%', square: '18%' };
  var LABELS = [['background', 'Background'], ['surface', 'Cards'], ['primary', 'Primary'], ['secondary', 'Secondary'], ['accent', 'Accent'], ['text', 'Text'], ['muted', 'Subtext']];

  var ARTS = [
    [/space|galaxy|cosmic|star|nebula|night|purple|violet/, 'galaxy-mood'],
    [/fire|lava|energy|storm|lightning|power|volcan|dragon|beam/, 'kameha-mood'],
    [/comic|hero|pop|retro|80s|bold|explosion|candy/, 'heroes-mood'],
    [/ocean|sea|wave|water|silk|flow|aurora|pastel|blossom|sakura|sunset|autumn|forest/, 'palette-wave'],
    [/glass|crystal|ice|minimal|tech|cyber|neon|city/, 'hero-backdrop']
  ];
  function wallpaperUrl(t, prompt) {
    var text = (prompt + ' ' + t.wallpaper).toLowerCase();
    for (var i = 0; i < ARTS.length; i++) if (ARTS[i][0].test(text)) return 'assets/art/' + ARTS[i][1] + '.webp';
    return 'assets/art/' + ['palette-wave', 'galaxy-mood', 'hero-backdrop', 'beta-glow'][seed(prompt) % 4] + '.webp';
  }

  var state = null, lastPrompt = '';

  function paintColors(t) {
    var c = t.colors, s = stage.style, r = root.style;
    [s, r].forEach(function (st) {
      st.setProperty('--t-bg', c.background); st.setProperty('--t-card', c.surface);
      st.setProperty('--t-pri', c.primary); st.setProperty('--t-sec', c.secondary);
      st.setProperty('--t-acc', c.accent); st.setProperty('--t-fg', c.text); st.setProperty('--t-mut', c.muted);
    });
    s.setProperty('--t-on', contrast('#FFFFFF', c.primary) >= 3 ? '#FFFFFF' : '#111318');
    s.setProperty('--t-font', FONTS[t.font]); s.setProperty('--t-ic', RADII[t.iconShape]);
    stage.setAttribute('data-icons', t.iconStyle);
    LABELS.forEach(function (l) {
      var inp = swatchEl.querySelector('input[data-k="' + l[0] + '"]');
      if (inp && inp.value.toUpperCase() !== c[l[0]]) inp.value = c[l[0]];
      var code = swatchEl.querySelector('span[data-k="' + l[0] + '"]');
      if (code) code.textContent = c[l[0]];
    });
    ['iconShape', 'iconStyle', 'font'].forEach(function (k) {
      var sel = root.querySelector('select[data-k="' + k + '"]');
      if (sel) sel.value = t[k];
    });
  }

  function paint(t, prompt) {
    state = t; lastPrompt = prompt;
    nameEl.textContent = t.name;
    tagEl.textContent = t.tagline;
    paintColors(t);
    var url = wallpaperUrl(t, prompt);
    wallImgs.forEach(function (img) {
      img.classList.remove('ready');
      img.onload = function () { img.classList.add('ready'); };
      img.onerror = function () { img.classList.remove('ready'); };
      img.src = url;
    });
  }

  // Palette editor: one colour picker per role, like the colour studio in the app.
  LABELS.forEach(function (l) {
    var li = document.createElement('li');
    li.innerHTML = '<label><input type="color" data-k="' + l[0] + '"><b></b><span data-k="' + l[0] + '"></span></label>';
    li.querySelector('b').textContent = l[1];
    li.querySelector('input').setAttribute('aria-label', l[1] + ' colour');
    swatchEl.appendChild(li);
  });
  swatchEl.addEventListener('input', function (e) {
    var k = e.target.getAttribute('data-k');
    if (!k || !state) return;
    state.colors[k] = e.target.value.toUpperCase();
    paintColors(state);
    status.textContent = 'Your own palette. Every screen follows your colours as you pick them.';
  });
  root.querySelectorAll('select[data-k]').forEach(function (sel) {
    sel.addEventListener('change', function () {
      if (!state) return;
      state[sel.getAttribute('data-k')] = sel.value;
      paintColors(state);
    });
  });
  var shuffle = root.querySelector('#try-shuffle');
  if (shuffle) shuffle.addEventListener('click', function () {
    if (!state) return;
    var hue = Math.floor(Math.random() * 360);
    var dark = lum(state.colors.background) < 0.35;
    var t = localTheme('x');
    t.colors = dark ? {
      background: hsl(hue, 40, 7), surface: hsl(hue, 34, 13), primary: hsl(hue, 80, 60),
      secondary: hsl((hue + 40) % 360, 70, 62), accent: hsl((hue + 180) % 360, 85, 64), text: hsl(hue, 20, 95), muted: hsl(hue, 14, 66)
    } : {
      background: hsl(hue, 30, 96), surface: hsl(hue, 35, 99), primary: hsl(hue, 72, 44),
      secondary: hsl((hue + 40) % 360, 62, 48), accent: hsl((hue + 180) % 360, 72, 50), text: hsl(hue, 30, 12), muted: hsl(hue, 12, 42)
    };
    state.colors = tidy(t, 'x').colors;
    paintColors(state);
    status.textContent = 'A fresh palette from one random seed colour, like the seed colour in the app.';
  });

  /* ---------- free agent ---------- */
  function askAgent(prompt) {
    var ctrl = window.AbortController ? new AbortController() : null;
    var timer = setTimeout(function () { if (ctrl) ctrl.abort(); }, 30000);
    return fetch('https://text.pollinations.ai/openai', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: ctrl ? ctrl.signal : undefined,
      body: JSON.stringify({
        model: 'openai-fast',
        messages: [{ role: 'system', content: SYSTEM }, { role: 'user', content: prompt }],
        referrer: 'hexnext-site'
      })
    }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    }).then(function (d) {
      var text = d && d.choices && d.choices[0] && d.choices[0].message && d.choices[0].message.content || '';
      var m = text.match(/\{[\s\S]*\}/);
      if (!m) throw new Error('no JSON');
      return JSON.parse(m[0]);
    }).finally(function () { clearTimeout(timer); });
  }

  var busy = false;
  function run(prompt) {
    prompt = (prompt || '').trim().slice(0, 200);
    if (!prompt || busy) return;
    busy = true;
    button.disabled = true;
    root.classList.add('working');
    status.textContent = 'The free open-source agent is designing your theme. This can take 10 to 30 seconds…';
    askAgent(prompt).then(function (t) {
      paint(tidy(t, prompt), prompt);
      status.textContent = 'Made by the free open-source agent (GPT-OSS 20B). Tap any part to recolour it, or follow up below.';
    }).catch(function () {
      paint(tidy(null, prompt), prompt);
      status.textContent = 'The free agent is busy right now, so this demo built a quick theme from your words instead. Try again in a minute for an AI one.';
    }).finally(function () {
      busy = false;
      button.disabled = false;
      root.classList.remove('working');
    });
  }

  /* ---------- tap an element: recolour it or ask the AI about just that part ---------- */
  var ROLE_NAMES = { background: 'Background', surface: 'Cards and panels', primary: 'Primary (switches, active tiles)', secondary: 'Secondary', accent: 'Accent', text: 'Text', muted: 'Subtext' };
  var pop = root.querySelector('#try-pop'), popTitle = root.querySelector('#pop-title');
  var popColor = root.querySelector('#pop-color'), popForm = root.querySelector('#pop-form'), popInput = root.querySelector('#pop-input');
  var result = root.querySelector('.try-result'), popRole = null, popEl = null;

  function closePop() {
    pop.hidden = true;
    if (popEl) popEl.classList.remove('picked');
    popEl = null;
  }
  stage.addEventListener('click', function (e) {
    var el = e.target.closest('[data-role]');
    if (!el || !state) return;
    e.stopPropagation();
    if (popEl) popEl.classList.remove('picked');
    popEl = el; popRole = el.getAttribute('data-role');
    el.classList.add('picked');
    popTitle.textContent = 'Recolour: ' + ROLE_NAMES[popRole];
    popColor.value = state.colors[popRole];
    popInput.value = '';
    var box = result.getBoundingClientRect(), r = el.getBoundingClientRect();
    pop.hidden = false;
    var w = pop.offsetWidth, x = Math.min(Math.max(8, r.left - box.left + r.width / 2 - w / 2), box.width - w - 8);
    pop.style.left = x + 'px';
    pop.style.top = (r.bottom - box.top + 10) + 'px';
  });
  root.querySelector('#pop-x').addEventListener('click', closePop);
  document.addEventListener('click', function (e) { if (!pop.hidden && !pop.contains(e.target)) closePop(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closePop(); });
  popColor.addEventListener('input', function () {
    if (!state || !popRole) return;
    state.colors[popRole] = popColor.value.toUpperCase();
    paintColors(state);
    status.textContent = ROLE_NAMES[popRole] + ' recoloured. Only that part changed.';
  });

  function refine(instruction, role) {
    instruction = (instruction || '').trim().slice(0, 200);
    if (!instruction || !state || busy) return;
    busy = true; root.classList.add('working');
    status.textContent = 'The free agent is changing ' + (role ? 'the ' + ROLE_NAMES[role].toLowerCase() : 'what you asked for') + ' and leaving the rest alone…';
    var current = JSON.stringify({ name: state.name, tagline: state.tagline, colors: state.colors, iconShape: state.iconShape, iconStyle: state.iconStyle, font: state.font });
    var ask = 'Current theme: ' + current + '\nChange request' + (role ? ' (about the "' + role + '" colour)' : '') + ': ' + instruction +
      '\nChange ONLY what the request names and keep every other value exactly the same. Reply with the full JSON object.';
    askAgent(ask).then(function (t) {
      var keepWall = state.wallpaper;
      var next = tidy(t, lastPrompt);
      next.wallpaper = keepWall;
      if (!t.name) next.name = state.name;
      state = next;
      nameEl.textContent = state.name; tagEl.textContent = state.tagline;
      paintColors(state);
      status.textContent = 'Updated by the free open-source agent. Keep going, or tap another part.';
    }).catch(function () {
      status.textContent = 'The free agent is busy right now. Use the colour picker for now, or try again in a minute.';
    }).finally(function () { busy = false; root.classList.remove('working'); });
  }
  popForm.addEventListener('submit', function (e) { e.preventDefault(); var r = popRole; closePop(); refine(popInput.value, r); });
  var follow = root.querySelector('#try-follow');
  if (follow) follow.addEventListener('submit', function (e) {
    e.preventDefault();
    var i = follow.querySelector('input');
    refine(i.value, null);
    i.value = '';
  });

  /* ---------- screen tabs over one big phone ---------- */
  var mocks = stage.querySelectorAll('.mock');
  var tabBtns = root.querySelectorAll('[data-screen]');
  function show(i) {
    closePop();
    mocks.forEach(function (m, j) { m.classList.toggle('on', j === i); });
    tabBtns.forEach(function (b, j) { b.setAttribute('aria-selected', j === i ? 'true' : 'false'); });
  }
  tabBtns.forEach(function (b) { b.addEventListener('click', function () { show(+b.getAttribute('data-screen')); }); });
  show(0);

  form.addEventListener('submit', function (e) { e.preventDefault(); run(input.value); });
  root.querySelectorAll('[data-idea]').forEach(function (chip) {
    chip.addEventListener('click', function () { input.value = chip.getAttribute('data-idea'); run(input.value); });
  });

  // First view: a ready-made theme, so the screens are never empty.
  var first = 'Deep ocean at night, calm, a little neon';
  paint(tidy({
    name: 'Midnight Tide', tagline: 'Calm depths with a neon glow',
    colors: { background: '#06121F', surface: '#0E2235', primary: '#2BD9F0', secondary: '#4F7BFF', accent: '#FF5FA2', text: '#EAF6FF', muted: '#8FB0C8' },
    iconShape: 'squircle', iconStyle: '3d', font: 'rounded', wallpaper: 'bioluminescent deep ocean at night, glowing jellyfish, soft neon light'
  }, first), first);
})();
