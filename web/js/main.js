// ── SCROLL REVEAL ──
const revealEls = document.querySelectorAll('.reveal');
const observer = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      e.target.classList.add('visible');
      observer.unobserve(e.target);
    }
  });
}, { threshold: 0.12 });
revealEls.forEach(el => observer.observe(el));

// ── NAVBAR SCROLL ──
const navbar = document.querySelector('.navbar');
window.addEventListener('scroll', () => {
  if (window.scrollY > 40) {
    navbar.style.background = 'rgba(10,15,13,0.95)';
    navbar.style.borderBottomColor = 'rgba(45,255,143,0.12)';
  } else {
    navbar.style.background = 'rgba(10,15,13,0.7)';
    navbar.style.borderBottomColor = 'rgba(45,255,143,0.08)';
  }
});

// ── COUNTER ANIMATION ──
function animateCounter(el, target, suffix = '') {
  const duration = 1800;
  const start = performance.now();
  const startVal = 0;

  function update(now) {
    const elapsed = now - start;
    const progress = Math.min(elapsed / duration, 1);
    // Ease out cubic
    const eased = 1 - Math.pow(1 - progress, 3);
    const current = Math.floor(startVal + (target - startVal) * eased);
    el.textContent = current.toLocaleString() + suffix;
    if (progress < 1) requestAnimationFrame(update);
  }

  requestAnimationFrame(update);
}

const countersObserver = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      const el = e.target;
      const target = parseInt(el.dataset.target);
      const suffix = el.dataset.suffix || '';
      animateCounter(el, target, suffix);
      countersObserver.unobserve(el);
    }
  });
}, { threshold: 0.5 });

document.querySelectorAll('[data-target]').forEach(el => countersObserver.observe(el));

// ── SMOOTH SCROLL FOR ANCHOR LINKS ──
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    const target = document.querySelector(a.getAttribute('href'));
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
});

// ── DISCORD INVITE BUTTON ──
document.querySelectorAll('[data-discord]').forEach(btn => {
  btn.addEventListener('click', () => {
    // Replace with real Discord invite link
    window.open('https://discord.com/api/oauth2/authorize', '_blank');
  });
});

// ── TYPING EFFECT for hero subtitle ──
const typingEl = document.getElementById('typing-text');
if (typingEl) {
  const texts = [
    'Support multilingue alimenté par l\'IA.',
    'Tickets traduits en temps réel.',
    'Votre communauté sans frontières.',
  ];
  let i = 0, j = 0, deleting = false;

  function type() {
    const current = texts[i];
    if (!deleting) {
      typingEl.textContent = current.slice(0, j + 1);
      j++;
      if (j === current.length) {
        deleting = true;
        setTimeout(type, 2200);
        return;
      }
    } else {
      typingEl.textContent = current.slice(0, j - 1);
      j--;
      if (j === 0) {
        deleting = false;
        i = (i + 1) % texts.length;
      }
    }
    setTimeout(type, deleting ? 35 : 55);
  }
  type();
}

// ── GRID TRACE ──
(function () {
  const canvas = document.getElementById('grid-trace');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const CELL = 60;
  let W, H, cols;

  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
    cols = Math.ceil(W / CELL) + 2;
  }
  resize();
  window.addEventListener('resize', resize);

  // ── Tout en coordonnées MONDE (Y absolu dans la page) ──
  // Le canvas est fixed : au dessin on fait simplement worldY - scrollY.
  // Ainsi le trail ne bouge jamais tout seul.

  let scrollY   = window.scrollY;
  let scrollVel = 0;
  let prevScroll = scrollY;

  // Position monde du point courant
  let wx = Math.floor(cols / 2) * CELL;
  let wy = (scrollY + H / 2);            // milieu de l'écran au démarrage
  // Snapper sur la grille
  wx = Math.round(wx / CELL) * CELL;
  wy = Math.round(wy / CELL) * CELL;

  // Cible monde
  let twx = wx;
  let twy = wy;

  // Le trail = liste de segments [{x1,y1,x2,y2}] en coords monde
  // On n'accumule PAS frame par frame, seulement quand on atteint un waypoint
  const segments = [];   // {ax, ay, bx, by} monde
  const MAX_SEG  = 18;

  // Dernier waypoint monde confirmé
  let lastWx = wx;
  let lastWy = wy;

  // Index de grille courant
  let gi = Math.round(wx / CELL);

  const STEP_MS = 460;
  let lastTime = 0;
  let timeSinceStep = 0;

  function pickNext() {
    const dirs = [
      {di:1,dj:0}, {di:-1,dj:0}, {di:0,dj:1}, {di:0,dj:-1}
    ];
    const weights = dirs.map(d => {
      let w = 1;
      if (scrollVel >  10 && d.dj ===  1) w = 5;
      if (scrollVel < -10 && d.dj === -1) w = 5;
      return w;
    });
    const tot = weights.reduce((a, b) => a + b, 0);
    let r = Math.random() * tot;
    for (let k = 0; k < dirs.length; k++) {
      r -= weights[k];
      if (r <= 0) {
        const ni = gi + dirs[k].di;
        // X : rester dans l'écran
        if (ni < 0 || ni >= cols) continue;
        const curGj = Math.round(twy / CELL);
        return { nx: ni * CELL, ny: (curGj + dirs[k].dj) * CELL };
      }
    }
    return { nx: twx, ny: twy };
  }

  function frame(now) {
    requestAnimationFrame(frame);
    const dt = Math.min(now - lastTime, 80);
    lastTime = now;

    // Scroll
    scrollY    = window.scrollY;
    scrollVel  = (scrollY - prevScroll) / (dt / 16);
    prevScroll = scrollY;

    // Step timer (accéléré par le scroll)
    const speed = 1 + Math.min(Math.abs(scrollVel) / 14, 4);
    timeSinceStep += dt * speed;
    if (timeSinceStep >= STEP_MS) {
      timeSinceStep = 0;
      const { nx, ny } = pickNext();
      // Enregistrer le segment monde : du waypoint précédent au nouveau
      segments.push({ ax: twx, ay: twy, bx: nx, by: ny });
      if (segments.length > MAX_SEG) segments.shift();
      twx = nx; twy = ny;
      gi  = Math.round(twx / CELL);
    }

    // Lissage de la tête (monde)
    wx += (twx - wx) * 0.13;
    wy += (twy - wy) * 0.13;

    // ── Dessin ──
    ctx.clearRect(0, 0, W, H);

    const n = segments.length;
    if (n === 0 && Math.abs(wx - twx) < 1 && Math.abs(wy - twy) < 1) return;

    // Dessiner les segments archivés (de plus en plus transparents vers l'arrière)
    for (let i = 0; i < n; i++) {
      const s = segments[i];
      const t = (i + 1) / (n + 1);
      const alpha = t * 0.18;
      const sy0 = s.ay - scrollY;
      const sy1 = s.by - scrollY;
      // Ignorer les segments hors écran
      if (Math.max(sy0, sy1) < -CELL || Math.min(sy0, sy1) > H + CELL) continue;
      ctx.beginPath();
      ctx.moveTo(s.ax, sy0);
      ctx.lineTo(s.bx, sy1);
      ctx.strokeStyle = `rgba(45,255,143,${alpha})`;
      ctx.lineWidth   = 1.5;
      ctx.shadowColor = 'rgba(45,255,143,0.18)';
      ctx.shadowBlur  = 5;
      ctx.stroke();
    }

    // Segment en cours : du dernier waypoint à la tête lissée
    const headScreenY = wy - scrollY;
    const tailScreenY = twy !== (segments.length ? segments[n-1].by : twy)
      ? twy - scrollY
      : (n > 0 ? segments[n-1].by - scrollY : headScreenY);

    // Dernier waypoint confirmé = twx/twy (avant lissage)
    const fromX = twx;
    const fromY = twy - scrollY;
    if (Math.abs(wx - twx) > 0.5 || Math.abs(wy - twy) > 0.5) {
      ctx.beginPath();
      ctx.moveTo(fromX, fromY);
      ctx.lineTo(wx, headScreenY);
      ctx.strokeStyle = 'rgba(45,255,143,0.18)';
      ctx.lineWidth   = 1.5;
      ctx.shadowColor = 'rgba(45,255,143,0.18)';
      ctx.shadowBlur  = 5;
      ctx.stroke();
    }

    // Point lumineux à la tête
    ctx.beginPath();
    ctx.arc(wx, headScreenY, 3, 0, Math.PI * 2);
    ctx.fillStyle   = 'rgba(45,255,143,0.5)';
    ctx.shadowColor = 'rgba(45,255,143,0.8)';
    ctx.shadowBlur  = 10;
    ctx.fill();
    ctx.shadowBlur = 0;
  }

  requestAnimationFrame(t => { lastTime = t; requestAnimationFrame(frame); });
})();