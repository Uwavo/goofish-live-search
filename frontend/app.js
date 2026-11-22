// State
let currentQuery = "";
let currentCategory = "all";
let currentView = "search";
let viewMode = "grid";
let cnyGbpRate = 0.11;
let sessionStatus = "guest";

// Elements
const searchInput = document.getElementById("searchInput");
const results = document.getElementById("results");
const statusBar = document.getElementById("statusBar");
const translateBadge = document.getElementById("translateBadge");

// Search on Enter
searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        currentQuery = searchInput.value.trim();
        if (currentQuery) {
            showView("search");
            doSearch();
        }
    }
});

// Category tabs
document.getElementById("categoryTabs").addEventListener("click", (e) => {
    const tab = e.target.closest(".cat-tab");
    if (!tab) return;
    document.querySelectorAll(".cat-tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    currentCategory = tab.dataset.cat;
    if (currentQuery) doSearch();
});

// Init
checkSession();
loadSavedCount();

// ── Search ──

async function doSearch() {
    if (!currentQuery) return;

    results.innerHTML = Array(8).fill('<div class="skeleton rounded-xl h-72"></div>').join("");
    showStatusBar("Searching silently in background...", "#EFF6FF", "#1D4ED8");

    const params = new URLSearchParams({
        q: currentQuery,
        page: 1,
        include_sold: document.getElementById("filterSold").checked,
        sort: document.getElementById("sortSelect").value,
        category: currentCategory,
        filter_spam: document.getElementById("settingsSpamFilter")?.checked ?? true,
    });
    const minP = document.getElementById("filterMin").value;
    const maxP = document.getElementById("filterMax").value;
    if (minP) params.set("min_price", minP);
    if (maxP) params.set("max_price", maxP);

    try {
        const res = await fetch(`/api/search?${params}`);
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP ${res.status}`);
        }
        const data = await res.json();
        sessionStatus = data.session || sessionStatus;
        if (data.rate) cnyGbpRate = data.rate;
        updateSessionUI();

        if (data.query_translated) {
            translateBadge.textContent = `"${currentQuery}" → "${data.query_translated}"`;
            translateBadge.classList.remove("hidden");
        } else {
            translateBadge.classList.add("hidden");
        }

        results.innerHTML = "";
        if (data.items.length === 0) {
            showStatusBar("No listings found. Try different keywords.", "#FEF3C7", "#92400E");
            return;
        }

        const showGBP = document.getElementById("showGBP").checked;
        data.items.forEach(item => results.appendChild(createCard(item, showGBP)));

        const srcLabel = data.items[0]?.source === "goofish_live" ? "Live Goofish" : "Web Index";
        showStatusBar(`Found ${data.total} listings via ${srcLabel}`, "#ECFDF5", "#065F46");
    } catch (err) {
        results.innerHTML = "";
        showStatusBar(`Error: ${err.message}`, "#FEF2F2", "#991B1B");
    }
}

// ── Card ──

function createCard(item, showGBP) {
    const card = document.createElement("div");
    card.className = "product-card bg-white rounded-xl overflow-hidden cursor-pointer";
    card.onclick = () => openDrawer(item);

    const hasImage = item.images && item.images.length > 0 && item.images[0];
    const priceCNY = item.price != null ? `¥${formatNum(item.price)}` : "";
    const priceGBP = showGBP && item.price != null ? `~£${formatNum(item.price * cnyGbpRate)}` : "";
    const isSaved = item.saved ? "saved" : "";
    const srcClass = item.source === "goofish_live" ? "source-live" : "source-index";
    const srcText = item.source === "goofish_live" ? "Live" : "Index";

    card.innerHTML = `
        <div class="relative" style="aspect-ratio: 4/5;">
            ${hasImage
                ? `<img src="${esc(item.images[0])}" alt="" class="w-full h-full object-cover bg-gray-100" loading="lazy"
                    onerror="this.parentElement.innerHTML='<div class=\\'w-full h-full bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center p-4\\'><p class=\\'text-xs text-gray-400 text-center line-clamp-2\\'>${esc(item.title)}</p></div>'">`
                : `<div class="w-full h-full bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center p-6">
                    <p class="text-sm text-gray-400 text-center line-clamp-2">${esc(item.description || item.title || "No preview")}</p>
                </div>`}
            <button class="heart-btn ${isSaved} absolute top-2.5 right-2.5 w-9 h-9 rounded-full bg-white shadow-sm flex items-center justify-center hover:scale-110 transition-transform"
                onclick="event.stopPropagation(); toggleSave(this, ${escAttr(JSON.stringify(item))})">
                <svg class="w-5 h-5" fill="${item.saved ? 'currentColor' : 'none'}" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/></svg>
            </button>
            ${item.deal_score && item.deal_score >= 20 ? `<span class="deal-badge absolute top-2.5 left-2.5">${item.deal_score}% off</span>` : ""}
        </div>
        <div class="p-3">
            <h3 class="text-sm font-medium text-gray-800 line-clamp-2 mb-1.5">${esc(item.title)}</h3>
            <div class="flex items-baseline gap-2 mb-1">
                ${priceCNY ? `<span class="text-base font-bold text-gray-900">${priceCNY}</span>` : `<span class="text-sm text-gray-400">Price N/A</span>`}
                ${priceGBP ? `<span class="text-xs text-gray-400">${priceGBP}</span>` : ""}
            </div>
            <div class="flex items-center justify-between text-xs text-gray-400">
                <span>${esc(item.location || "")}</span>
                <span class="px-1.5 py-0.5 rounded text-xs font-medium ${srcClass}">${srcText}</span>
            </div>
        </div>
    `;
    return card;
}

// ── Drawer ──

function openDrawer(item) {
    const showGBP = document.getElementById("showGBP").checked;
    const priceCNY = item.price != null ? `¥${formatNum(item.price)}` : "Price N/A";
    const priceGBP = showGBP && item.price != null ? ` · ~£${formatNum(item.price * cnyGbpRate)}` : "";
    const hasImage = item.images && item.images.length > 0 && item.images[0];

    document.getElementById("drawerContent").innerHTML = `
        ${hasImage ? `<img src="${esc(item.images[0])}" class="w-full rounded-xl mb-4 bg-gray-100" loading="lazy">` : ""}
        <h2 class="text-lg font-bold text-gray-900 mb-2">${esc(item.title)}</h2>
        <div class="text-2xl font-bold text-gray-900 mb-3">${priceCNY}${priceGBP}</div>
        ${item.deal_score && item.deal_score >= 20 ? `<span class="deal-badge mb-3 inline-block">${item.deal_score}% below median</span>` : ""}
        <div class="space-y-2 text-sm text-gray-600 mb-4">
            ${item.seller ? `<div><span class="font-medium">Seller:</span> ${esc(item.seller)}</div>` : ""}
            ${item.location ? `<div><span class="font-medium">Location:</span> ${esc(item.location)}</div>` : ""}
            ${item.source ? `<div><span class="font-medium">Source:</span> ${item.source === "goofish_live" ? "Live Goofish" : "Bing Web Index"}</div>` : ""}
        </div>
        ${item.description ? `<div class="text-sm text-gray-500 mb-4 p-3 bg-gray-50 rounded-lg">${esc(item.description)}</div>` : ""}
        <a href="${esc(item.url)}" target="_blank" rel="noopener"
            class="block w-full text-center py-3 rounded-xl font-semibold text-white" style="background: var(--primary);">
            Open on Goofish ↗
        </a>
    `;
    document.getElementById("drawer").classList.add("open");
    document.getElementById("drawerOverlay").classList.add("open");
}

function closeDrawer() {
    document.getElementById("drawer").classList.remove("open");
    document.getElementById("drawerOverlay").classList.remove("open");
}

// ── Saved Deals ──

async function toggleSave(btn, item) {
    const isSaved = btn.classList.contains("saved");
    if (isSaved) {
        await fetch(`/api/deals/${item.id}`, { method: "DELETE" });
        btn.classList.remove("saved");
        btn.querySelector("svg").setAttribute("fill", "none");
    } else {
        await fetch("/api/deals/save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ item }),
        });
        btn.classList.add("saved");
        btn.querySelector("svg").setAttribute("fill", "currentColor");
    }
    loadSavedCount();
}

async function loadSavedCount() {
    try {
        const res = await fetch("/api/deals");
        const data = await res.json();
        const badge = document.getElementById("savedBadge");
        if (data.total > 0) {
            badge.textContent = data.total;
            badge.classList.remove("hidden");
        } else {
            badge.classList.add("hidden");
        }
    } catch {}
}

async function loadSavedDeals() {
    const container = document.getElementById("savedResults");
    const empty = document.getElementById("savedEmpty");
    try {
        const res = await fetch("/api/deals");
        const data = await res.json();
        container.innerHTML = "";
        if (data.items.length === 0) {
            empty.classList.remove("hidden");
        } else {
            empty.classList.add("hidden");
            const showGBP = document.getElementById("showGBP").checked;
            data.items.forEach(item => {
                item.saved = true;
                container.appendChild(createCard(item, showGBP));
            });
        }
    } catch {}
}

// ── Session ──

async function checkSession() {
    try {
        const res = await fetch("/api/session/status");
        const data = await res.json();
        sessionStatus = data.status;
        updateSessionUI();
    } catch {}
}

function updateSessionUI() {
    const labels = { guest: "Guest Mode", connected: "Full Access", expired: "Session Expired" };
    document.getElementById("headerStatus").textContent = labels[sessionStatus] || "Guest Mode";
    document.getElementById("headerDot").className = `status-dot ${sessionStatus}`;
    document.getElementById("sidebarDot").className = `status-dot ${sessionStatus}`;

    const connectBtn = document.getElementById("connectBtn");
    const connectedDiv = document.getElementById("accountConnected");
    const actionsDiv = document.getElementById("accountActions");
    if (sessionStatus === "connected") {
        actionsDiv?.classList.add("hidden");
        connectedDiv?.classList.remove("hidden");
    } else {
        actionsDiv?.classList.remove("hidden");
        connectedDiv?.classList.add("hidden");
    }

    // Update live view
    if (sessionStatus === "connected") {
        document.getElementById("liveDesc").textContent = "Your Alipay account is connected. Searches use real-time Goofish data.";
        document.getElementById("liveConnectBtn").textContent = "Search now →";
        document.getElementById("liveConnectBtn").onclick = () => { showView("search"); searchInput.focus(); };
    }
}

async function startLogin() {
    const btn = document.getElementById("connectBtn");
    btn.disabled = true;
    btn.innerHTML = '<svg class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg> Opening login window...';

    try {
        const res = await fetch("/api/session/login", { method: "POST" });
        const data = await res.json();
        if (data.success) {
            sessionStatus = "connected";
            updateSessionUI();
        } else {
            alert(data.error || "Login failed");
        }
    } catch (e) {
        alert("Login error: " + e.message);
    }
    btn.disabled = false;
    btn.innerHTML = '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z"/></svg> Connect via Alipay QR';
}

async function doLogout() {
    await fetch("/api/session/logout", { method: "POST" });
    sessionStatus = "guest";
    updateSessionUI();
}

// ── Views ──

function showView(view) {
    currentView = view;
    ["search", "live", "saved", "settings", "account"].forEach(v => {
        document.getElementById(`view-${v}`).classList.toggle("hidden", v !== view);
    });
    document.querySelectorAll(".sidebar-link").forEach(l => {
        l.classList.toggle("active", l.dataset.view === view);
    });
    if (view === "saved") loadSavedDeals();
}

function setView(mode) {
    viewMode = mode;
    document.getElementById("gridBtn").classList.toggle("active", mode === "grid");
    document.getElementById("listBtn").classList.toggle("active", mode === "list");
    if (mode === "list") {
        results.className = "space-y-3";
    } else {
        results.className = "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4";
    }
}

// ── Helpers ──

function showStatusBar(msg, bg, color) {
    statusBar.style.background = bg;
    statusBar.style.color = color;
    statusBar.textContent = msg;
    statusBar.classList.remove("hidden");
}

function formatNum(n) {
    return n.toLocaleString("en", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function esc(str) {
    const d = document.createElement("div");
    d.textContent = str || "";
    return d.innerHTML;
}

function escAttr(str) {
    return str.replace(/'/g, "\\'").replace(/"/g, "&quot;");
}

document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDrawer();
});

// GBP toggle re-renders
document.getElementById("showGBP").addEventListener("change", () => {
    if (currentQuery && results.children.length > 0) doSearch();
});
