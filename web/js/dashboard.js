const API_URL = "https://api.veridiancloud.xyz:201";
const CLIENT_ID = "1475845849333498038";
const REDIRECT_URI = "https://veridiancloud.xyz/dashboard.html";

async function handleOAuth() {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");

    if (code) {
        window.history.replaceState({}, document.title, "/dashboard.html");
        try {
            const res = await fetch(`${API_URL}/auth/discord`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ code })
            });
            const data = await res.json();

            if (data.user) {
                sessionStorage.setItem("vai_user", JSON.stringify(data.user));
                sessionStorage.setItem("vai_guilds", JSON.stringify(data.guilds));
                showDashboard(data.user, data.guilds);
            }
        } catch (err) {
            console.error("OAuth error:", err);
            showLoginScreen();
        }
        return;
    }

    const savedUser = sessionStorage.getItem("vai_user");
    if (savedUser) {
        const user = JSON.parse(savedUser);
        const guilds = JSON.parse(sessionStorage.getItem("vai_guilds") || "[]");
        showDashboard(user, guilds);
        return;
    }

    showLoginScreen();
}

function loginWithDiscord() {
    const url = `https://discord.com/api/oauth2/authorize`
        + `?client_id=${CLIENT_ID}`
        + `&redirect_uri=${encodeURIComponent(REDIRECT_URI)}`
        + `&response_type=code`
        + `&scope=identify%20guilds`;
    window.location.href = url;
}

function showLoginScreen() {
    const login = document.getElementById("login-screen");
    const app = document.getElementById("app");
    if (login) login.style.display = "flex";
    if (app) app.style.display = "none";
}

function showDashboard(user, guilds) {
    const login = document.getElementById("login-screen");
    const app = document.getElementById("app");
    if (login) login.style.display = "none";
    if (app) app.style.display = "flex";

    document.querySelectorAll(".user-avatar-img").forEach(el => {
        el.src = user.avatar;
        el.alt = user.username;
    });

    document.querySelectorAll(".user-name").forEach(el => {
        el.textContent = user.username;
    });

    document.querySelectorAll(".user-role").forEach(el => {
        el.textContent = user.is_super_admin ? "Super Admin" : "Server Admin";
    });

    const select = document.getElementById("server-select");
    if (select && guilds.length > 0) {
        select.innerHTML = guilds.map(g => `
            <option value="${g.id}">${g.name}</option>
        `).join("");
    }
}

function logout() {
    sessionStorage.removeItem("vai_user");
    sessionStorage.removeItem("vai_guilds");
    showLoginScreen();
}

document.addEventListener("DOMContentLoaded", handleOAuth);
