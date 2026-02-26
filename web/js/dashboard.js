/**
 * Veridian AI — Dashboard JS
 * Auth: JWT Bearer uniquement pour les appels /internal/*
 * CDC 2026: utilisateur lambda = Tickets + Settings uniquement
 *           Super Admin = tout (Dashboard, Orders, KB, Super Admin, clés Groq)
 */

// ─────────────────────────────────────────────────────────────
// CONFIG
// ─────────────────────────────────────────────────────────────
const API_BASE = "https://api.veridiancloud.xyz:201";
// redirect_uri DOIT correspondre exactement à DISCORD_REDIRECT_URI dans le .env
// et à ce qui est enregistré dans le portail Discord Developer
const DISCORD_REDIRECT_URI = "https://api.veridiancloud.xyz:201/auth/callback";

// ─────────────────────────────────────────────────────────────
// STATE
// ─────────────────────────────────────────────────────────────
let state = {
  token: null,
  user: null,
  guilds: [],
  currentGuild: null,
  currentPage: "dashboard",
};

// ─────────────────────────────────────────────────────────────
// INIT
// ─────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  bindStaticActions();
  initApp();
  initNav();
  initKB();
  initToggleSwitches();
  initProgressBars();
  initBarChart();
  initServerSelector();
  initSettingsSave();
  initTicketSearch();
  updateTopbarDate();
});

function bindStaticActions() {
  // Non-inline event handlers (required for strict CSP).
  const loginBtn = document.getElementById("login-discord-btn");
  if (loginBtn) loginBtn.addEventListener("click", loginWithDiscord);

  document.addEventListener("click", (e) => {
    const nav = e.target.closest("[data-nav]");
    if (nav) {
      navigateTo(nav.dataset.nav);
      return;
    }

    const actionEl = e.target.closest("[data-action]");
    if (actionEl) {
      const action = actionEl.dataset.action;
      if (action === "logout") return void logout();
      if (action === "close-transcript") return void closeTranscriptModal();
      if (action === "refresh-dashboard") return void loadDashboardStats();
      if (action === "refresh-tickets") return void loadTickets();
      if (action === "refresh-orders") return void loadOrders();
      if (action === "refresh-superadmin") return void loadSuperAdminData();
      if (action === "kb-cancel") {
        const form = document.getElementById("kb-form");
        if (form) form.style.display = "none";
        return;
      }
      if (action === "admin-activate-sub") return void adminActivateSub();
      if (action === "admin-revoke-sub") return void adminRevokeSub();
    }

    const ticketBtn = e.target.closest("[data-ticket-action]");
    if (ticketBtn) {
      const ticketId = parseInt(ticketBtn.dataset.ticketId, 10);
      if (!Number.isFinite(ticketId)) return;
      if (ticketBtn.dataset.ticketAction === "view") return void viewTicketTranscript(ticketId);
      if (ticketBtn.dataset.ticketAction === "close") return void closeTicket(ticketId);
    }

    const orderBtn = e.target.closest("[data-order-action]");
    if (orderBtn) {
      const orderId = orderBtn.dataset.orderId;
      const status = orderBtn.dataset.status;
      if (!orderId || !status) return;
      if (orderBtn.dataset.orderAction === "set-status") return void validateOrder(orderBtn, orderId, status);
    }

    const kbBtn = e.target.closest("[data-kb-action]");
    if (kbBtn) {
      const id = parseInt(kbBtn.dataset.kbId, 10);
      if (!Number.isFinite(id)) return;
      if (kbBtn.dataset.kbAction === "edit") return void editKBEntry(id);
      if (kbBtn.dataset.kbAction === "delete") return void deleteKBEntry(id);
    }
  });

  // Escape closes the transcript modal (if open).
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeTranscriptModal();
  });
}

async function initApp() {
  const urlParams = new URLSearchParams(window.location.search);
  const authCode  = urlParams.get("auth");   // temp_code apres OAuth (60s, usage unique)
  const urlError  = urlParams.get("error");

  if (urlError) {
    showLoginScreen();
    showToast("Erreur OAuth: " + urlError, "error");
    return;
  }

  // 1. Temp code dans l'URL → l'echanger contre le vrai JWT
  if (authCode) {
    // NE PAS effacer l'URL avant l'echange — si echec on peut reessayer
    await exchangeTempCode(authCode);
    return;
  }

  // 2. JWT deja en localStorage (session existante)
  const stored = localStorage.getItem("vai_token");
  if (stored) {
    state.token = stored;
    await loadUserFromToken();
    return;
  }

  // 3. Rien → ecran de login
  showLoginScreen();
}

async function exchangeTempCode(tempCode) {
  console.log("[auth] Echange temp_code...");
  try {
    const res = await fetch(API_BASE + "/auth/exchange", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ code: tempCode }),
    });

    console.log("[auth] /auth/exchange status:", res.status);

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      const msg = err.detail || "Echange de code echoue (" + res.status + ")";
      console.error("[auth] Erreur exchange:", msg);
      throw new Error(msg);
    }

    const data = await res.json();
    console.log("[auth] Exchange OK, user:", data.user && data.user.username);

    state.token  = data.token;
    state.user   = data.user;
    state.guilds = data.guilds || [];
    localStorage.setItem("vai_token", data.token);

    // Nettoyer l'URL seulement apres succes
    window.history.replaceState({}, "", window.location.pathname);
    renderDashboard();

  } catch (e) {
    console.error("[auth] exchangeTempCode erreur:", e);
    showLoginScreen();
    showToast("Erreur de connexion: " + e.message, "error");
  }
}

// ─────────────────────────────────────────────────────────────
// AUTH
// ─────────────────────────────────────────────────────────────

function loginWithDiscord() {
  // Redirect vers le backend qui gère le flux OAuth Discord
  window.location.href = API_BASE + "/auth/discord/login";
}

async function handleOAuthCode(code) {
  showToast("Connexion en cours…", "info");
  try {
    const res = await apiPost("/auth/discord", { code });
    state.token = res.token;
    state.user = res.user;
    state.guilds = res.guilds || [];
    localStorage.setItem("vai_token", res.token);
    window.history.replaceState({}, "", window.location.pathname);
    renderDashboard();
  } catch (e) {
    showLoginScreen();
    showToast("Erreur d'authentification: " + e.message, "error");
  }
}

async function loadUserFromToken() {
  try {
    const data = await apiFetch(`/auth/user/me`, { auth: true });
    state.user = {
      id: String(data.user_id),
      username: data.username,
      is_super_admin: data.is_super_admin,
    };
    // Charger les guilds depuis l'API (le token ne les contient pas)
    await loadGuilds();
    renderDashboard();
  } catch (e) {
    // Token invalide ou expiré
    localStorage.removeItem("vai_token");
    state.token = null;
    showLoginScreen();
    if (e.status !== 401) showToast("Session expirée, veuillez vous reconnecter", "warn");
  }
}

async function loadGuilds() {
  try {
    // On récupère les guilds via un appel auth/discord avec le token actuel
    // Alternative : endpoint dédié /auth/guilds
    const data = await apiFetch("/auth/user/guilds", { auth: true });
    state.guilds = data.guilds || [];
  } catch (e) {
    // Endpoint optionnel — pas bloquant
    logger?.warn?.("Guilds non chargées:", e);
  }
}

async function logout() {
  try {
    await apiPost("/auth/logout", { token: state.token });
  } catch (_) {}
  localStorage.removeItem("vai_token");
  state.token = null;
  state.user = null;
  state.guilds = [];
  state.currentGuild = null;
  showLoginScreen();
}

// ─────────────────────────────────────────────────────────────
// RENDER
// ─────────────────────────────────────────────────────────────

function showLoginScreen() {
  document.getElementById("login-screen").style.display = "flex";
  document.getElementById("app").style.display = "none";
}

function renderDashboard() {
  document.getElementById("login-screen").style.display = "none";
  document.getElementById("app").style.display = "flex";

  const isSuper = !!state.user?.is_super_admin;

  // User card
  const u = state.user;
  if (u) {
    document.querySelector(".user-name").textContent = u.username || "—";
    document.querySelector(".user-role").textContent = isSuper ? "Super Admin 👑" : "Admin Serveur";
    const avatarImg = document.querySelector(".user-avatar-img");
    if (avatarImg && u.avatar) avatarImg.src = u.avatar;
  }

  // Server selector
  populateServerSelector();

  // CDC: navigation et pages réservées au Super Admin
  toggleSuperAdminNav(isSuper);

  // CDC: masquer les pages réservées au Super Admin pour les utilisateurs lambda
  // Utilisateur lambda : uniquement Tickets + Settings
  const superOnlyPages = ["page-dashboard", "page-orders", "page-kb"];
  superOnlyPages.forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.style.display = isSuper ? "" : "none";
  });

  // CDC: masquer le bouton Upgrader (redirige vers Orders, réservé Super Admin)
  const upgradeBtn = document.querySelector(".btn[onclick*=\"orders\"]");
  if (upgradeBtn) upgradeBtn.style.display = isSuper ? "" : "none";

  // Charger la page par défaut selon le rôle
  const defaultPage = isSuper ? "dashboard" : "tickets";
  navigateTo(state.currentPage || defaultPage);
}

function populateServerSelector() {
  const display = document.getElementById("server-selector-display");
  if (!display) return;

  const guilds = state.guilds;
  if (!guilds || guilds.length === 0) {
    display.querySelector(".server-name").textContent = "Aucun serveur";
    display.querySelector(".server-plan").textContent = "—";
    return;
  }

  // Sélectionner le premier par défaut
  if (!state.currentGuild) state.currentGuild = guilds[0];
  const g = state.currentGuild;

  display.querySelector(".server-name").textContent = g.name || "Serveur";
  display.querySelector(".server-plan").textContent = g.tier || "Free";

  // Avatar serveur
  const avatar = display.querySelector(".server-avatar");
  if (avatar) {
    if (g.icon) {
      // Avoid innerHTML injection: build the element.
      avatar.textContent = "";
      const iconUrl = String(g.icon || "");
      if (iconUrl.startsWith("https://")) {
        const img = document.createElement("img");
        img.src = iconUrl;
        img.alt = "";
        img.style.width = "28px";
        img.style.height = "28px";
        img.style.borderRadius = "6px";
        img.style.objectFit = "cover";
        avatar.appendChild(img);
      } else {
        avatar.textContent = g.name?.[0]?.toUpperCase() || "?";
      }
    } else {
      avatar.textContent = g.name?.[0]?.toUpperCase() || "?";
    }
  }
}

function toggleSuperAdminNav(isSuperAdmin) {
  // Tous les éléments marqués [data-super-admin] sont réservés au Super Admin :
  // nav items Dashboard, Orders, KB + groupe Super Admin dans la sidebar
  // CDC 2026 : utilisateur lambda = Tickets + Settings uniquement
  document.querySelectorAll("[data-super-admin]").forEach((el) => {
    el.style.display = isSuperAdmin ? "" : "none";
  });
}

// ─────────────────────────────────────────────────────────────
// NAVIGATION
// ─────────────────────────────────────────────────────────────

function initNav() {
  document.querySelectorAll(".nav-item[data-page]").forEach((item) => {
    item.addEventListener("click", () => {
      const page = item.dataset.page;
      navigateTo(page);
    });
  });
}

function navigateTo(page) {
  // CDC: utilisateur lambda = non super-admin
  // Pages réservées au Super Admin : dashboard (global), orders, kb, superadmin
  const isSuper = !!state.user?.is_super_admin;
  if (!isSuper && ["dashboard", "orders", "kb", "superadmin"].includes(page)) page = "tickets";

  state.currentPage = page;

  // Nav items
  document.querySelectorAll(".nav-item").forEach((el) => el.classList.remove("active"));
  const target = document.querySelector(`.nav-item[data-page="${page}"]`);
  if (target) target.classList.add("active");

  // Pages
  document.querySelectorAll(".page-content").forEach((el) => el.classList.remove("active"));
  const pageEl = document.getElementById(`page-${page}`);
  if (pageEl) pageEl.classList.add("active");

  // Breadcrumb
  const names = {
    dashboard: "Dashboard",
    tickets: "Tickets",
    orders: "Orders",
    settings: "Settings",
    kb: "Knowledge Base",
    superadmin: "Super Admin",
  };
  const breadcrumb = document.getElementById("breadcrumb-page");
  if (breadcrumb) breadcrumb.textContent = names[page] || page;

  // Charger les données de la page
  if (state.token && state.currentGuild) {
    if (page === "tickets") loadTickets();
    if (page === "orders" && state.user?.is_super_admin) loadOrders();
    if (page === "settings") loadSettings();
    if (page === "kb") loadKB();
    if (page === "dashboard") loadDashboardStats();
    if (page === "superadmin") loadSuperAdminData();
  }
}

// ─────────────────────────────────────────────────────────────
// API HELPERS
// ─────────────────────────────────────────────────────────────

async function apiFetch(path, { auth = false, method = "GET", body = null } = {}) {
  const headers = { "Content-Type": "application/json" };

  // Toutes les routes /internal/* et /auth/* nécessitent le JWT Bearer.
  // Le secret interne (INTERNAL_API_SECRET) reste côté serveur uniquement
  // et n'est jamais exposé dans le navigateur.
  if ((auth || path.startsWith("/internal/")) && state.token) {
    headers["Authorization"] = `Bearer ${state.token}`;
  }

  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  const res = await fetch(API_BASE + path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const e = new Error(err.detail || `HTTP ${res.status}`);
    e.status = res.status;
    throw e;
  }
  return res.json();
}

async function apiPost(path, data) {
  return apiFetch(path, { method: "POST", body: data, auth: true });
}

async function apiPut(path, data) {
  return apiFetch(path, { method: "PUT", body: data, auth: true });
}

// ─────────────────────────────────────────────────────────────
// DASHBOARD STATS
// ─────────────────────────────────────────────────────────────

async function loadDashboardStats() {
  if (!state.currentGuild) return;
  const guildId = state.currentGuild.id;

  try {
    const stats = await apiFetch(`/internal/guild/${guildId}/stats`, { auth: true });

    setStatValue("stat-tickets-actifs", stats.open_tickets ?? "—");
    setStatValue("stat-tickets-mois", stats.total_tickets ?? "—");

    // Langues
    if (stats.languages && Array.isArray(stats.languages)) {
      renderLanguageStats(stats.languages);
    }

    // Badge tickets actifs sidebar
    const badge = document.querySelector('[data-badge="tickets"]');
    if (badge && stats.open_tickets != null) badge.textContent = stats.open_tickets;
  } catch (e) {
    console.warn("Dashboard stats:", e.message);
  }

  // Les commandes (orders) sont réservées au Super Admin
  if (state.user?.is_super_admin) {
    try {
      const orders = await apiFetch(`/internal/orders/pending`, { auth: true });
      const badge = document.querySelector('[data-badge="orders"]');
      if (badge && orders.total != null) badge.textContent = orders.total;
      setStatValue("stat-orders-attente", orders.total ?? "—");
    } catch (_) {}
  } else {
    const badge = document.querySelector('[data-badge="orders"]');
    if (badge) badge.textContent = "—";
    setStatValue("stat-orders-attente", "—");
  }
}

function setStatValue(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

const LANG_FLAGS = { en: "🇬🇧", fr: "🇫🇷", de: "🇩🇪", es: "🇪🇸", ru: "🇷🇺", ja: "🇯🇵", zh: "🇨🇳", pt: "🇵🇹", it: "🇮🇹" };
const LANG_NAMES = { en: "Anglais", fr: "Français", de: "Allemand", es: "Espagnol", ru: "Russe", ja: "Japonais", zh: "Chinois", pt: "Portugais", it: "Italien" };

function renderLanguageStats(languages) {
  const container = document.getElementById("lang-stats");
  if (!container) return;

  const total = languages.reduce((s, l) => s + (l.count || 0), 0);
  if (total === 0) return;

  container.innerHTML = languages
    .sort((a, b) => b.count - a.count)
    .slice(0, 5)
    .map((l) => {
      const code = l.user_language || l.lang || "?";
      const pctRaw = Math.round(((l.count || 0) / total) * 100);
      const pct = Math.max(0, Math.min(100, pctRaw));
      const flag = LANG_FLAGS[code] || "🌐";
      const name = LANG_NAMES[code] || code.toUpperCase();
      return `
      <div class="progress-item">
        <div class="progress-header">
          <div class="progress-label">${escHtml(flag)} ${escHtml(name)}</div>
          <div class="progress-pct">${pct}%</div>
        </div>
        <div class="progress-track">
          <div class="progress-fill" data-width="${pct}%" style="width:0"></div>
        </div>
      </div>`;
    })
    .join("");

  // Réanimer les nouvelles barres
  setTimeout(() => animateProgressBars(container), 50);
}

// ─────────────────────────────────────────────────────────────
// TICKETS
// ─────────────────────────────────────────────────────────────

let allTickets = [];
let ticketFilter = "all";

async function loadTickets() {
  if (!state.currentGuild) return;
  const guildId = state.currentGuild.id;

  const tbody = document.getElementById("tickets-tbody");
  if (tbody) tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--text3);padding:24px">Chargement…</td></tr>`;

  try {
    const data = await apiFetch(`/internal/guild/${guildId}/tickets`, { auth: true });
    allTickets = data.tickets || [];
    renderTickets(allTickets);
  } catch (e) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--red);padding:24px">Erreur: ${escHtml(e.message || String(e))}</td></tr>`;
  }
}

function renderTickets(tickets) {
  const tbody = document.getElementById("tickets-tbody");
  if (!tbody) return;

  if (!tickets.length) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--text3);padding:24px">Aucun ticket trouvé</td></tr>`;
    return;
  }

  tbody.innerHTML = tickets.map((t) => {
    const statusClass = { open: "pill pending", closed: "pill paid", "in_progress": "pill premium" }[t.status] || "pill";
    const statusLabel = { open: "Ouvert", closed: "Fermé", in_progress: "En cours" }[t.status] || t.status;
    const date = t.opened_at ? new Date(t.opened_at).toLocaleDateString("fr-FR") : "—";
    const flag = LANG_FLAGS[t.user_language] || "🌐";
    const tid = parseInt(String(t.id), 10);
    return `
    <tr>
      <td><span class="mono-id">#${Number.isFinite(tid) ? tid : escHtml(t.id)}</span></td>
      <td>${escHtml(t.user_username || String(t.user_id))}</td>
      <td><span class="${statusClass}">${escHtml(statusLabel)}</span></td>
      <td>${escHtml(flag)} ${escHtml((t.user_language || "").toUpperCase())}</td>
      <td>${escHtml(t.staff_username || "—")}</td>
      <td class="mono-grey">${date}</td>
      <td>
        <button class="btn btn-ghost btn-sm btn-xs" data-ticket-action="view" data-ticket-id="${Number.isFinite(tid) ? tid : ""}" type="button">📄 Voir</button>
        ${t.status === "open" && Number.isFinite(tid) ? `<button class="btn btn-red btn-sm btn-xs" data-ticket-action="close" data-ticket-id="${tid}" type="button" style="margin-left:4px">Fermer</button>` : ""}
      </td>
    </tr>`;
  }).join("");
}

function initTicketSearch() {
  const input = document.getElementById("ticket-search");
  if (!input) return;
  input.addEventListener("input", () => {
    const q = input.value.toLowerCase();
    const filtered = allTickets.filter(
      (t) =>
        String(t.id).includes(q) ||
        (t.user_username || "").toLowerCase().includes(q) ||
        (t.status || "").includes(q)
    );
    renderTickets(filtered);
  });

  // Filtres statut
  document.querySelectorAll("[data-ticket-filter]").forEach((btn) => {
    btn.addEventListener("click", () => {
      ticketFilter = btn.dataset.ticketFilter;
      document.querySelectorAll("[data-ticket-filter]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      const filtered = ticketFilter === "all" ? allTickets : allTickets.filter((t) => t.status === ticketFilter);
      renderTickets(filtered);
    });
  });
}

async function viewTicketTranscript(ticketId) {
  const modal = document.getElementById("transcript-modal");
  const content = document.getElementById("transcript-content");
  if (!modal || !content) return;

  content.textContent = "Chargement…";
  modal.style.display = "flex";

  try {
    const data = await apiFetch(`/internal/ticket/${ticketId}/transcript`, { auth: true });
    content.textContent = data.transcript || "Aucune transcription disponible.";
    document.getElementById("transcript-title").textContent = `Ticket #${ticketId}`;
  } catch (e) {
    content.textContent = "Erreur: " + e.message;
  }
}

function closeTranscriptModal() {
  const modal = document.getElementById("transcript-modal");
  if (modal) modal.style.display = "none";
}

async function closeTicket(ticketId) {
  if (!confirm(`Fermer le ticket #${ticketId} ?`)) return;
  try {
    await apiFetch(`/internal/ticket/${ticketId}/close`, { method: "POST", auth: true });
    showToast(`Ticket #${ticketId} fermé`, "success");
    loadTickets();
  } catch (e) {
    showToast("Erreur: " + e.message, "error");
  }
}

// ─────────────────────────────────────────────────────────────
// ORDERS
// ─────────────────────────────────────────────────────────────

async function loadOrders() {
  try {
    const data = await apiFetch(`/internal/orders/pending`, { auth: true });
    renderOrders(data.orders || []);
  } catch (e) {
    console.warn("Orders:", e.message);
  }
}

function renderOrders(orders, containerId = "orders-list") {
  const container = document.getElementById(containerId);
  if (!container) return;

  if (!orders.length) {
    container.innerHTML = `<div style="text-align:center;color:var(--text3);padding:40px;font-size:13px">✅ Aucune commande en attente</div>`;
    return;
  }

  container.innerHTML = orders.map((o) => {
    const orderKey = o.order_id || o.order_ref || o.id;
    return `
    <div class="order-card" data-order-key="${escAttr(orderKey)}">
      <div class="order-method-icon ${o.method === 'paypal' ? 'paypal' : o.method === 'giftcard' ? 'giftcard' : 'oxapay'}">
        ${o.method === 'paypal' ? '💳' : o.method === 'giftcard' ? '🎁' : '🔐'}
      </div>
      <div class="order-info">
        <div class="order-id">${escHtml(orderKey)}</div>
        <div class="order-user">${escHtml(o.username || "—")} <span class="mono-grey">#${o.user_id}</span></div>
        <div class="order-meta">${escHtml(o.method)} · ${escHtml(o.plan)} · ${timeAgo(o.created_at)}</div>
      </div>
      <div style="margin-right:8px;text-align:right">
        <div class="order-amount">${parseFloat(o.amount || 0).toFixed(2)}€</div>
        <span class="pill pending" style="font-size:9px">EN ATTENTE</span>
      </div>
      <div class="order-actions">
        <button class="btn btn-primary btn-sm" data-order-action="set-status" data-order-id="${escAttr(orderKey)}" data-status="paid" type="button" title="Valider">✅</button>
        <button class="btn btn-yellow btn-sm" data-order-action="set-status" data-order-id="${escAttr(orderKey)}" data-status="partial" type="button" title="Montant incomplet">⚠️</button>
        <button class="btn btn-red btn-sm" data-order-action="set-status" data-order-id="${escAttr(orderKey)}" data-status="rejected" type="button" title="Rejeter">❌</button>
      </div>
    </div>`;
  }).join("");
}

async function validateOrder(btn, orderId, status) {
  const labels = { paid: "valider", partial: "marquer comme incomplet", rejected: "rejeter" };
  if (!confirm(`Voulez-vous ${labels[status] || status} la commande ${orderId} ?`)) return;

  btn.disabled = true;
  const siblings = btn.parentElement.querySelectorAll("button");
  siblings.forEach((b) => (b.disabled = true));

  try {
    await apiFetch(`/internal/orders/${encodeURIComponent(orderId)}/status`, {
      method: "PUT",
      auth: true,
      body: { status },
    });

    const card = btn.closest(".order-card");
    if (card) {
      const pillClass = { paid: "paid", partial: "yellow", rejected: "rejected" }[status] || "";
      const label = { paid: "Payé ✅", partial: "Incomplet ⚠️", rejected: "Rejeté ❌" }[status] || status;
      card.querySelector(".order-actions").innerHTML = `<span class="pill ${pillClass}">${label}</span>`;
    }

    showToast(`Commande ${orderId} : ${labels[status]}`, "success");

    // Mettre à jour le badge
    const badge = document.querySelector('[data-badge="orders"]');
    if (badge) {
      const count = parseInt(badge.textContent) || 0;
      badge.textContent = Math.max(0, count - 1);
    }
  } catch (e) {
    showToast("Erreur: " + e.message, "error");
    siblings.forEach((b) => (b.disabled = false));
  }
}

// ─────────────────────────────────────────────────────────────
// SETTINGS
// ─────────────────────────────────────────────────────────────

async function loadSettings() {
  if (!state.currentGuild) return;
  const guildId = state.currentGuild.id;

  try {
    const cfg = await apiFetch(`/internal/guild/${guildId}/config`, { auth: true });

    const fields = {
      "settings-support-channel": cfg.support_channel_id ? `#${cfg.support_channel_id}` : "",
      "settings-ticket-category": cfg.ticket_category_id ? cfg.ticket_category_id : "",
      "settings-staff-role": cfg.staff_role_id ? `@${cfg.staff_role_id}` : "",
      "settings-log-channel": cfg.log_channel_id ? `#${cfg.log_channel_id}` : "",
    };

    for (const [id, val] of Object.entries(fields)) {
      const el = document.getElementById(id);
      if (el) el.value = val;
    }

    const langSelect = document.getElementById("settings-default-lang");
    if (langSelect && cfg.default_language) langSelect.value = cfg.default_language;
  } catch (e) {
    showToast("Erreur chargement config: " + e.message, "error");
  }
}

function initSettingsSave() {
  const saveBtn = document.getElementById("settings-save-btn");
  if (!saveBtn) return;

  saveBtn.addEventListener("click", async () => {
    if (!state.currentGuild) return showToast("Aucun serveur sélectionné", "warn");

    saveBtn.textContent = "Sauvegarde…";
    saveBtn.disabled = true;

    const cfg = {
      default_language: document.getElementById("settings-default-lang")?.value || "en",
    };

    // Extraire les IDs depuis les champs texte (retirer # et @)
    const supportVal = document.getElementById("settings-support-channel")?.value?.replace(/[#@]/g, "");
    if (supportVal) cfg.support_channel_id = parseInt(supportVal) || null;

    const staffVal = document.getElementById("settings-staff-role")?.value?.replace(/[#@]/g, "");
    if (staffVal) cfg.staff_role_id = parseInt(staffVal) || null;

    const logVal = document.getElementById("settings-log-channel")?.value?.replace(/[#@]/g, "");
    if (logVal) cfg.log_channel_id = parseInt(logVal) || null;

    try {
      await apiPut(`/internal/guild/${state.currentGuild.id}/config`, cfg);
      showToast("Configuration sauvegardée ✅", "success");
    } catch (e) {
      showToast("Erreur: " + e.message, "error");
    } finally {
      saveBtn.textContent = "Sauvegarder";
      saveBtn.disabled = false;
    }
  });
}

// ─────────────────────────────────────────────────────────────
// KNOWLEDGE BASE
// ─────────────────────────────────────────────────────────────

let kbEntries = [];

async function loadKB() {
  if (!state.currentGuild) return;
  const guildId = state.currentGuild.id;

  try {
    const data = await apiFetch(`/internal/guild/${guildId}/kb`, { auth: true });
    kbEntries = data.entries || [];
    renderKBEntries();
    updateKBCounter();
  } catch (e) {
    console.warn("KB:", e.message);
  }
}

function renderKBEntries() {
  const container = document.getElementById("kb-entries");
  if (!container) return;

  if (!kbEntries.length) {
    container.innerHTML = `<div style="text-align:center;color:var(--text3);padding:24px;font-size:13px">Aucune entrée. Cliquez sur "+ Ajouter" pour commencer.</div>`;
    return;
  }

  container.innerHTML = kbEntries.map((e) => `
    <div class="kb-item" data-kb-id="${e.id}">
      <div class="kb-question">${escHtml(e.question)}</div>
      <div class="kb-answer">${escHtml(e.answer)}</div>
      <div class="kb-footer">
        <button class="btn btn-ghost btn-sm" data-kb-action="edit" data-kb-id="${escAttr(e.id)}" type="button">Modifier</button>
        <button class="btn btn-red btn-sm" data-kb-action="delete" data-kb-id="${escAttr(e.id)}" type="button">Supprimer</button>
      </div>
    </div>`).join("");
}

function updateKBCounter() {
  const limit = state.currentGuild?.tier === "pro" ? 100 : 50;
  const count = kbEntries.length;
  const el = document.querySelector(".card-meta[data-kb-counter]");
  if (el) el.textContent = `${count} / ${limit} ENTRÉES`;
  const fill = document.querySelector(".progress-fill[data-kb-fill]");
  if (fill) {
    const pct = Math.min(100, Math.round((count / limit) * 100));
    fill.style.width = pct + "%";
  }
}

function initKB() {
  const addBtn = document.getElementById("kb-add-btn");
  const form = document.getElementById("kb-form");
  if (addBtn && form) {
    addBtn.addEventListener("click", () => {
      form.style.display = form.style.display === "none" ? "block" : "none";
      document.getElementById("kb-form-id").value = "";
      document.getElementById("kb-form-q").value = "";
      document.getElementById("kb-form-a").value = "";
      document.getElementById("kb-form-title").textContent = "Nouvelle entrée";
    });
  }

  const saveBtn = document.getElementById("kb-save-btn");
  if (saveBtn) saveBtn.addEventListener("click", saveKBEntry);
}

async function saveKBEntry() {
  if (!state.currentGuild) return showToast("Aucun serveur sélectionné", "warn");

  const id = document.getElementById("kb-form-id")?.value;
  const question = document.getElementById("kb-form-q")?.value?.trim();
  const answer = document.getElementById("kb-form-a")?.value?.trim();

  if (!question || !answer) return showToast("Question et réponse requis", "warn");

  try {
    if (id) {
      await apiPut(`/internal/guild/${state.currentGuild.id}/kb/${id}`, { question, answer });
      showToast("Entrée mise à jour ✅", "success");
    } else {
      await apiPost(`/internal/guild/${state.currentGuild.id}/kb`, { question, answer });
      showToast("Entrée ajoutée ✅", "success");
    }
    document.getElementById("kb-form").style.display = "none";
    await loadKB();
  } catch (e) {
    showToast("Erreur: " + e.message, "error");
  }
}

function editKBEntry(id) {
  const entry = kbEntries.find((e) => e.id === id);
  if (!entry) return;

  document.getElementById("kb-form-id").value = id;
  document.getElementById("kb-form-q").value = entry.question;
  document.getElementById("kb-form-a").value = entry.answer;
  document.getElementById("kb-form-title").textContent = "Modifier l'entrée";
  document.getElementById("kb-form").style.display = "block";
  document.getElementById("kb-form").scrollIntoView({ behavior: "smooth" });
}

async function deleteKBEntry(id) {
  if (!confirm("Supprimer cette entrée ?")) return;
  try {
    await apiFetch(`/internal/guild/${state.currentGuild.id}/kb/${id}`, { method: "DELETE", auth: true });
    showToast("Entrée supprimée", "success");
    await loadKB();
  } catch (e) {
    showToast("Erreur: " + e.message, "error");
  }
}

// ─────────────────────────────────────────────────────────────
// SUPER ADMIN
// ─────────────────────────────────────────────────────────────

async function loadSuperAdminData() {
  // Indicateur de chargement
  const ordersContainer = document.getElementById("admin-orders-list");
  if (ordersContainer) ordersContainer.innerHTML = `<div style="color:var(--text3);font-size:13px;text-align:center;padding:24px">Chargement…</div>`;

  const [globalStats, pendingOrders, botStatus] = await Promise.allSettled([
    apiFetch("/internal/admin/stats", { auth: true }),
    apiFetch("/internal/orders/pending", { auth: true }),
    apiFetch("/internal/bot/status", { auth: true }),
  ]);

  // Stats globales
  if (globalStats.status === "fulfilled") {
    const s = globalStats.value;
    setStatValue("admin-stat-servers", s.total_guilds ?? "—");
    setStatValue("admin-stat-users", s.total_users ?? "—");
    setStatValue("admin-stat-tickets", s.tickets_today ?? "—");
    setStatValue("admin-stat-revenue", s.revenue_month ? `${s.revenue_month}€` : "—");
    // Badge orders dans la sidebar
    const badge = document.querySelector('[data-badge="orders"]');
    if (badge && s.orders_pending != null) badge.textContent = s.orders_pending;
  } else {
    console.warn("SuperAdmin stats error:", globalStats.reason?.message);
  }

  // Commandes en attente
  if (pendingOrders.status === "fulfilled") {
    renderOrders(pendingOrders.value.orders || [], "admin-orders-list");
  } else {
    if (ordersContainer) ordersContainer.innerHTML = `<div style="color:var(--red);font-size:13px;text-align:center;padding:24px">❌ Erreur chargement commandes</div>`;
  }

  // Statut bot (uptime + version)
  if (botStatus.status === "fulfilled") {
    const b = botStatus.value;
    const uptimeEl = document.getElementById("admin-bot-uptime");
    const versionEl = document.getElementById("admin-bot-version");
    if (uptimeEl && b.uptime_sec != null) {
      const h = Math.floor(b.uptime_sec / 3600);
      const m = Math.floor((b.uptime_sec % 3600) / 60);
      uptimeEl.textContent = `${h}h ${m}m`;
    }
    if (versionEl && b.version) versionEl.textContent = b.version;
  }
}

async function adminActivateSub() {
  const guildIdRaw = document.getElementById("admin-guild-id")?.value?.trim();
  const plan = document.getElementById("admin-plan")?.value || "premium";
  const guildId = parseInt(guildIdRaw, 10);
  if (!Number.isFinite(guildId)) return showToast("Guild ID invalide", "warn");

  try {
    await apiPost("/internal/admin/activate-sub", { guild_id: guildId, plan, duration_days: 30 });
    showToast(`Abonnement ${plan} activé pour ${guildId}`, "success");
  } catch (e) {
    showToast("Erreur: " + e.message, "error");
  }
}

async function adminRevokeSub() {
  const guildIdRaw = document.getElementById("admin-guild-id")?.value?.trim();
  const guildId = parseInt(guildIdRaw, 10);
  if (!Number.isFinite(guildId)) return showToast("Guild ID invalide", "warn");

  try {
    await apiPost("/internal/revoke-sub", { guild_id: guildId });
    showToast(`Abonnement révoqué pour ${guildId}`, "success");
  } catch (e) {
    showToast("Erreur: " + e.message, "error");
  }
}

// ─────────────────────────────────────────────────────────────
// SERVER SELECTOR DROPDOWN
// ─────────────────────────────────────────────────────────────

function initServerSelector() {
  const display = document.getElementById("server-selector-display");
  const dropdown = document.getElementById("server-dropdown");
  if (!display) return;

  display.addEventListener("click", () => {
    if (!dropdown) return;
    dropdown.style.display = dropdown.style.display === "none" ? "block" : "none";
  });

  document.addEventListener("click", (e) => {
    if (dropdown && !display.contains(e.target) && !dropdown.contains(e.target)) {
      dropdown.style.display = "none";
    }
  });
}

function selectGuild(guildId) {
  const guild = state.guilds.find((g) => g.id === guildId);
  if (!guild) return;

  state.currentGuild = guild;
  populateServerSelector();

  const dropdown = document.getElementById("server-dropdown");
  if (dropdown) dropdown.style.display = "none";

  // Recharger la page courante avec le nouveau serveur
  navigateTo(state.currentPage);
}

// ─────────────────────────────────────────────────────────────
// UI: PROGRESS BARS
// ─────────────────────────────────────────────────────────────

function initProgressBars() {
  animateProgressBars(document);
}

function animateProgressBars(root) {
  root.querySelectorAll(".progress-fill[data-width]").forEach((el) => {
    setTimeout(() => {
      el.style.width = el.dataset.width;
    }, 100);
  });
  root.querySelectorAll(".key-fill[data-width]").forEach((el) => {
    setTimeout(() => {
      el.style.width = el.dataset.width;
    }, 150);
  });
}

// ─────────────────────────────────────────────────────────────
// UI: BAR CHART (tickets 7 jours)
// ─────────────────────────────────────────────────────────────

function initBarChart() {
  const chart = document.getElementById("bar-chart");
  if (!chart) return;

  // Données placeholder — sera remplacé par loadDashboardStats()
  const data = [
    { day: "Lun", val: 18 },
    { day: "Mar", val: 24 },
    { day: "Mer", val: 15 },
    { day: "Jeu", val: 31 },
    { day: "Ven", val: 27 },
    { day: "Sam", val: 12 },
    { day: "Dim", val: 8 },
  ];
  renderBarChart(chart, data);
}

function renderBarChart(container, data) {
  const max = Math.max(...data.map((d) => d.val), 1);
  container.innerHTML = data
    .map(
      (d) => `
    <div class="bar-group">
      <div class="bar-value">${d.val}</div>
      <div class="bar" style="height:0" data-height="${Math.round((d.val / max) * 100)}%"></div>
      <div class="bar-label">${d.day}</div>
    </div>`
    )
    .join("");

  setTimeout(() => {
    container.querySelectorAll(".bar[data-height]").forEach((bar) => {
      bar.style.height = bar.dataset.height;
    });
  }, 100);
}

// ─────────────────────────────────────────────────────────────
// UI: TOGGLE SWITCHES
// ─────────────────────────────────────────────────────────────

function initToggleSwitches() {
  document.querySelectorAll(".toggle-switch:not([style*='pointer-events:none'])").forEach((toggle) => {
    toggle.addEventListener("click", () => {
      toggle.classList.toggle("on");
    });
  });
}

// ─────────────────────────────────────────────────────────────
// UI: TOAST
// ─────────────────────────────────────────────────────────────

function showToast(message, type = "info") {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.style.cssText =
      "position:fixed;bottom:24px;right:24px;z-index:99999;display:flex;flex-direction:column;gap:8px;";
    document.body.appendChild(container);
  }

  const colors = {
    success: "var(--accent)",
    error: "var(--red)",
    warn: "var(--yellow)",
    info: "var(--blue)",
  };

  const toast = document.createElement("div");
  toast.style.cssText = `
    padding:10px 16px;border-radius:8px;font-size:13px;font-weight:500;
    background:var(--bg2);border:1px solid ${colors[type] || colors.info};
    color:var(--text);box-shadow:0 4px 20px rgba(0,0,0,0.4);
    display:flex;align-items:center;gap:8px;
    animation:slideIn .2s ease;max-width:320px;
  `;
  toast.innerHTML = `<span style="color:${colors[type]};font-size:16px">
    ${{ success: "✅", error: "❌", warn: "⚠️", info: "ℹ️" }[type]}
  </span> ${escHtml(message)}`;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity .3s";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// ─────────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────────

function escHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function escAttr(str) {
  // Same escaping as HTML text, plus single-quote (handled in escHtml).
  return escHtml(str);
}

function timeAgo(dateStr) {
  if (!dateStr) return "—";
  const diff = Date.now() - new Date(dateStr).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "à l'instant";
  if (m < 60) return `il y a ${m} min`;
  const h = Math.floor(m / 60);
  if (h < 24) return `il y a ${h}h`;
  return `il y a ${Math.floor(h / 24)}j`;
}

function updateTopbarDate() {
  const el = document.querySelector(".page-sub");
  if (!el) return;
  const now = new Date();
  const opts = { weekday: "long", year: "numeric", month: "long", day: "numeric" };
  el.textContent = now.toLocaleDateString("fr-FR", opts);
}

// Injecter l'animation CSS si absente
if (!document.getElementById("dashboard-anim-style")) {
  const style = document.createElement("style");
  style.id = "dashboard-anim-style";
  style.textContent = `
    @keyframes slideIn { from { transform: translateX(30px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
    .bar { transition: height 0.6s cubic-bezier(.34,1.56,.64,1); border-radius: 4px 4px 0 0; background: var(--accent); }
    .progress-fill { transition: width 0.8s cubic-bezier(.34,1.56,.64,1); }
    .key-fill { transition: width 0.7s ease; }
    .nav-item[data-ticket-filter].active { background: var(--accent-dim); color: var(--accent); }
  `;
  document.head.appendChild(style);
}
