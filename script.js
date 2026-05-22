"use strict";

/* ════════════════════════════════════
   HABIT RPG — script.js
   Full game logic: XP, gold, streaks,
   avatar shop, achievements, log
════════════════════════════════════ */

// ─────────────────────────────────────
// STATIC DATA
// ─────────────────────────────────────

const AVATARS_DATA = [
    { emoji: "🧙‍♂️", name: "Маг",         cost: 0,    rarity: "common" },
    { emoji: "🧙‍♀️", name: "Чаклунка",    cost: 100,  rarity: "common" },
    { emoji: "🦸‍♂️", name: "Супергерой",  cost: 150,  rarity: "uncommon" },
    { emoji: "🦸‍♀️", name: "Супергероїня",cost: 150,  rarity: "uncommon" },
    { emoji: "🧝‍♂️", name: "Ельф",        cost: 250,  rarity: "uncommon" },
    { emoji: "🧝‍♀️", name: "Ельфійка",    cost: 250,  rarity: "uncommon" },
    { emoji: "🧛‍♂️", name: "Вампір",      cost: 400,  rarity: "rare" },
    { emoji: "🤴",   name: "Принц",       cost: 500,  rarity: "rare" },
    { emoji: "👸",   name: "Принцеса",    cost: 500,  rarity: "rare" },
    { emoji: "🥷",   name: "Ніндзя",      cost: 750,  rarity: "epic" },
    { emoji: "🤖",   name: "Робот",       cost: 900,  rarity: "epic" },
    { emoji: "👑",   name: "Монарх",      cost: 1200, rarity: "legendary" },
    { emoji: "🐉",   name: "Дракон",      cost: 2000, rarity: "legendary" },
];

const ACHIEVEMENTS_DATA = [
    { id: "first_step",      icon: "🌟", name: "Перший Крок",      desc: "Виконай першу звичку",              check: s => s.hero.totalHabitsCompleted >= 1 },
    { id: "habit_collector", icon: "📋", name: "Організатор",      desc: "Додай 5 звичок одночасно",          check: s => s.habits.length >= 5 },
    { id: "week_streak",     icon: "🔥", name: "Тиждень Вогню",    desc: "7 днів поспіль",                    check: s => s.hero.streak >= 7 },
    { id: "month_streak",    icon: "🌙", name: "Місяць Сили",      desc: "30 днів поспіль",                   check: s => s.hero.streak >= 30 },
    { id: "habits_50",       icon: "💪", name: "Залізна Воля",     desc: "Виконай 50 звичок загалом",         check: s => s.hero.totalHabitsCompleted >= 50 },
    { id: "habits_100",      icon: "🏅", name: "Легіонер",         desc: "Виконай 100 звичок загалом",        check: s => s.hero.totalHabitsCompleted >= 100 },
    { id: "rich",            icon: "💎", name: "Заможний",         desc: "Накопич 500 монет одночасно",       check: s => s.hero.gold >= 500 },
    { id: "mega_rich",       icon: "🏦", name: "Казначей",         desc: "Накопич 2000 монет одночасно",      check: s => s.hero.gold >= 2000 },
    { id: "level5",          icon: "⚔️", name: "Відважний Герой",  desc: "Досягни 5-го рівня",                check: s => s.hero.level >= 5 },
    { id: "level10",         icon: "🏆", name: "Легенда Краю",     desc: "Досягни 10-го рівня",               check: s => s.hero.level >= 10 },
    { id: "avatar_shop",     icon: "🎭", name: "Перевтілення",     desc: "Купи свій перший аватар",           check: s => s.hero.ownedAvatars.length >= 2 },
    { id: "buy_reward",      icon: "🎁", name: "Заслужена Нагорода",desc: "Купи нагороду вперше",             check: s => s.hero.totalRewardsBought >= 1 },
];

const DIFF = {
    easy:   { xp: 10,  gold: 5,  label: "Легка",   statBoost: 1, hpLoss: 5  },
    medium: { xp: 20,  gold: 12, label: "Середня", statBoost: 2, hpLoss: 10 },
    hard:   { xp: 40,  gold: 25, label: "Важка",   statBoost: 3, hpLoss: 15 },
};

const STAT_ICONS = { str: "⚔️", wis: "📚", end: "🛡️", cha: "✨" };

const XP_FOR_LEVEL = (lvl) => 100 + (lvl - 1) * 50;

// ─────────────────────────────────────
// DEFAULT STATE
// ─────────────────────────────────────

function defaultState() {
    return {
        hero: {
            name: "Мій Герой",
            level: 1,
            xp: 30,
            hp: 100,
            maxHp: 100,
            gold: 150,
            streak: 0,
            lastActiveDate: null,
            avatar: "🧙‍♂️",
            ownedAvatars: ["🧙‍♂️"],
            stats: { str: 2, wis: 3, end: 1, cha: 1 },
            achievements: [],
            totalHabitsCompleted: 0,
            totalRewardsBought: 0,
        },
        habits: [
            { id: 1, title: "Ранкова зарядка 15 хв",  difficulty: "easy",   stat: "str", streak: 0, completedToday: false, totalCompleted: 0 },
            { id: 2, title: "Вчити Python (FastAPI)",  difficulty: "hard",   stat: "wis", streak: 0, completedToday: false, totalCompleted: 0 },
        ],
        rewards: [
            { id: 101, title: "Пограти в ігри 1 годину", cost: 50 },
            { id: 102, title: "З'їсти смачну піцу",      cost: 120 },
        ],
        log: [],
        nextHabitId: 3,
        nextRewardId: 103,
    };
}

// ─────────────────────────────────────
// STATE
// ─────────────────────────────────────

let S = defaultState();

function save() {
    try { localStorage.setItem("habitrpg_v2", JSON.stringify(S)); } catch(_) {}
}

function load() {
    try {
        const raw = localStorage.getItem("habitrpg_v2");
        if (raw) {
            S = JSON.parse(raw);
            // safe migrations
            if (S.hero.totalHabitsCompleted === undefined) S.hero.totalHabitsCompleted = 0;
            if (S.hero.totalRewardsBought   === undefined) S.hero.totalRewardsBought = 0;
            if (!S.hero.achievements) S.hero.achievements = [];
            if (!S.hero.ownedAvatars) S.hero.ownedAvatars = ["🧙‍♂️"];
            if (!S.log) S.log = [];
        }
    } catch(_) { S = defaultState(); }
}

// ─────────────────────────────────────
// DATE HELPERS
// ─────────────────────────────────────

function today() { return new Date().toISOString().slice(0, 10); }
function yesterday() {
    const d = new Date(); d.setDate(d.getDate() - 1);
    return d.toISOString().slice(0, 10);
}

// ─────────────────────────────────────
// DAILY RESET
// ─────────────────────────────────────

function checkDailyReset() {
    const td = today();
    const yd = yesterday();
    const last = S.hero.lastActiveDate;
    if (!last) return;

    if (last !== td) {
        // new day — reset habits
        S.habits.forEach(h => { h.completedToday = false; });

        if (last !== yd) {
            // missed a day → reset streak
            if (S.hero.streak > 0) {
                addLog(`💔 Стрік ${S.hero.streak} днів скинуто через пропуск`);
                S.hero.streak = 0;
            }
        }
        save();
    }
}

// ─────────────────────────────────────
// LOG
// ─────────────────────────────────────

function addLog(msg) {
    const t = new Date().toLocaleTimeString("uk-UA", { hour: "2-digit", minute: "2-digit" });
    S.log.unshift({ msg, t });
    if (S.log.length > 40) S.log.pop();
    renderLog();
}

function renderLog() {
    const el = document.getElementById("activity-log");
    if (!el) return;
    if (S.log.length === 0) {
        el.innerHTML = '<div class="log-empty">Поки що нічого не відбулось...</div>';
        return;
    }
    el.innerHTML = S.log.map(e =>
        `<div class="log-entry"><span class="log-time">${e.t}</span><span class="log-msg">${e.msg}</span></div>`
    ).join("");
}

// ─────────────────────────────────────
// TOAST
// ─────────────────────────────────────

function toast(html, type = "info", ms = 3200) {
    const c = document.getElementById("toast-container");
    const el = document.createElement("div");
    el.className = `toast toast-${type}`;
    el.innerHTML = html;
    c.appendChild(el);
    requestAnimationFrame(() => { requestAnimationFrame(() => el.classList.add("toast-visible")); });
    setTimeout(() => {
        el.classList.remove("toast-visible");
        setTimeout(() => el.remove(), 400);
    }, ms);
}

// ─────────────────────────────────────
// HERO RENDER
// ─────────────────────────────────────

function renderHero() {
    const h = S.hero;
    const xpNeed = XP_FOR_LEVEL(h.level);
    const xpPct  = Math.min((h.xp / xpNeed) * 100, 100).toFixed(1);
    const hpPct  = Math.min((h.hp / h.maxHp) * 100, 100).toFixed(1);

    setEl("hero-avatar",  h.avatar);
    setEl("hero-level",   h.level);
    setEl("hero-name",    h.name);
    setEl("xp-text",      `${h.xp}/${xpNeed}`);
    setEl("hp-text",      `${h.hp}/${h.maxHp}`);
    setEl("gold-count",   h.gold);
    setEl("avatar-gold",  h.gold);
    setEl("streak-count", h.streak);

    setPct("xp-bar-inner", xpPct);
    setPct("hp-bar-inner",  hpPct);

    // HP color
    const hpBar = document.getElementById("hp-bar-inner");
    hpBar.className = "bar-inner hp-color" +
        (h.hp / h.maxHp < 0.25 ? " hp-critical" : h.hp / h.maxHp < 0.5 ? " hp-warning" : "");

    // Streak badge
    document.getElementById("streak-badge")
        .classList.toggle("streak-epic", h.streak >= 7);

    // Stats
    const MAX = 99;
    ["str", "wis", "end", "cha"].forEach(st => {
        setEl(`${st}-val`, h.stats[st]);
        setPct(`${st}-bar`, (h.stats[st] / MAX) * 100);
    });

    // Habits progress
    const done  = S.habits.filter(h => h.completedToday).length;
    const total = S.habits.length;
    setEl("habits-progress-text", `${done}/${total} звичок виконано сьогодні`);

    renderAchievementsMini();
}

function setEl(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}
function setPct(id, pct) {
    const el = document.getElementById(id);
    if (el) el.style.width = pct + "%";
}

// ─────────────────────────────────────
// ACHIEVEMENTS
// ─────────────────────────────────────

function checkAchievements() {
    ACHIEVEMENTS_DATA.forEach(a => {
        if (!S.hero.achievements.includes(a.id) && a.check(S)) {
            S.hero.achievements.push(a.id);
            toast(`🏆 Досягнення: <strong>${a.name}</strong>! ${a.icon}`, "achievement", 4500);
            addLog(`🏆 Нове досягнення: ${a.icon} ${a.name}`);
        }
    });
    renderAchievementsMini();
    renderAchievementsTab();
    // Update count
    const lbl = document.getElementById("ach-count-label");
    if (lbl) lbl.textContent = `${S.hero.achievements.length}/${ACHIEVEMENTS_DATA.length}`;
}

function renderAchievementsMini() {
    const el = document.getElementById("achievements-row");
    if (!el) return;
    const unlocked = S.hero.achievements.slice(-6);
    if (unlocked.length === 0) {
        el.innerHTML = '<span class="ach-empty">Ще немає</span>';
        return;
    }
    el.innerHTML = unlocked.map(id => {
        const a = ACHIEVEMENTS_DATA.find(x => x.id === id);
        return a ? `<span class="ach-icon-mini" title="${a.name}: ${a.desc}">${a.icon}</span>` : "";
    }).join("");
}

function renderAchievementsTab() {
    const el = document.getElementById("achievements-list");
    if (!el) return;
    el.innerHTML = ACHIEVEMENTS_DATA.map(a => {
        const unlocked = S.hero.achievements.includes(a.id);
        return `<div class="ach-card ${unlocked ? "ach-unlocked" : "ach-locked"}">
            <div class="ach-icon-big">${unlocked ? a.icon : "🔒"}</div>
            <div class="ach-info">
                <div class="ach-name">${a.name}</div>
                <div class="ach-desc">${a.desc}</div>
            </div>
        </div>`;
    }).join("");
    const lbl = document.getElementById("ach-count-label");
    if (lbl) lbl.textContent = `${S.hero.achievements.length}/${ACHIEVEMENTS_DATA.length}`;
}

// ─────────────────────────────────────
// HABITS RENDER
// ─────────────────────────────────────

let activeFilter = "all";

function renderHabits(filter) {
    if (filter !== undefined) activeFilter = filter;
    const list = document.getElementById("habits-list");
    const habits = activeFilter === "all"
        ? S.habits
        : S.habits.filter(h => h.difficulty === activeFilter);

    if (habits.length === 0) {
        list.innerHTML = '<div class="empty-state">Немає звичок у цій категорії ⚔️</div>';
        return;
    }
    list.innerHTML = habits.map(h => habitCard(h)).join("");
}

function habitCard(h) {
    const cfg = DIFF[h.difficulty];
    const done = h.completedToday;
    return `
    <div class="card habit-card ${done ? "habit-done" : ""}" data-id="${h.id}">
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
            <button class="action-btn btn-success" data-action="complete" data-id="${h.id}" title="Виконано">✓</button>
            <button class="action-btn btn-danger"  data-action="fail"     data-id="${h.id}" title="Пропущено">✗</button>
            <button class="action-btn btn-delete"  data-action="delete"   data-id="${h.id}" title="Видалити">🗑</button>
        </div>
    </div>`;
}

// ─────────────────────────────────────
// HABIT ACTIONS
// ─────────────────────────────────────

function completeHabit(id) {
    const h = S.habits.find(x => x.id === id);
    if (!h) return;
    if (h.completedToday) { toast("⚠️ Цю звичку вже виконано сьогодні!", "warning"); return; }

    const cfg = DIFF[h.difficulty];
    h.completedToday = true;
    h.streak++;
    h.totalCompleted++;
    S.hero.xp   += cfg.xp;
    S.hero.gold += cfg.gold;
    S.hero.stats[h.stat] = Math.min(S.hero.stats[h.stat] + cfg.statBoost, 99);
    S.hero.totalHabitsCompleted++;

    // Day streak logic
    const td = today();
    const yd = yesterday();
    const last = S.hero.lastActiveDate;
    if (last !== td) {
        if      (last === yd) { S.hero.streak++; }
        else if (!last)       { S.hero.streak = 1; }
        else                  { S.hero.streak = 1; } // missed days, restart
        S.hero.lastActiveDate = td;
    }

    toast(`✅ <strong>${escHtml(h.title)}</strong> — +${cfg.xp} XP, +${cfg.gold} 💰`, "success");
    addLog(`✅ Виконано: ${h.title} (+${cfg.xp} XP, +${cfg.gold} 💰, 🔥 стрік → ${h.streak})`);

    checkLevelUp();
    checkAchievements();
    save();
    renderHero();
    renderHabits();
}

function failHabit(id) {
    const h = S.habits.find(x => x.id === id);
    if (!h) return;
    const cfg = DIFF[h.difficulty];
    const loss = cfg.hpLoss;
    h.streak = 0;

    S.hero.hp = Math.max(0, S.hero.hp - loss);
    addLog(`💔 Пропущено: ${h.title} (−${loss} HP)`);
    toast(`💔 <strong>${escHtml(h.title)}</strong> пропущено — −${loss} ❤️ HP`, "danger");

    if (S.hero.hp <= 0) {
        const xpPenalty = Math.floor(S.hero.xp * 0.3);
        S.hero.xp = Math.max(0, S.hero.xp - xpPenalty);
        S.hero.hp = S.hero.maxHp;
        toast(`💀 HP вичерпано! Штраф: −${xpPenalty} XP. HP відновлено.`, "danger", 5000);
        addLog(`💀 HP = 0! Штраф −${xpPenalty} XP, HP відновлено до ${S.hero.maxHp}`);
    }

    save();
    renderHero();
    renderHabits();
}

function deleteHabit(id) {
    const h = S.habits.find(x => x.id === id);
    S.habits = S.habits.filter(x => x.id !== id);
    if (h) addLog(`🗑 Видалено звичку: ${h.title}`);
    save();
    renderHabits();
    renderHero();
}

function addHabit(title, difficulty, stat) {
    const h = { id: S.nextHabitId++, title, difficulty, stat, streak: 0, completedToday: false, totalCompleted: 0 };
    S.habits.push(h);
    addLog(`➕ Нова звичка: ${title} (${DIFF[difficulty].label})`);
    save();
    renderHabits();
    renderHero();
    checkAchievements();
}

// ─────────────────────────────────────
// REWARDS RENDER
// ─────────────────────────────────────

function renderRewards() {
    const list = document.getElementById("rewards-list");
    if (S.rewards.length === 0) {
        list.innerHTML = '<div class="empty-state">Нагород поки немає 🎁<br>Додай перший приз!</div>';
        return;
    }
    list.innerHTML = S.rewards.map(r => {
        const affordable = S.hero.gold >= r.cost;
        return `
        <div class="card reward-card" data-id="${r.id}">
            <div class="card-info">
                <h4 class="card-title">${escHtml(r.title)}</h4>
                <div class="reward-cost">💰 ${r.cost} монет</div>
            </div>
            <div class="reward-actions">
                <button class="btn btn-buy ${affordable ? "" : "btn-buy-disabled"}"
                    data-action="buy" data-id="${r.id}">Придбати</button>
                <button class="action-btn btn-delete" data-action="delete-reward" data-id="${r.id}">🗑</button>
            </div>
        </div>`;
    }).join("");
}

function buyReward(id) {
    const r = S.rewards.find(x => x.id === id);
    if (!r) return;
    if (S.hero.gold < r.cost) {
        toast(`💰 Не вистачає монет! Потрібно ${r.cost}, є ${S.hero.gold}`, "warning");
        return;
    }
    S.hero.gold -= r.cost;
    S.hero.totalRewardsBought++;
    toast(`🎁 Насолоджуйся: <strong>${escHtml(r.title)}</strong>!`, "success");
    addLog(`🎁 Куплено нагороду: ${r.title} (−${r.cost} 💰)`);
    checkAchievements();
    save();
    renderHero();
    renderRewards();
}

function deleteReward(id) {
    const r = S.rewards.find(x => x.id === id);
    S.rewards = S.rewards.filter(x => x.id !== id);
    if (r) addLog(`🗑 Видалено нагороду: ${r.title}`);
    save();
    renderRewards();
}

function addReward(title, cost) {
    S.rewards.push({ id: S.nextRewardId++, title, cost: parseInt(cost, 10) });
    addLog(`➕ Нова нагорода: ${title} (${cost} 💰)`);
    save();
    renderRewards();
}

// ─────────────────────────────────────
// AVATAR SHOP
// ─────────────────────────────────────

function renderAvatarShop() {
    const grid = document.getElementById("avatar-grid");
    grid.innerHTML = AVATARS_DATA.map(av => {
        const owned    = S.hero.ownedAvatars.includes(av.emoji);
        const equipped = S.hero.avatar === av.emoji;
        const canAfford = S.hero.gold >= av.cost;
        let btn = "";
        if (equipped) {
            btn = `<button class="btn-equipped" disabled>✓ Обрано</button>`;
        } else if (owned) {
            btn = `<button class="btn-equip" data-avatar="${av.emoji}">Надягти</button>`;
        } else {
            btn = `<button class="btn-buy-avatar ${canAfford ? "" : "btn-buy-disabled"}"
                        data-avatar="${av.emoji}" data-cost="${av.cost}">💰 ${av.cost}</button>`;
        }
        return `
        <div class="avatar-card rarity-${av.rarity} ${equipped ? "avatar-equipped" : ""}">
            <div class="avatar-card-emoji">${av.emoji}</div>
            <div class="avatar-card-name">${av.name}</div>
            <div class="rarity-label-${av.rarity}">${rarityLabel(av.rarity)}</div>
            ${btn}
        </div>`;
    }).join("");
}

function rarityLabel(r) {
    return { common: "Звичайний", uncommon: "Незвичайний", rare: "Рідкісний", epic: "Епічний", legendary: "Легендарний" }[r] || r;
}

function buyAvatar(emoji, cost) {
    if (S.hero.gold < cost) { toast(`💰 Не вистачає монет! Потрібно ${cost}`, "warning"); return; }
    S.hero.gold -= cost;
    S.hero.ownedAvatars.push(emoji);
    S.hero.avatar = emoji;
    const av = AVATARS_DATA.find(a => a.emoji === emoji);
    toast(`🎭 Новий аватар <strong>${av ? av.name : ""}</strong> придбано та одягнено!`, "success");
    addLog(`🎭 Куплено аватар ${emoji} ${av ? av.name : ""} (−${cost} 💰)`);
    checkAchievements();
    save();
    renderHero();
    renderAvatarShop();
}

function equipAvatar(emoji) {
    S.hero.avatar = emoji;
    const av = AVATARS_DATA.find(a => a.emoji === emoji);
    toast(`🎭 Аватар ${av ? av.name : ""} обрано!`, "info");
    save();
    renderHero();
    renderAvatarShop();
}

// ─────────────────────────────────────
// LEVEL UP
// ─────────────────────────────────────

function checkLevelUp() {
    let leveled = false;
    while (S.hero.xp >= XP_FOR_LEVEL(S.hero.level)) {
        S.hero.xp    -= XP_FOR_LEVEL(S.hero.level);
        S.hero.level++;
        S.hero.maxHp += 10;
        S.hero.hp     = S.hero.maxHp;
        leveled = true;
    }
    if (leveled) {
        setEl("levelup-num", S.hero.level);
        const bonusEl = document.getElementById("levelup-bonuses");
        if (bonusEl) bonusEl.innerHTML = `<span>+10 ❤️ Max HP</span><span>HP відновлено!</span>`;
        openModal("levelup-modal");
        addLog(`⭐ РІВЕНЬ ВИЩЕ! Тепер ${S.hero.level}-й рівень. HP: ${S.hero.maxHp}`);
        checkAchievements();
    }
}

// ─────────────────────────────────────
// MODALS
// ─────────────────────────────────────

function openModal(id)  { document.getElementById(id).classList.remove("hidden"); }
function closeModal(id) { document.getElementById(id).classList.add("hidden"); }

// ─────────────────────────────────────
// TABS
// ─────────────────────────────────────

function switchTab(name) {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.add("hidden"));
    const btn = document.querySelector(`.tab-btn[data-tab="${name}"]`);
    const cnt = document.getElementById(`tab-${name}`);
    if (btn) btn.classList.add("active");
    if (cnt) cnt.classList.remove("hidden");
    if (name === "avatars")      renderAvatarShop();
    if (name === "achievements") renderAchievementsTab();
}

// ─────────────────────────────────────
// COUNTDOWN TIMER
// ─────────────────────────────────────

function updateTimer() {
    const now  = new Date();
    const next = new Date(); next.setHours(24, 0, 0, 0);
    const ms   = next - now;
    const hh   = String(Math.floor(ms / 3600000)).padStart(2, "0");
    const mm   = String(Math.floor((ms % 3600000) / 60000)).padStart(2, "0");
    const ss   = String(Math.floor((ms % 60000)   / 1000)).padStart(2, "0");
    setEl("reset-timer", `${hh}:${mm}:${ss}`);
}

// ─────────────────────────────────────
// UTILS
// ─────────────────────────────────────

function escHtml(str) {
    return String(str)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;")
        .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ─────────────────────────────────────
// EVENT LISTENERS
// ─────────────────────────────────────

function initEvents() {

    // ── Add habit modal
    document.getElementById("add-habit-btn").addEventListener("click", () => openModal("habit-modal"));
    document.getElementById("habit-modal-close").addEventListener("click",  () => closeModal("habit-modal"));
    document.getElementById("habit-modal-cancel").addEventListener("click", () => closeModal("habit-modal"));
    document.getElementById("habit-modal-save").addEventListener("click", () => {
        const title = document.getElementById("habit-title").value.trim();
        const diff  = document.getElementById("habit-difficulty").value;
        const stat  = document.getElementById("habit-stat").value;
        if (!title) { toast("⚠️ Введи назву звички!", "warning"); return; }
        addHabit(title, diff, stat);
        document.getElementById("habit-title").value = "";
        closeModal("habit-modal");
    });

    // ── Add reward modal
    document.getElementById("add-reward-btn").addEventListener("click", () => openModal("reward-modal"));
    document.getElementById("reward-modal-close").addEventListener("click",  () => closeModal("reward-modal"));
    document.getElementById("reward-modal-cancel").addEventListener("click", () => closeModal("reward-modal"));
    document.getElementById("reward-modal-save").addEventListener("click", () => {
        const title = document.getElementById("reward-title").value.trim();
        const cost  = document.getElementById("reward-cost").value;
        if (!title || !cost || parseInt(cost, 10) < 1) { toast("⚠️ Заповни всі поля коректно!", "warning"); return; }
        addReward(title, cost);
        document.getElementById("reward-title").value = "";
        document.getElementById("reward-cost").value  = "";
        closeModal("reward-modal");
    });

    // ── Level up modal
    document.getElementById("levelup-close").addEventListener("click", () => closeModal("levelup-modal"));

    // ── Habits list (delegation)
    document.getElementById("habits-list").addEventListener("click", e => {
        const btn = e.target.closest("[data-action]");
        if (!btn) return;
        const id     = parseInt(btn.dataset.id, 10);
        const action = btn.dataset.action;
        if      (action === "complete") completeHabit(id);
        else if (action === "fail")     failHabit(id);
        else if (action === "delete")   { if (confirm("Видалити цю звичку?")) deleteHabit(id); }
    });

    // ── Rewards list (delegation)
    document.getElementById("rewards-list").addEventListener("click", e => {
        const btn = e.target.closest("[data-action]");
        if (!btn) return;
        const id     = parseInt(btn.dataset.id, 10);
        const action = btn.dataset.action;
        if      (action === "buy")           buyReward(id);
        else if (action === "delete-reward") { if (confirm("Видалити цю нагороду?")) deleteReward(id); }
    });

    // ── Avatar grid (delegation)
    document.getElementById("avatar-grid").addEventListener("click", e => {
        const btn = e.target.closest("[data-avatar]");
        if (!btn) return;
        const emoji = btn.dataset.avatar;
        const cost  = parseInt(btn.dataset.cost || "0", 10);
        if (btn.classList.contains("btn-buy-avatar"))   buyAvatar(emoji, cost);
        else if (btn.classList.contains("btn-equip"))   equipAvatar(emoji);
    });

    // ── Tabs
    document.querySelectorAll(".tab-btn").forEach(btn =>
        btn.addEventListener("click", () => switchTab(btn.dataset.tab))
    );

    // ── Filters
    document.querySelectorAll(".filter-btn").forEach(btn =>
        btn.addEventListener("click", () => {
            document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            renderHabits(btn.dataset.filter);
        })
    );

    // ── Close modals on overlay click
    document.querySelectorAll(".modal-overlay").forEach(ov =>
        ov.addEventListener("click", e => { if (e.target === ov) ov.classList.add("hidden"); })
    );

    // ── Avatar shortcut (header)
    document.getElementById("open-avatar-shop").addEventListener("click", () => {
        switchTab("avatars");
        document.querySelector(".shop-section").scrollIntoView({ behavior: "smooth" });
    });

    // ── Clear log
    document.getElementById("clear-log-btn").addEventListener("click", () => {
        S.log = [];
        save();
        renderLog();
    });

    // ── Keyboard: Enter in inputs
    ["habit-title", "reward-title", "reward-cost"].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener("keydown", e => {
            if (e.key === "Enter") {
                if (id === "habit-title")  document.getElementById("habit-modal-save").click();
                if (id.startsWith("reward")) document.getElementById("reward-modal-save").click();
            }
        });
    });
}

// ─────────────────────────────────────
// INIT
// ─────────────────────────────────────

function init() {
    load();
    checkDailyReset();
    renderHero();
    renderHabits();
    renderRewards();
    renderLog();
    renderAchievementsMini();
    renderAchievementsTab();
    checkAchievements();
    initEvents();
    updateTimer();
    setInterval(updateTimer, 1000);

    // Greeting
    const hr = new Date().getHours();
    const greet = hr < 12 ? "🌅 Доброго ранку" : hr < 18 ? "☀️ Доброго дня" : "🌙 Доброго вечора";
    setTimeout(() => toast(`${greet}, <strong>${escHtml(S.hero.name)}</strong>! Готовий до нових звичок?`, "info", 3500), 600);
}

document.addEventListener("DOMContentLoaded", init);