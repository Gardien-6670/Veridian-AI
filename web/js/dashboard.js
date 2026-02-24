// ══════════════════════════════════════════════════════════════════
// CONFIGURATION
// ══════════════════════════════════════════════════════════════════

const API_URL = "https://api.veridiancloud.xyz";
const CLIENT_ID = "1475845849333498038";
const REDIRECT_URI = "https://veridiancloud.xyz/dashboard.html";

// ══════════════════════════════════════════════════════════════════
// OAUTH2 HANDLER
// ══════════════════════════════════════════════════════════════════

/**
 * Récupère le code OAuth depuis l'URL et l'échange contre user + guilds
 */
async function handleOAuth() {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");

    if (code) {
        // Nettoyer l'URL sans recharger la page
        window.history.replaceState({}, document.title, "/dashboard.html");

        // Envoyer le code au backend Flask pour l'échanger
        try {
            const res = await fetch(`${API_URL}/auth/discord`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ code })
            });

            if (!res.ok) {
                const errorData = await res.json();
                console.error("❌ OAuth error:", errorData);
                showLoginScreen();
                return;
            }

            const data = await res.json();

            if (data.user && data.guilds !== undefined) {
                // Stocker user et guilds en sessionStorage
                sessionStorage.setItem("vai_user", JSON.stringify(data.user));
                sessionStorage.setItem("vai_guilds", JSON.stringify(data.guilds));
                
                // Afficher le dashboard avec les données
                showDashboard(data.user, data.guilds);
                console.log("✓ OAuth successful:", data.user.username);
                return;
            } else {
                console.error("❌ Invalid response structure");
                showLoginScreen();
            }
        } catch (error) {
            console.error("❌ OAuth handler error:", error);
            showLoginScreen();
        }
        return;
    }

    // Vérifier si déjà connecté via sessionStorage
    const savedUser = sessionStorage.getItem("vai_user");
    if (savedUser) {
        try {
            const user = JSON.parse(savedUser);
            const guilds = JSON.parse(sessionStorage.getItem("vai_guilds") || "[]");
            showDashboard(user, guilds);
            console.log("✓ Restored session for:", user.username);
            return;
        } catch (e) {
            console.error("❌ Session restore error:", e);
        }
    }

    // Pas connecté → afficher l'écran de login
    showLoginScreen();
}

// ══════════════════════════════════════════════════════════════════
// LOGIN / LOGOUT
// ══════════════════════════════════════════════════════════════════

/**
 * Redirige vers Discord OAuth2
 */
function loginWithDiscord() {
    const url = `https://discord.com/api/oauth2/authorize`
        + `?client_id=${CLIENT_ID}`
        + `&redirect_uri=${encodeURIComponent(REDIRECT_URI)}`
        + `&response_type=code`
        + `&scope=identify%20guilds`;
    
    console.log("🔗 Redirecting to Discord OAuth:", url);
    window.location.href = url;
}

/**
 * Déconnecter l'utilisateur
 */
function logout() {
    sessionStorage.removeItem("vai_user");
    sessionStorage.removeItem("vai_guilds");
    console.log("✓ Logged out");
    showLoginScreen();
}

// ══════════════════════════════════════════════════════════════════
// UI DISPLAY
// ══════════════════════════════════════════════════════════════════

/**
 * Affiche l'écran de login
 */
function showLoginScreen() {
    const loginScreen = document.getElementById("login-screen");
    const appContent = document.getElementById("app");
    
    if (loginScreen) loginScreen.style.display = "flex";
    if (appContent) appContent.style.display = "none";
    
    console.log("Showing login screen");
}

/**
 * Affiche le dashboard avec user + serveurs
 */
function showDashboard(user, guilds) {
    const loginScreen = document.getElementById("login-screen");
    const appContent = document.getElementById("app");
    
    if (loginScreen) loginScreen.style.display = "none";
    if (appContent) appContent.style.display = "flex";
    
    // Injecter la photo de profil
    const avatarEls = document.querySelectorAll(".user-avatar-img");
    avatarEls.forEach(el => {
        el.src = user.avatar;
        el.alt = user.username;
        el.title = user.username;
    });
    
    // Injecter le nom d'utilisateur
    document.querySelectorAll(".user-name").forEach(el => {
        el.textContent = user.username;
    });
    
    // Injecter le rôle
    document.querySelectorAll(".user-role").forEach(el => {
        el.textContent = user.is_super_admin ? "Super Admin" : "Server Admin";
    });
    
    // Remplir le sélecteur de serveurs
    const select = document.getElementById("server-select");
    if (select) {
        if (guilds && guilds.length > 0) {
            select.innerHTML = "";
            guilds.forEach(g => {
                const option = document.createElement("option");
                option.value = g.id;
                option.textContent = g.name;
                select.appendChild(option);
            });
        } else {
            // Aucun serveur commun
            showNoGuildsMessage();
        }
    }
    
    console.log(`✓ Dashboard shown with ${guilds ? guilds.length : 0} guilds`);
}

/**
 * Affiche un message si l'utilisateur n'a aucun serveur commun
 */
function showNoGuildsMessage() {
    const container = document.getElementById("app");
    if (container) {
        container.innerHTML = `
            <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;gap:20px">
                <div style="font-size:48px">🤔</div>
                <div style="font-size:18px;font-weight:600">Aucun serveur disponible</div>
                <div style="color:#888;font-size:14px;text-align:center;max-width:400px">
                    Vous n'êtes admin sur aucun serveur où Veridian AI est installé.
                    <br>Contactez l'admin de votre serveur pour installer le bot.
                </div>
                <button onclick="logout()" style="padding:10px 20px;background:#5865F2;color:white;border:none;border-radius:4px;cursor:pointer;margin-top:20px">
                    Retour
                </button>
            </div>
        `;
    }
}

// ══════════════════════════════════════════════════════════════════
// NAVIGATION
// ══════════════════════════════════════════════════════════════════

const pages = ['dashboard', 'tickets', 'orders', 'settings', 'kb'];

const pageMeta = {
  dashboard: { label: 'Dashboard',         sub: 'Vue d\'ensemble' },
  tickets:   { label: 'Tickets',           sub: 'Gestion des tickets' },
  orders:    { label: 'Orders',            sub: 'Commandes en attente' },
  settings:  { label: 'Settings',          sub: 'Configuration du bot' },
  kb:        { label: 'Knowledge Base',    sub: 'Base de connaissances' },
};

function navigateTo(page) {
  // Pages
  document.querySelectorAll('.page-content').forEach(el => el.classList.remove('active'));
  const target = document.getElementById('page-' + page);
  if (target) target.classList.add('active');

  // Nav items
  document.querySelectorAll('.nav-item[data-page]').forEach(el => {
    el.classList.toggle('active', el.dataset.page === page);
  });

  // Breadcrumb
  const meta = pageMeta[page] || {};
  const bc = document.getElementById('breadcrumb-page');
  if (bc) bc.textContent = meta.label || page;

  // Topbar sub
  const sub = document.getElementById('topbar-sub');
  if (sub) sub.textContent = meta.sub || '';
}

document.querySelectorAll('.nav-item[data-page]').forEach(el => {
  el.addEventListener('click', () => navigateTo(el.dataset.page));
});

// ══════════════════════════════════════════════════════════════════
// BAR CHART (Dashboard)
// ══════════════════════════════════════════════════════════════════
function buildBarChart() {
  const container = document.getElementById('bar-chart');
  if (!container) return;

  const data = [
    { day: 'Lun', val: 18 },
    { day: 'Mar', val: 32 },
    { day: 'Mer', val: 25 },
    { day: 'Jeu', val: 41 },
    { day: 'Ven', val: 29 },
    { day: 'Sam', val: 37 },
    { day: 'Auj', val: 44, today: true },
  ];
  const max = Math.max(...data.map(d => d.val));

  container.innerHTML = '';
  data.forEach(d => {
    const col = document.createElement('div');
    col.className = 'bar-col';
    const fill = document.createElement('div');
    fill.className = 'bar-fill' + (d.today ? ' today' : '');
    fill.style.height = '0%';
    fill.title = `${d.day} : ${d.val} tickets`;
    fill.setAttribute('data-height', Math.round(d.val / max * 100) + '%');
    const lbl = document.createElement('div');
    lbl.className = 'bar-label';
    lbl.textContent = d.day;
    col.appendChild(fill);
    col.appendChild(lbl);
    container.appendChild(col);
  });

  // Animate bars after render
  setTimeout(() => {
    container.querySelectorAll('.bar-fill').forEach(el => {
      el.style.transition = 'height 0.7s cubic-bezier(0.4,0,0.2,1)';
      el.style.height = el.dataset.height;
    });
  }, 80);
}

// ══════════════════════════════════════════════════════════════════
// PROGRESS BARS
// ══════════════════════════════════════════════════════════════════
function animateProgressBars() {
  document.querySelectorAll('.progress-fill[data-width]').forEach(el => {
    setTimeout(() => {
      el.style.width = el.dataset.width;
    }, 200);
  });
  document.querySelectorAll('.key-fill[data-width]').forEach(el => {
    setTimeout(() => {
      el.style.width = el.dataset.width;
    }, 300);
  });
}

// ══════════════════════════════════════════════════════════════════
// TOGGLE SWITCHES
// ══════════════════════════════════════════════════════════════════
document.querySelectorAll('.toggle-switch').forEach(sw => {
  sw.addEventListener('click', () => sw.classList.toggle('on'));
});

// ══════════════════════════════════════════════════════════════════
// ORDER ACTIONS
// ══════════════════════════════════════════════════════════════════
function validateOrder(btn, orderId, action) {
  const card = btn.closest('.order-card');
  if (!card) return;

  // Visual feedback
  card.style.transition = 'opacity 0.3s, transform 0.3s';
  card.style.opacity = '0.4';
  card.style.pointerEvents = 'none';

  setTimeout(() => {
    card.style.transform = 'translateX(20px)';
    card.style.opacity = '0';
    setTimeout(() => {
      card.style.display = 'none';

      // Update pending count badges
      const remaining = document.querySelectorAll('#page-orders .order-card:not([style*="none"])').length;
      document.querySelectorAll('[data-badge="orders"]').forEach(el => {
        el.textContent = remaining;
        if (remaining === 0) el.style.display = 'none';
      });

      // Show empty state if none left
      const container = document.getElementById('orders-list');
      if (container && !container.querySelector('.order-card:not([style*="none"])')) {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">✅</div>
            <div class="empty-text">Aucune commande en attente</div>
          </div>`;
      }
    }, 300);
  }, 200);
}

// ══════════════════════════════════════════════════════════════════
// KB — ADD ENTRY (mock)
// ══════════════════════════════════════════════════════════════════
const kbAddBtn = document.getElementById('kb-add-btn');
const kbForm = document.getElementById('kb-form');
if (kbAddBtn && kbForm) {
  kbAddBtn.addEventListener('click', () => {
    kbForm.style.display = kbForm.style.display === 'none' ? 'block' : 'none';
  });
}

// ══════════════════════════════════════════════════════════════════
// INIT
// ══════════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  handleOAuth();
  navigateTo('dashboard');
  buildBarChart();
  setTimeout(animateProgressBars, 300);
});
