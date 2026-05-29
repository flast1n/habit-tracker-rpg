"use strict";
/* ════════════════════════════════════════════════════════
   HabitRPG — script.js v3
   Повністю підключено до FastAPI бекенду
   Всі дані зберігаються в SQLite через REST API
════════════════════════════════════════════════════════ */

// ──────────────────────────────────────
// CONFIG
// ──────────────────────────────────────

const API = "http://127.0.0.1:8000";

const AVATARS_DATA = [
    { emoji:"🧙‍♂️", name:"Маг",          cost:0,    rarity:"common"    },
    { emoji:"🧙‍♀️", name:"Чаклунка",     cost:100,  rarity:"common"    },
    { emoji:"🦸‍♂️", name:"Супергерой",   cost:150,  rarity:"uncommon"  },
    { emoji:"🦸‍♀️", name:"Супергероїня", cost:150,  rarity:"uncommon"  },
    { emoji:"🧝‍♂️", name:"Ельф",         cost:250,  rarity:"uncommon"  },
    { emoji:"🧝‍♀️", name:"Ельфійка",     cost:250,  rarity:"uncommon"  },
    { emoji:"🧛‍♂️", name:"Вампір",       cost:400,  rarity:"rare"      },
    { emoji:"🤴",   name:"Принц",        cost:500,  rarity:"rare"      },
    { emoji:"👸",   name:"Принцеса",     cost:500,  rarity:"rare"      },
    { emoji:"🥷",   name:"Ніндзя",       cost:750,  rarity:"epic"      },
    { emoji:"🤖",   name:"Робот",        cost:900,  rarity:"epic"      },
    { emoji:"👑",   name:"Монарх",       cost:1200, rarity:"legendary" },
    { emoji:"🐉",   name:"Дракон",       cost:2000, rarity:"legendary" },
];

const ACHIEVEMENTS_DATA = [
    { id:"first_step",      icon:"🌟", name:"Перший Крок",        desc:"Виконай першу звичку",              check: s => s.total_completed >= 1 },
    { id:"week_streak",     icon:"🔥", name:"Тиждень Вогню",      desc:"7 днів стріку",                    check: s => s.streak >= 7 },
    { id:"month_streak",    icon:"🌙", name:"Місяць Сили",        desc:"30 днів стріку",                   check: s => s.streak >= 30 },
    { id:"habits_50",       icon:"💪", name:"Залізна Воля",       desc:"Виконай 50 звичок загалом",        check: s => s.total_completed >= 50 },
    { id:"habits_100",      icon:"🏅", name:"Легіонер",           desc:"Виконай 100 звичок загалом",       check: s => s.total_completed >= 100 },
    { id:"rich",            icon:"💎", name:"Заможний",           desc:"500+ монет",                       check: s => s.coins >= 500 },
    { id:"mega_rich",       icon:"🏦", name:"Казначей",           desc:"2000+ монет",                      check: s => s.coins >= 2000 },
    { id:"level5",          icon:"⚔️", name:"Відважний Герой",    desc:"Досягни 5-го рівня",               check: s => s.level >= 5 },
    { id:"level10",         icon:"🏆", name:"Легенда Краю",       desc:"Досягни 10-го рівня",              check: s => s.level >= 10 },
];

const DIFF = {
    easy:   { xp:10,  gold:5,  label:"Легка",   statBoost:1, hpLoss:5  },
    medium: { xp:20,  gold:12, label:"Середня", statBoost:2, hpLoss:10 },
    hard:   { xp:40,  gold:25, label:"Важка",   statBoost:3, hpLoss:15 },
};

const STAT_ICONS = { str:"⚔️", wis:"📚", end:"🛡️", cha:"✨" };
const XP_FOR_LEVEL = lvl => 100 + (lvl - 1) * 50;

// ──────────────────────────────────────
// SESSION (тільки токен у localStorage)
// ──────────────────────────────────────

const SESSION_KEY = "habitrpg_token_v3";

function getToken()          { return localStorage.getItem(SESSION_KEY); }
function setToken(t)         { localStorage.setItem(SESSION_KEY, t); }
function clearToken()        { localStorage.removeItem(SESSION_KEY); }

// ──────────────────────────────────────
// API HELPER
// ──────────────────────────────────────

async function api(method, path, body = null) {
    const headers = { "Content-Type": "application/json" };
    const token = getToken();
    if (token) headers["Authorization"] = "Bearer " + token;

    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);

    const res = await fetch(API + path, opts);
    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
        const msg = data.detail || "Помилка сервера";
        throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
    }
    return data;
}

// ──────────────────────────────────────
// STATE
// ──────────────────────────────────────

let currentUser  = null;   // дані з /auth/me
let habits       = [];     // масив звичок
let rewards      = [];     // масив нагород
let activityLog  = [];     // локальний лог дій
let activeFilter = "all";

// ──────────────────────────────────────
// VIEWS
// ──────────────────────────────────────

function showView(viewId) {
    ["auth-screen", "admin-panel", "main-app"].forEach(id =>
        document.getElementById(id).classList.toggle("hidden", id !== viewId)
    );
}

// ──────────────────────────────────────
// AUTH
// ──────────────────────────────────────

async function doLogin(username, password) {
    try {
        showLoading(true);
        const data = await api("POST", "/auth/login", { username, password });
        setToken(data.access_token);
        currentUser = data;
        await enterApp();
    } catch (e) {
        showAuthError("login-error", e.message);
    } finally {
        showLoading(false);
    }
}

async function doRegister(username, password, confirm) {
    if (username.length < 3)  return showAuthError("register-error", "Логін мінімум 3 символи");
    if (password.length < 4)  return showAuthError("register-error", "Пароль мінімум 4 символи");
    if (password !== confirm)  return showAuthError("register-error", "Паролі не збігаються");
    if (/\s/.test(username))   return showAuthError("register-error", "Логін не може містити пробіли");

    try {
        showLoading(true);
        const data = await api("POST", "/auth/register", { username, password });
        setToken(data.access_token);
        currentUser = data;
        toast(`🌟 Ласкаво просимо, <strong>${escHtml(username)}</strong>! Твій герой створений!`, "success", 4000);
        await enterApp();
    } catch (e) {
        showAuthError("register-error", e.message);
    } finally {
        showLoading(false);
    }
}

function doLogout() {
    stopDeathPolling();
    clearToken();
    currentUser = null;
    habits = [];
    rewards = [];
    activityLog = [];
    showView("auth-screen");
    document.getElementById("login-username").value = "";
    document.getElementById("login-password").value = "";
    clearAuthErrors();
}

async function enterApp() {
    if (!currentUser) return;
    if (currentUser.role === "admin") {
        await loadAdminData();
        showView("admin-panel");
    } else {
        await loadGameData();
        startGame();
        showView("main-app");
    }
}

async function restoreSession() {
    const token = getToken();
    if (!token) return false;
    try {
        currentUser = await api("GET", "/auth/me");
        return true;
    } catch {
        clearToken();
        return false;
    }
}

function showAuthError(elId, msg) {
    const el = document.getElementById(elId);
    el.textContent = msg;
    el.classList.remove("hidden");
}

function clearAuthErrors() {
    ["login-error", "register-error"].forEach(id => {
        document.getElementById(id).classList.add("hidden");
        document.getElementById(id).textContent = "";
    });
}

function showLoading(on) {
    const btn = document.getElementById("login-btn");
    const rbtn = document.getElementById("register-btn");
    if (btn)  btn.disabled  = on;
    if (rbtn) rbtn.disabled = on;
}

// ──────────────────────────────────────
// LOAD GAME DATA
// ──────────────────────────────────────

async function loadGameData() {
    // Оновлюємо поточного юзера
    currentUser = await api("GET", "/auth/me");

    // Звички
    const raw = await api("GET", `/habits/user/${currentUser.user_id}`);
    habits = raw.map(h => ({
        id:             h.id,
        title:          h.title,
        difficulty:     h.difficulty,
        stat:           h.stat,
        streak:         h.streak,
        best_streak:    h.best_streak,
        completedToday: h.is_done === 1,
        failedToday:    h.failed_today === 1,
        totalCompleted: h.total_completed,
    }));
        try {
                const rawLog = await api("GET", "/users/me/activity-log?limit=50");
                activityLog = rawLog.map(log => ({
                    msg: log.message,
                    t: new Date(log.created_at.replace(" ", "T") + "Z")
                            .toLocaleTimeString("uk-UA", { hour:"2-digit", minute:"2-digit" })
                }));
            } catch (e) {
                console.warn("Не вдалося завантажити журнал подій:", e);
                activityLog = [];
            }
    // Нагороди
    const rawR = await api("GET", "/users/me/rewards");
    rewards = rawR.map(r => ({ id: r.id, title: r.title, cost: r.cost }));
}

// ──────────────────────────────────────
// TOAST
// ──────────────────────────────────────

function toast(html, type = "info", ms = 3200) {
    const c = document.getElementById("toast-container");
    const el = document.createElement("div");
    el.className = `toast toast-${type}`;
    el.innerHTML = html;
    c.appendChild(el);
    requestAnimationFrame(() => requestAnimationFrame(() => el.classList.add("toast-visible")));
    setTimeout(() => {
        el.classList.remove("toast-visible");
        setTimeout(() => el.remove(), 400);
    }, ms);
}

// ──────────────────────────────────────
// LOG
// ──────────────────────────────────────

function addLog(msg) {
    const t = new Date().toLocaleTimeString("uk-UA", { hour:"2-digit", minute:"2-digit" });
    activityLog.unshift({ msg, t });
    if (activityLog.length > 40) activityLog.pop();
    renderLog();

    // Зберігаємо в БД асинхронно
    if (currentUser) {
        api("POST", "/users/me/activity-log", { message: msg }).catch(e => 
            console.warn("Помилка при збереженні журналу:", e)
        );
    }
}

function renderLog() {
    const el = document.getElementById("activity-log");
    if (!el) return;
    if (!activityLog.length) {
        el.innerHTML = '<div class="log-empty">Поки що нічого не відбулось...</div>';
        return;
    }
    el.innerHTML = activityLog.map(e =>
        `<div class="log-entry"><span class="log-time">${e.t}</span><span class="log-msg">${e.msg}</span></div>`
    ).join("");
}

// ──────────────────────────────────────
// HERO RENDER
// ──────────────────────────────────────

function renderHero() {
    if (!currentUser) return;
    const u = currentUser;
    const xpNeed = XP_FOR_LEVEL(u.level);
    const xpPct  = Math.min((u.xp / xpNeed) * 100, 100).toFixed(1);
    const hpPct  = Math.min((u.hp / u.max_hp) * 100, 100).toFixed(1);

    setEl("hero-avatar",     u.avatar);
    setEl("hero-level",      u.level);
    setEl("hero-name",       u.username);
    setEl("xp-text",         `${u.xp}/${xpNeed}`);
    setEl("hp-text",         `${u.hp}/${u.max_hp}`);
    setEl("gold-count",      u.coins);
    setEl("avatar-gold",     u.coins);
    setEl("streak-count",    u.streak);
    setEl("header-username", u.username);

    const roleBadge = document.getElementById("header-role-badge");
    if (roleBadge) roleBadge.textContent = u.role === "admin" ? "👑 Адмін" : "🧙 Гравець";

    const adminBtn = document.getElementById("game-admin-btn");
    if (adminBtn) adminBtn.classList.toggle("hidden", u.role !== "admin");

    setPct("xp-bar-inner", xpPct);
    setPct("hp-bar-inner",  hpPct);

    const hpBar = document.getElementById("hp-bar-inner");
    if (hpBar) {
        hpBar.className = "bar-inner hp-color" +
            (u.hp / u.max_hp < 0.25 ? " hp-critical" : u.hp / u.max_hp < 0.5 ? " hp-warning" : "");
    }

    document.getElementById("streak-badge")?.classList.toggle("streak-epic", u.streak >= 7);

    const stats = typeof u.stats === "string" ? JSON.parse(u.stats) : u.stats;
    ["str","wis","end","cha"].forEach(st => {
        setEl(`${st}-val`, stats[st] || 1);
        setPct(`${st}-bar`, Math.min(((stats[st] || 1) / 99) * 100, 100));
    });

    const done  = habits.filter(h => h.completedToday).length;
    const total = habits.length;
    setEl("habits-progress-text", `${done}/${total} звичок виконано сьогодні`);

    renderAchievementsMini();
}

function setEl(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }
function setPct(id, pct) { const el = document.getElementById(id); if (el) el.style.width = pct + "%"; }

// ──────────────────────────────────────
// ACHIEVEMENTS
// ──────────────────────────────────────

async function checkAchievements() {
    if (!currentUser) return;
    
    // Отримуємо список вже відкритих досягнень
    const owned = typeof currentUser.achievements === "string"
        ? JSON.parse(currentUser.achievements)
        : (currentUser.achievements || []);

    let isNewUnlocked = false;

    ACHIEVEMENTS_DATA.forEach(a => {
        // Якщо досягнення ЩЕ НЕМАЄ в масиві (!owned.includes) І умова виконана
        if (!owned.includes(a.id) && a.check(currentUser)) {
            owned.push(a.id); // Записуємо, що воно тепер є
            toast(`🏆 Досягнення: <strong>${a.name}</strong>! ${a.icon}`, "achievement", 4500);
            addLog(`🏆 Нове досягнення: ${a.icon} ${a.name}`);
            isNewUnlocked = true;
        }
    });
    
    // Оновлюємо дані локально, щоб відразу відобразити
    currentUser.achievements = owned;
    renderAchievementsMini();
    renderAchievementsTab();

    // Якщо відкрили нове досягнення — тихо відправляємо його на бекенд
    if (isNewUnlocked) {
        try {
            await api("PUT", "/users/me/achievements", { achievements: owned });
        } catch (e) {
            // Порожній блок catch. 
            // Якщо не вдалося зберегти в базу — просто ігноруємо, ніяких повідомлень.
        }
    }
}

function renderAchievementsMini() {
    const el = document.getElementById("achievements-row");
    if (!el) return;
    const owned = typeof currentUser?.achievements === "string"
        ? JSON.parse(currentUser.achievements)
        : (currentUser?.achievements || []);
    const unlocked = owned.slice(-6);
    if (!unlocked.length) { el.innerHTML = '<span class="ach-empty">Ще немає</span>'; return; }
    el.innerHTML = unlocked.map(id => {
        const a = ACHIEVEMENTS_DATA.find(x => x.id === id);
        return a ? `<span class="ach-icon-mini" title="${a.name}: ${a.desc}">${a.icon}</span>` : "";
    }).join("");
}

function renderAchievementsTab() {
    const el = document.getElementById("achievements-list");
    if (!el) return;
    const owned = typeof currentUser?.achievements === "string"
        ? JSON.parse(currentUser.achievements)
        : (currentUser?.achievements || []);
    el.innerHTML = ACHIEVEMENTS_DATA.map(a => {
        const u = owned.includes(a.id);
        return `<div class="ach-card ${u ? "ach-unlocked" : "ach-locked"}">
            <div class="ach-icon-big">${u ? a.icon : "🔒"}</div>
            <div class="ach-info">
                <div class="ach-name">${a.name}</div>
                <div class="ach-desc">${a.desc}</div>
            </div>
        </div>`;
    }).join("");
    const lbl = document.getElementById("ach-count-label");
    if (lbl) lbl.textContent = `${owned.length}/${ACHIEVEMENTS_DATA.length}`;
}

// ──────────────────────────────────────
// HABITS
// ──────────────────────────────────────

function renderHabits(filter) {
    if (filter !== undefined) activeFilter = filter;
    const list = document.getElementById("habits-list");
    if (!list) return;
    const filtered = activeFilter === "all"
        ? habits
        : habits.filter(h => h.difficulty === activeFilter);

    if (!filtered.length) {
        list.innerHTML = '<div class="empty-state">Немає звичок у цій категорії ⚔️<br>Додай першу!</div>';
        return;
    }
    list.innerHTML = filtered.map(h => {
        const cfg  = DIFF[h.difficulty] || DIFF.easy;
        const done   = h.completedToday;
        const failed = h.failedToday;
        return `<div class="card habit-card ${done ? "habit-done" : failed ? "habit-failed" : ""}" data-id="${h.id}">
            <div class="card-info">
                <h4 class="card-title">${escHtml(h.title)}</h4>
                <div class="card-meta">
                    <span class="badge badge-${h.difficulty}">${cfg.label}</span>
                    <span class="habit-streak-mini" title="Стрік цієї звички">🔥 ${h.streak}</span>
                    <span class="habit-stat-mini" title="${h.stat}">${STAT_ICONS[h.stat] || "⭐"}</span>
                </div>
                <div class="habit-rewards">+${cfg.xp} XP · +${cfg.gold} 💰 · ${STAT_ICONS[h.stat]}+${cfg.statBoost}</div>
            </div>
            <div class="card-actions">
                <button class="action-btn btn-success" data-action="complete" data-id="${h.id}" title="Виконано" ${done || h.failedToday ? "disabled" : ""}>✓</button>
                <button class="action-btn btn-danger"  data-action="fail"     data-id="${h.id}" title="Пропущено" ${done || h.failedToday ? "disabled" : ""}>X</button>
                <button class="action-btn btn-delete"  data-action="delete"   data-id="${h.id}" title="Видалити">🗑</button>
            </div>
        </div>`;
    }).join("");
}

async function completeHabit(id) {
    const h = habits.find(x => x.id === id);
    if (!h) return;
    if (h.completedToday) { toast("⚠️ Цю звичку вже виконано сьогодні!", "warning"); return; }

    try {
        const res = await api("POST", `/habits/${id}/complete`);
        h.completedToday = true;
        h.streak++;
        h.totalCompleted++;

        // Оновлюємо currentUser з відповіді
        currentUser = await api("GET", "/auth/me");

        toast(`✅ <strong>${escHtml(h.title)}</strong> — +${res.xp_gained} XP, +${res.gold_gained} 💰`, "success");
        addLog(`✅ Виконано: ${h.title} (+${res.xp_gained} XP, +${res.gold_gained} 💰, 🔥 стрік → ${h.streak})`);

        if (res.levelled_up) {
            setEl("levelup-num", res.levelled_up);
            const b = document.getElementById("levelup-bonuses");
            if (b) b.innerHTML = `<span>+10 ❤️ Max HP</span><span>HP відновлено!</span>`;
            openModal("levelup-modal");
            addLog(`⭐ РІВЕНЬ ВИЩЕ! Тепер ${res.levelled_up}-й рівень`);
        }

        checkAchievements();
        renderHero();
        renderHabits();
    } catch (e) {
        toast(`❌ ${e.message}`, "danger");
    }
}

async function failHabit(id) {
    const h = habits.find(x => x.id === id);
    if (!h) return;
    const loss = DIFF[h.difficulty]?.hpLoss || 5;

    try {
        const res = await api("POST", `/habits/${id}/fail`);
        if (res.hp_lost === 0) {
            toast("⚠️ Цю звичку вже відмічено як провалену сьогодні!", "warning");
            return;
        }
        h.streak = 0;
        h.failedToday = true;
        currentUser = await api("GET", "/auth/me");

        addLog(`💔 Пропущено: ${h.title} (−${loss} HP)`);
        toast(`💔 <strong>${escHtml(h.title)}</strong> пропущено — −${loss} ❤️ HP`, "danger");

        if (res.died) {
            currentUser = await api("GET", "/auth/me");
            showDeathScreen();
            return;
        }

        renderHero();
        renderHabits();
    } catch (e) {
        toast(`❌ ${e.message}`, "danger");
    }
}

async function deleteHabit(id) {
    const h = habits.find(x => x.id === id);
    try {
        await api("DELETE", `/habits/${id}`);
        habits = habits.filter(x => x.id !== id);
        if (h) addLog(`🗑 Видалено звичку: ${h.title}`);
        renderHabits();
        renderHero();
    } catch (e) {
        toast(`❌ ${e.message}`, "danger");
    }
}

async function addHabit(title, difficulty, stat) {
    try {
        await api("POST", "/habits/", { title, difficulty, stat });
        const raw = await api("GET", `/habits/user/${currentUser.user_id}`);
        habits = raw.map(h => ({
            id:             h.id,
            title:          h.title,
            difficulty:     h.difficulty,
            stat:           h.stat,
            streak:         h.streak,
            best_streak:    h.best_streak,
            completedToday: h.is_done === 1,
            totalCompleted: h.total_completed,
        }));
        addLog(`➕ Нова звичка: ${title} (${DIFF[difficulty]?.label || difficulty})`);
        renderHabits();
        renderHero();
        checkAchievements();
    } catch (e) {
        toast(`❌ ${e.message}`, "danger");
    }
}

// ──────────────────────────────────────
// REWARDS
// ──────────────────────────────────────

function renderRewards() {
    const list = document.getElementById("rewards-list");
    if (!list) return;
    if (!rewards.length) {
        list.innerHTML = '<div class="empty-state">Нагород поки немає 🎁<br>Додай перший приз!</div>';
        return;
    }
    list.innerHTML = rewards.map(r => {
        const ok = currentUser.coins >= r.cost;
        return `<div class="card reward-card" data-id="${r.id}">
            <div class="card-info">
                <h4 class="card-title">${escHtml(r.title)}</h4>
                <div class="reward-cost">💰 ${r.cost} монет</div>
            </div>
            <div class="reward-actions">
                <button class="btn btn-buy ${ok ? "" : "btn-buy-disabled"}" data-action="buy" data-id="${r.id}">Придбати</button>
                <button class="action-btn btn-delete" data-action="delete-reward" data-id="${r.id}">🗑</button>
            </div>
        </div>`;
    }).join("");
}

async function buyReward(id) {
    const r = rewards.find(x => x.id === id);
    if (!r) return;
    if (currentUser.coins < r.cost) { toast(`💰 Не вистачає монет! Потрібно ${r.cost}`, "warning"); return; }

    try {
        await api("POST", `/users/me/rewards/${id}/buy`);
        currentUser = await api("GET", "/auth/me");
        toast(`🎁 Насолоджуйся: <strong>${escHtml(r.title)}</strong>!`, "success");
        addLog(`🎁 Куплено нагороду: ${r.title} (−${r.cost} 💰)`);
        checkAchievements();
        renderHero();
        renderRewards();
    } catch (e) {
        toast(`❌ ${e.message}`, "danger");
    }
}

async function deleteReward(id) {
    const r = rewards.find(x => x.id === id);
    try {
        await api("DELETE", `/users/me/rewards/${id}`);
        rewards = rewards.filter(x => x.id !== id);
        if (r) addLog(`🗑 Видалено нагороду: ${r.title}`);
        renderRewards();
    } catch (e) {
        toast(`❌ ${e.message}`, "danger");
    }
}

async function addReward(title, cost) {
    try {
        await api("POST", "/users/me/rewards", { title, cost: parseInt(cost, 10) });
        const rawR = await api("GET", "/users/me/rewards");
        rewards = rawR.map(r => ({ id: r.id, title: r.title, cost: r.cost }));
        addLog(`➕ Нова нагорода: ${title} (${cost} 💰)`);
        renderRewards();
    } catch (e) {
        toast(`❌ ${e.message}`, "danger");
    }
}

// ──────────────────────────────────────
// AVATAR SHOP
// ──────────────────────────────────────

function renderAvatarShop() {
    const grid = document.getElementById("avatar-grid");
    if (!grid) return;
    const owned = typeof currentUser.owned_avatars === "string"
        ? JSON.parse(currentUser.owned_avatars)
        : (currentUser.owned_avatars || ["🧙‍♂️"]);

    grid.innerHTML = AVATARS_DATA.map(av => {
        const isOwned   = owned.includes(av.emoji);
        const equipped  = currentUser.avatar === av.emoji;
        const canAfford = currentUser.coins >= av.cost;
        let btn = "";
        if (equipped)      btn = `<button class="btn-equipped" disabled>✓ Обрано</button>`;
        else if (isOwned)  btn = `<button class="btn-equip" data-avatar="${av.emoji}">Надягти</button>`;
        else               btn = `<button class="btn-buy-avatar ${canAfford ? "" : "btn-buy-disabled"}" data-avatar="${av.emoji}" data-cost="${av.cost}">💰 ${av.cost}</button>`;

        return `<div class="avatar-card rarity-${av.rarity} ${equipped ? "avatar-equipped" : ""}">
            <div class="avatar-card-emoji">${av.emoji}</div>
            <div class="avatar-card-name">${av.name}</div>
            <div class="rarity-label-${av.rarity}">${rarityLabel(av.rarity)}</div>
            ${btn}
        </div>`;
    }).join("");
}

function rarityLabel(r) {
    return { common:"Звичайний", uncommon:"Незвичайний", rare:"Рідкісний", epic:"Епічний", legendary:"Легендарний" }[r] || r;
}

async function buyAvatar(emoji, cost) {
    if (currentUser.coins < cost) { toast(`💰 Не вистачає монет!`, "warning"); return; }
    try {
        await api("POST", "/users/avatars/buy", { emoji });
        currentUser = await api("GET", "/auth/me");
        const av = AVATARS_DATA.find(a => a.emoji === emoji);
        toast(`🎭 Аватар <strong>${av ? av.name : ""}</strong> придбано!`, "success");
        addLog(`🎭 Куплено аватар ${emoji} ${av ? av.name : ""} (−${cost} 💰)`);
        checkAchievements();
        renderHero();
        renderAvatarShop();
    } catch (e) {
        toast(`❌ ${e.message}`, "danger");
    }
}

async function equipAvatar(emoji) {
    try {
        await api("POST", "/users/avatars/equip", { emoji });
        currentUser = await api("GET", "/auth/me");
        const av = AVATARS_DATA.find(a => a.emoji === emoji);
        toast(`🎭 Аватар ${av ? av.name : ""} обрано!`, "info");
        renderHero();
        renderAvatarShop();
    } catch (e) {
        toast(`❌ ${e.message}`, "danger");
    }
}

// ──────────────────────────────────────
// TABS
// ──────────────────────────────────────

function switchTab(name) {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.add("hidden"));
    document.querySelector(`.tab-btn[data-tab="${name}"]`)?.classList.add("active");
    document.getElementById(`tab-${name}`)?.classList.remove("hidden");
    if (name === "avatars")      renderAvatarShop();
    if (name === "achievements") renderAchievementsTab();
}

// ──────────────────────────────────────
// MODALS
// ──────────────────────────────────────

function openModal(id)  { document.getElementById(id)?.classList.remove("hidden"); }
function closeModal(id) { document.getElementById(id)?.classList.add("hidden"); }

// ──────────────────────────────────────
// COUNTDOWN TIMER
// ──────────────────────────────────────

function updateTimer() {
    const now  = new Date();
    const next = new Date(); next.setHours(24, 0, 0, 0);
    const ms   = next - now;
    const hh   = String(Math.floor(ms / 3600000)).padStart(2,"0");
    const mm   = String(Math.floor((ms % 3600000) / 60000)).padStart(2,"0");
    const ss   = String(Math.floor((ms % 60000)   / 1000)).padStart(2,"0");
    setEl("reset-timer", `${hh}:${mm}:${ss}`);
}

// ──────────────────────────────────────
// ADMIN PANEL
// ──────────────────────────────────────

let adminUsers = [];

async function loadAdminData() {
    try {
        const stats = await api("GET", "/admin/stats");
        setEl("stat-total-users",  stats.total_users);
        setEl("stat-active-today", stats.active_today);
        setEl("stat-total-habits", stats.done_today);
        setEl("stat-total-gold",   stats.total_gold);
        setEl("stat-banned",       stats.banned);
        setEl("admin-greeting",    `Вітаємо, ${currentUser.username} 👑`);

        const usersData = await api("GET", "/admin/users?page_size=100");
        adminUsers = usersData.users || [];
        renderAdminTable(adminUsers);
    } catch (e) {
        toast(`❌ ${e.message}`, "danger");
    }
}

function renderAdminTable(users, search = "", filterRole = "all", filterStatus = "all") {
    const tbody = document.getElementById("admin-users-tbody");
    const empty = document.getElementById("admin-empty");
    if (!tbody) return;

    let filtered = [...(users || adminUsers)];
    if (search)               filtered = filtered.filter(u => u.username.toLowerCase().includes(search.toLowerCase()));
    if (filterRole !== "all") filtered = filtered.filter(u => u.role === filterRole);
    if (filterStatus === "active") filtered = filtered.filter(u => !u.is_banned);
    if (filterStatus === "banned") filtered = filtered.filter(u => u.is_banned);

    if (!filtered.length) {
        tbody.innerHTML = "";
        empty.classList.remove("hidden");
        return;
    }
    empty.classList.add("hidden");

    const stats = typeof currentUser.stats === "string" ? JSON.parse(currentUser.stats) : currentUser.stats;

    tbody.innerHTML = filtered.map(u => {
        const isSelf = u.id === currentUser.user_id;
        return `<tr class="${u.is_banned ? "row-banned" : ""}">
            <td>
                <div class="td-user">
                    <span class="td-avatar">${u.avatar || "🧙‍♂️"}</span>
                    <div>
                        <div class="td-username">${escHtml(u.username)} ${isSelf ? "<span style='font-size:11px;color:var(--text-dim)'>(ти)</span>" : ""}</div>
                        <div class="td-joined">${new Date(u.created_at).toLocaleDateString("uk-UA")}</div>
                    </div>
                </div>
            </td>
            <td><span class="role-pill ${u.role === "admin" ? "role-admin" : "role-user"}">${u.role === "admin" ? "👑 Адмін" : "🧙 Гравець"}</span></td>
            <td>${u.level}</td>
            <td style="color:var(--gold);font-weight:700">${u.coins}</td>
            <td>${u.streak} 🔥</td>
            <td>${u.total_completed}</td>
            <td><span class="status-pill ${u.is_banned ? "status-banned" : "status-active"}">${u.is_banned ? "🚫 Бан" : "✅ Активний"}</span></td>
            <td style="font-size:12px;color:var(--text-dim)">${new Date(u.created_at).toLocaleDateString("uk-UA")}</td>
            <td>
                <div class="admin-actions">
                    <button class="btn btn-sm btn-view"   data-aaction="view"   data-uid="${u.id}">👁 Деталі</button>
                    <button class="btn btn-sm btn-edit"   data-aaction="edit"   data-uid="${u.id}" ${isSelf ? "disabled" : ""}>✏️ Ред.</button>
                    ${!isSelf ? `
                    ${u.role !== "admin"
                        ? `<button class="btn btn-sm btn-promote" data-aaction="promote" data-uid="${u.id}">👑 Адмін</button>`
                        : `<button class="btn btn-sm btn-demote"  data-aaction="demote"  data-uid="${u.id}">↓ Гравець</button>`
                    }
                    ${u.is_banned
                        ? `<button class="btn btn-sm btn-unban"  data-aaction="unban"  data-uid="${u.id}">✅ Розбан</button>`
                        : `<button class="btn btn-sm btn-ban"    data-aaction="ban"    data-uid="${u.id}">🚫 Бан</button>`
                    }
                    <button class="btn btn-sm btn-delete-user" data-aaction="delete" data-uid="${u.id}">🗑</button>
                    ` : ""}
                </div>
            </td>
        </tr>`;
    }).join("");
}

async function adminAction(action, uid) {
    const userId = parseInt(uid, 10);
    try {
        switch (action) {
            case "view": {
                const detail = await api("GET", `/admin/users/${userId}`);
                openUserDetail(detail);
                break;
            }
            case "edit": {
                const detail = await api("GET", `/admin/users/${userId}`);
                openUserEdit(detail.user);
                break;
            }
            case "ban":
                if (confirm("Заблокувати гравця?")) {
                    await api("POST", `/admin/users/${userId}/ban`);
                    toast("🚫 Гравця заблоковано", "warning");
                    await loadAdminData();
                }
                break;
            case "unban":
                await api("POST", `/admin/users/${userId}/unban`);
                toast("✅ Гравця розблоковано", "success");
                await loadAdminData();
                break;
            case "promote":
                if (confirm("Зробити адміністратором?")) {
                    await api("PUT", `/admin/users/${userId}`, { role: "admin" });
                    toast("👑 Роль підвищено", "success");
                    await loadAdminData();
                }
                break;
            case "demote":
                if (confirm("Зняти адмін-права?")) {
                    await api("PUT", `/admin/users/${userId}`, { role: "player" });
                    toast("↓ Роль знижено", "info");
                    await loadAdminData();
                }
                break;
            case "delete":
                if (confirm("ВИДАЛИТИ гравця? Це незворотньо!")) {
                    await api("DELETE", `/admin/users/${userId}`);
                    toast("🗑 Гравця видалено", "danger");
                    await loadAdminData();
                }
                break;
        }
    } catch (e) {
        toast(`❌ ${e.message}`, "danger");
    }
}

function openUserDetail(detail) {
    const u = detail.user;
    const stats = typeof u.stats === "string" ? JSON.parse(u.stats) : (u.stats || {});
    const achs  = typeof u.achievements === "string" ? JSON.parse(u.achievements) : (u.achievements || []);
    setEl("ud-title", `${u.avatar || "🧙‍♂️"} ${u.username}`);
    document.getElementById("ud-content").innerHTML = `
        <div class="ud-row">
            <div class="ud-stat"><div class="ud-stat-label">Рівень</div><div class="ud-stat-val">${u.level}</div></div>
            <div class="ud-stat"><div class="ud-stat-label">XP</div><div class="ud-stat-val">${u.xp}</div></div>
            <div class="ud-stat"><div class="ud-stat-label">Золото</div><div class="ud-stat-val" style="color:var(--gold)">${u.coins}</div></div>
            <div class="ud-stat"><div class="ud-stat-label">Стрік</div><div class="ud-stat-val">${u.streak} 🔥</div></div>
            <div class="ud-stat"><div class="ud-stat-label">Виконано</div><div class="ud-stat-val">${u.total_completed}</div></div>
        </div>
        <div class="ud-row">
            <div class="ud-stat"><div class="ud-stat-label">⚔️ Сила</div><div class="ud-stat-val">${stats.str || 1}</div></div>
            <div class="ud-stat"><div class="ud-stat-label">📚 Інтелект</div><div class="ud-stat-val">${stats.wis || 1}</div></div>
            <div class="ud-stat"><div class="ud-stat-label">🛡️ Витривалість</div><div class="ud-stat-val">${stats.end || 1}</div></div>
            <div class="ud-stat"><div class="ud-stat-label">✨ Харизма</div><div class="ud-stat-val">${stats.cha || 1}</div></div>
        </div>
        <div>
            <div class="ud-stat-label" style="margin-bottom:8px">Звички (${detail.habits.length})</div>
            <div class="ud-habits-list">
                ${detail.habits.length ? detail.habits.map(h => `
                    <div class="ud-habit-row">
                        <span>${escHtml(h.title)}</span>
                        <span style="color:var(--text-muted);font-size:12px">🔥 ${h.streak} · ✅ ${h.total_completed} · <span class="badge badge-${h.difficulty}">${DIFF[h.difficulty]?.label || h.difficulty}</span></span>
                    </div>`).join("") : '<div style="color:var(--text-dim);font-size:13px">Немає звичок</div>'}
            </div>
        </div>
        <div>
            <div class="ud-stat-label" style="margin-bottom:8px">Досягнення (${achs.length})</div>
            <div style="display:flex;gap:8px;flex-wrap:wrap">
                ${achs.map(id => {
                    const a = ACHIEVEMENTS_DATA.find(x => x.id === id);
                    return a ? `<span class="ach-icon-mini" title="${a.name}">${a.icon}</span>` : "";
                }).join("") || '<span style="color:var(--text-dim);font-size:13px">Ще немає</span>'}
            </div>
        </div>
    `;
    openModal("user-detail-modal");
}

let editingUserId = null;

function openUserEdit(user) {
    editingUserId = user.id;
    setEl("admin-edit-title", `Редагування: ${user.username}`);
    document.getElementById("admin-edit-content").innerHTML = `
        <div class="admin-edit-fields">
            <div class="form-group">
                <label>Роль</label>
                <select id="edit-role">
                    <option value="player" ${user.role === "player" ? "selected" : ""}>🧙 Гравець</option>
                    <option value="admin"  ${user.role === "admin"  ? "selected" : ""}>👑 Адмін</option>
                </select>
            </div>
            <div class="form-group">
                <label>Монети</label>
                <input type="number" id="edit-coins" value="${user.coins}" min="0" max="99999">
            </div>
            <div class="form-group">
                <label>Рівень</label>
                <input type="number" id="edit-level" value="${user.level}" min="1" max="100">
            </div>
        </div>
    `;
    openModal("admin-edit-modal");
}

async function saveUserEdit() {
    if (!editingUserId) return;
    try {
        const role  = document.getElementById("edit-role")?.value;
        const coins = parseInt(document.getElementById("edit-coins")?.value || "0", 10);
        const level = parseInt(document.getElementById("edit-level")?.value || "1", 10);
        await api("PUT", `/admin/users/${editingUserId}`, { role, coins, level });
        closeModal("admin-edit-modal");
        editingUserId = null;
        toast("✅ Зміни збережено", "success");
        await loadAdminData();
    } catch (e) {
        toast(`❌ ${e.message}`, "danger");
    }
}

// ──────────────────────────────────────
// GAME INIT
// ──────────────────────────────────────

function startGame() {
    renderHero();
    renderHabits();
    renderRewards();
    renderLog();
    renderAchievementsMini();
    renderAchievementsTab();
    checkAchievements();
    checkDeathOnLoad();
    startDeathPolling(); // ← НОВЕ: запускаємо фоновий polling

    const hr = new Date().getHours();
    const greet = hr < 12 ? "🌅 Доброго ранку" : hr < 18 ? "☀️ Доброго дня" : "🌙 Доброго вечора";
    setTimeout(() => toast(`${greet}, <strong>${escHtml(currentUser.username)}</strong>! Готовий до нових звичок?`, "info", 3500), 500);
}

// ──────────────────────────────────────
// екран смерті

let deathTimerInterval = null;
let deathPollingInterval = null;  // фоновий polling

function stopDeathTimer() {
    if (deathTimerInterval) {
        clearInterval(deathTimerInterval);
        deathTimerInterval = null;
    }
}

function showDeathScreen() {
    if (!currentUser) return;
    const dead = isUserDead(currentUser);
    if (!dead) return;

    openModal("death-modal");
    if (currentUser.death_seconds_left > 0) {
        startDeathTimer();
    } else {
        setEl("death-timer", "00:00");
        setPct("death-timer-bar", 0);
        tryRevive();
    }
}

function startDeathTimer() {
    stopDeathTimer();

    const startedAt = Date.now();
    const totalMs   = (currentUser.death_seconds_left || 900) * 1000;

    function tick() {
        const elapsed = Date.now() - startedAt;
        const msLeft  = totalMs - elapsed;

        if (msLeft <= 0) {
            stopDeathTimer();
            tryRevive();  // пробуємо воскреснути кілька разів
            return;
        }

        const totalSec = Math.ceil(msLeft / 1000);
        const mm = String(Math.floor(totalSec / 60)).padStart(2, "0");
        const ss = String(totalSec % 60).padStart(2, "0");
        setEl("death-timer", `${mm}:${ss}`);
        setPct("death-timer-bar", Math.max(0, (msLeft / totalMs) * 100));
    }

    tick();
    deathTimerInterval = setInterval(tick, 1000);
}

async function refreshCurrentUser() {
    currentUser = await api("GET", "/auth/me");
    return currentUser;
}

function completeRevival(user) {
    stopDeathTimer();
    closeModal("death-modal");
    toast("❤️ Ти воскрес! HP відновлено!", "success", 4000);
    addLog("❤️ Воскресіння! HP повністю відновлено");
    currentUser = user;
    renderHero();
    renderHabits();
}

function isUserDead(user) {
    if (!user) return false;
    if (typeof user.death_seconds_left === "number") {
        return user.death_seconds_left > 0;
    }
    return user.hp === 0;
}

async function tryRevive(attempt = 0) {
    try {
        const result = await api("POST", "/auth/revive");
        const user = result.user ? result.user : await refreshCurrentUser();
        completeRevival(user);
        return;
    } catch (err) {
        const user = await refreshCurrentUser().catch(() => null);
        if (!user) {
            stopDeathTimer();
            closeModal("death-modal");
            toast("⚠️ Не вдалося оновити стан гравця. Онови сторінку (F5)", "warning", 5000);
            return;
        }

        if (isUserDead(user)) {
            if (!document.getElementById("death-modal")?.classList.contains("hidden")) {
                startDeathTimer();
            } else {
                showDeathScreen();
            }
            const retryDelay = 1000;
            if (attempt < 60) {
                setTimeout(() => tryRevive(attempt + 1), retryDelay);
            }
            return;
        }

        completeRevival(user);
        return;
    }
}

function checkDeathOnLoad() {
    if (!isUserDead(currentUser)) return;
    showDeathScreen();
}

// Фоновий polling для автовідстеження смерті
function startDeathPolling() {
    if (deathPollingInterval) clearInterval(deathPollingInterval);
    
    deathPollingInterval = setInterval(async () => {
        try {
            const user = await api("GET", "/auth/me");
            currentUser = user;
            
            const deathModal = document.getElementById("death-modal");
            const isModalOpen = deathModal && !deathModal.classList.contains("hidden");
            
            if (isUserDead(user)) {
                if (!isModalOpen) {
                    showDeathScreen();
                }
            } else if (isModalOpen) {
                completeRevival(user);
            }
            
        } catch (e) {
            // Ігноруємо помилки
        }
    }, 1000);
}

function stopDeathPolling() {
    if (deathPollingInterval) {
        clearInterval(deathPollingInterval);
        deathPollingInterval = null;
    }
}

// ──────────────────────────────────────
// UTIL
// ──────────────────────────────────────

function escHtml(str) {
    return String(str)
        .replace(/&/g,"&amp;").replace(/</g,"&lt;")
        .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

// ──────────────────────────────────────
// EVENT LISTENERS
// ──────────────────────────────────────

function initEvents() {

    // ── AUTH TABS
    document.querySelectorAll(".auth-tab").forEach(btn =>
        btn.addEventListener("click", () => {
            const tab = btn.dataset.authtab;
            document.querySelectorAll(".auth-tab").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            document.getElementById("auth-login-panel").classList.toggle("hidden",    tab !== "login");
            document.getElementById("auth-register-panel").classList.toggle("hidden", tab !== "register");
            clearAuthErrors();
        })
    );

    // ── LOGIN
    document.getElementById("login-btn").addEventListener("click", () => {
        const u = document.getElementById("login-username").value.trim();
        const p = document.getElementById("login-password").value;
        doLogin(u, p);
    });
    document.getElementById("login-password").addEventListener("keydown", e => {
        if (e.key === "Enter") document.getElementById("login-btn").click();
    });

    // ── REGISTER
    document.getElementById("register-btn").addEventListener("click", () => {
        const u = document.getElementById("reg-username").value;
        const p = document.getElementById("reg-password").value;
        const c = document.getElementById("reg-confirm").value;
        doRegister(u, p, c);
    });
    document.getElementById("reg-confirm").addEventListener("keydown", e => {
        if (e.key === "Enter") document.getElementById("register-btn").click();
    });

    // ── DEMO ACCOUNTS
    document.getElementById("demo-fill-admin").addEventListener("click", () => {
        document.getElementById("login-username").value = "admin";
        document.getElementById("login-password").value = "admin123";
        document.querySelectorAll(".auth-tab").forEach(b => b.classList.remove("active"));
        document.querySelector('.auth-tab[data-authtab="login"]').classList.add("active");
        document.getElementById("auth-login-panel").classList.remove("hidden");
        document.getElementById("auth-register-panel").classList.add("hidden");
    });
    document.getElementById("demo-fill-user").addEventListener("click", () => {
        document.getElementById("login-username").value = "hero_student";
        document.getElementById("login-password").value = "hero123";
        document.querySelectorAll(".auth-tab").forEach(b => b.classList.remove("active"));
        document.querySelector('.auth-tab[data-authtab="login"]').classList.add("active");
        document.getElementById("auth-login-panel").classList.remove("hidden");
        document.getElementById("auth-register-panel").classList.add("hidden");
    });

    // ── PASSWORD TOGGLE
    document.querySelectorAll(".toggle-pass").forEach(btn =>
        btn.addEventListener("click", () => {
            const inp = document.getElementById(btn.dataset.target);
            if (!inp) return;
            inp.type = inp.type === "password" ? "text" : "password";
            btn.textContent = inp.type === "password" ? "👁" : "🙈";
        })
    );

    // ── LOGOUT
    document.getElementById("game-logout-btn").addEventListener("click", doLogout);

    // ── ADMIN button
    document.getElementById("game-admin-btn").addEventListener("click", async () => {
        await loadAdminData();
        showView("admin-panel");
    });

    // ── ADMIN: back to game
    document.getElementById("admin-play-btn").addEventListener("click", async () => {
        await loadGameData();
        startGame();
        showView("main-app");
    });

    // ── ADMIN: logout
    document.getElementById("admin-logout-btn").addEventListener("click", doLogout);

    // ── ADMIN: table actions
    document.getElementById("admin-users-tbody").addEventListener("click", e => {
        const btn = e.target.closest("[data-aaction]");
        if (!btn) return;
        adminAction(btn.dataset.aaction, btn.dataset.uid);
    });

    // ── ADMIN: search & filters
    document.getElementById("admin-search").addEventListener("input", applyAdminFilters);
    document.getElementById("admin-filter-role").addEventListener("change", applyAdminFilters);
    document.getElementById("admin-filter-status").addEventListener("change", applyAdminFilters);

    // ── ADMIN edit modal
    document.getElementById("admin-edit-close").addEventListener("click",  () => closeModal("admin-edit-modal"));
    document.getElementById("admin-edit-cancel").addEventListener("click", () => closeModal("admin-edit-modal"));
    document.getElementById("admin-edit-save").addEventListener("click",   saveUserEdit);

    // ── USER DETAIL modal
    document.getElementById("ud-close").addEventListener("click", () => closeModal("user-detail-modal"));

    // ── ADD HABIT modal
    document.getElementById("add-habit-btn").addEventListener("click",     () => openModal("habit-modal"));
    document.getElementById("habit-modal-close").addEventListener("click", () => closeModal("habit-modal"));
    document.getElementById("habit-modal-cancel").addEventListener("click",() => closeModal("habit-modal"));
    document.getElementById("habit-modal-save").addEventListener("click",  () => {
        const title = document.getElementById("habit-title").value.trim();
        const diff  = document.getElementById("habit-difficulty").value;
        const stat  = document.getElementById("habit-stat").value;
        if (!title) { toast("⚠️ Введи назву звички!", "warning"); return; }
        addHabit(title, diff, stat);
        document.getElementById("habit-title").value = "";
        closeModal("habit-modal");
    });
    document.getElementById("habit-title").addEventListener("keydown", e => {
        if (e.key === "Enter") document.getElementById("habit-modal-save").click();
    });

    // ── ADD REWARD modal
    document.getElementById("add-reward-btn").addEventListener("click",     () => openModal("reward-modal"));
    document.getElementById("reward-modal-close").addEventListener("click", () => closeModal("reward-modal"));
    document.getElementById("reward-modal-cancel").addEventListener("click",() => closeModal("reward-modal"));
    document.getElementById("reward-modal-save").addEventListener("click",  () => {
        const title = document.getElementById("reward-title").value.trim();
        const cost  = document.getElementById("reward-cost").value;
        if (!title || !cost || parseInt(cost,10) < 1) { toast("⚠️ Заповни всі поля!", "warning"); return; }
        addReward(title, cost);
        document.getElementById("reward-title").value = "";
        document.getElementById("reward-cost").value  = "";
        closeModal("reward-modal");
    });

    // ── LEVEL UP modal
    document.getElementById("levelup-close").addEventListener("click", () => closeModal("levelup-modal"));

    // ── HABITS list
    document.getElementById("habits-list").addEventListener("click", e => {
        const btn = e.target.closest("[data-action]");
        if (!btn) return;
        const id = parseInt(btn.dataset.id, 10);
        if      (btn.dataset.action === "complete") completeHabit(id);
        else if (btn.dataset.action === "fail")     failHabit(id);
        else if (btn.dataset.action === "delete")   { if (confirm("Видалити звичку?")) deleteHabit(id); }
    });

    // ── REWARDS list
    document.getElementById("rewards-list").addEventListener("click", e => {
        const btn = e.target.closest("[data-action]");
        if (!btn) return;
        const id = parseInt(btn.dataset.id, 10);
        if      (btn.dataset.action === "buy")           buyReward(id);
        else if (btn.dataset.action === "delete-reward") { if (confirm("Видалити нагороду?")) deleteReward(id); }
    });

    // ── AVATAR grid
    document.getElementById("avatar-grid").addEventListener("click", e => {
        const btn = e.target.closest("[data-avatar]");
        if (!btn) return;
        const emoji = btn.dataset.avatar;
        const cost  = parseInt(btn.dataset.cost || "0", 10);
        if      (btn.classList.contains("btn-buy-avatar")) buyAvatar(emoji, cost);
        else if (btn.classList.contains("btn-equip"))      equipAvatar(emoji);
    });

    // ── TABS
    document.querySelectorAll(".tab-btn").forEach(btn =>
        btn.addEventListener("click", () => switchTab(btn.dataset.tab))
    );

    // ── FILTERS
    document.querySelectorAll(".filter-btn").forEach(btn =>
        btn.addEventListener("click", () => {
            document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            renderHabits(btn.dataset.filter);
        })
    );

    // ── Avatar shortcut in header
    document.getElementById("open-avatar-shop").addEventListener("click", () => {
        switchTab("avatars");
        document.querySelector(".shop-section")?.scrollIntoView({ behavior:"smooth" });
    });

    // ── Clear log
    document.getElementById("clear-log-btn").addEventListener("click", async () => {
        activityLog = [];
        renderLog();
        try { await api("DELETE", "/users/me/activity-log"); } catch {}
    });

    // ── Close modals on overlay click (крім death-modal)
    document.querySelectorAll(".modal-overlay").forEach(ov =>
        ov.addEventListener("click", e => {
            if (e.target === ov && !ov.dataset.noClose) ov.classList.add("hidden");
        })
    );
}

function applyAdminFilters() {
    const search = document.getElementById("admin-search")?.value || "";
    const role   = document.getElementById("admin-filter-role")?.value || "all";
    const status = document.getElementById("admin-filter-status")?.value || "all";
    renderAdminTable(adminUsers, search, role, status);
}

// ──────────────────────────────────────
// BOOT
// ──────────────────────────────────────

async function init() {
    initEvents();
    updateTimer();
    setInterval(updateTimer, 1000);
    
    // ← ДОДАЙ ЦЕ:
    const hasSession = await restoreSession();
    if (hasSession) {
        await enterApp();  // Автовхід, якщо токен валідний
    } else {
        showView("auth-screen");
    }
}

document.addEventListener("DOMContentLoaded", init);