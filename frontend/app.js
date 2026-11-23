// State
let currentQuery = "";
let currentCategory = "all";
let currentView = "search";
let viewMode = "grid";
let cnyGbpRate = 0.11;
let sessionStatus = "guest";
let currentPage = 1;
let lastSearchTotal = 0;
let isLoadingMore = false;

const itemStore = new Map();

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

// Delegated click handlers for cards and heart buttons
document.addEventListener("click", (e) => {
    const heartBtn = e.target.closest(".heart-btn");
    if (heartBtn) {
        e.stopPropagation();
        const itemId = heartBtn.dataset.itemId;
        if (itemId && itemStore.has(itemId)) {
            toggleSave(heartBtn, itemStore.get(itemId));
        }
        return;
    }
    const card = e.target.closest(".product-card");
    if (card) {
        const itemId = card.dataset.itemId;
        if (itemId && itemStore.has(itemId)) {
            openDrawer(itemStore.get(itemId));
        }
    }
});

// Init
checkSession();
loadSavedCount();

// ── Search ──

async function doSearch(append = false) {
    if (!currentQuery) return;

    if (!append) {
        currentPage = 1;
        results.innerHTML = Array(8).fill('<div class="skeleton rounded-xl h-72"></div>').join("");
        showStatusBar("Searching silently in background...", "#EFF6FF", "#1D4ED8");
        document.getElementById("loadMoreWrap").classList.add("hidden");
    }

    const params = new URLSearchParams({
        q: currentQuery,
        page: currentPage,
        include_sold: document.getElementById("filterSold").checked,
        sort: document.getElementById("sortSelect").value,
        category: currentCategory,
        filter_spam: document.getElementById("settingsSpamFilter")?.checked ?? true,
    });
    const minP = document.getElementById("filterMin").value;
    const maxP = document.getElementById("filterMax").value;
    if (minP) params.set("min_price", minP);
    if (maxP) params.set("max_price", maxP);
    if (document.getElementById("filterPersonal").checked) params.set("personal_only", "true");
    if (document.getElementById("filterFreeShip").checked) params.set("free_shipping", "true");
    if (document.getElementById("filterBrandNew").checked) params.set("brand_new", "true");

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

        if (!append) results.innerHTML = "";
        if (data.items.length === 0 && !append) {
            showStatusBar("No listings found. Try different keywords.", "#FEF3C7", "#92400E");
            document.getElementById("loadMoreWrap").classList.add("hidden");
            return;
        }

        const showGBP = document.getElementById("showGBP").checked;
        data.items.forEach(item => {
            itemStore.set(String(item.id), item);
            results.appendChild(createCard(item, showGBP));
        });

        lastSearchTotal = data.total || data.items.length;
        const loaded = results.children.length;
        const wrap = document.getElementById("loadMoreWrap");
        if (data.items.length >= 10 && loaded < lastSearchTotal) {
            wrap.classList.remove("hidden");
            document.getElementById("loadMoreInfo").textContent = `Showing ${loaded} of ${lastSearchTotal} results`;
        } else {
            wrap.classList.add("hidden");
        }

        const srcMap = { goofish_live: "Live Goofish", rapidapi: "RapidAPI", bing_search: "Web Index" };
        const srcLabel = srcMap[data.items[0]?.source] || "Web Index";
        showStatusBar(`Found ${loaded} listings via ${srcLabel}`, "#ECFDF5", "#065F46");
        if (data.rapidapi) updateRapidApiUI(data.rapidapi);
    } catch (err) {
        results.innerHTML = "";
        showStatusBar(`Error: ${err.message}`, "#FEF2F2", "#991B1B");
    }
}

// ── Card (safe DOM creation) ──

function createCard(item, showGBP) {
    const card = document.createElement("div");
    card.className = "product-card bg-white rounded-xl overflow-hidden cursor-pointer";
    card.dataset.itemId = String(item.id);

    const hasImage = item.images && item.images.length > 0 && item.images[0];
    const priceCNY = item.price != null ? `¥${formatNum(item.price)}` : "";
    const priceGBP = showGBP && item.price != null ? `~£${formatNum(item.price * cnyGbpRate)}` : "";
    const isSaved = item.saved ? "saved" : "";
    const srcClass = item.source === "goofish_live" ? "source-live" : item.source === "rapidapi" ? "source-rapidapi" : "source-index";
    const srcText = item.source === "goofish_live" ? "Live" : item.source === "rapidapi" ? "API" : "Index";

    // Image container
    const imgWrap = document.createElement("div");
    imgWrap.className = "relative";
    imgWrap.style.aspectRatio = "4/5";

    if (hasImage) {
        const img = document.createElement("img");
        img.src = item.images[0];
        img.alt = "";
        img.className = "w-full h-full object-cover bg-gray-100";
        img.loading = "lazy";
        img.addEventListener("error", () => {
            const fallback = document.createElement("div");
            fallback.className = "w-full h-full bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center p-4";
            const p = document.createElement("p");
            p.className = "text-xs text-gray-400 text-center line-clamp-2";
            p.textContent = item.title || "";
            fallback.appendChild(p);
            imgWrap.replaceChildren(fallback);
            imgWrap.appendChild(heartBtn);
            if (dealBadge) imgWrap.appendChild(dealBadge);
        });
        imgWrap.appendChild(img);
    } else {
        const fallback = document.createElement("div");
        fallback.className = "w-full h-full bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center p-6";
        const p = document.createElement("p");
        p.className = "text-sm text-gray-400 text-center line-clamp-2";
        p.textContent = item.description || item.title || "No preview";
        fallback.appendChild(p);
        imgWrap.appendChild(fallback);
    }

    // Heart button
    const heartBtn = document.createElement("button");
    heartBtn.className = `heart-btn ${isSaved} absolute top-2.5 right-2.5 w-9 h-9 rounded-full bg-white shadow-sm flex items-center justify-center hover:scale-110 transition-transform`;
    heartBtn.dataset.itemId = String(item.id);
    heartBtn.innerHTML = `<svg class="w-5 h-5" fill="${item.saved ? 'currentColor' : 'none'}" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/></svg>`;
    imgWrap.appendChild(heartBtn);

    // Deal badge
    let dealBadge = null;
    if (item.deal_score && item.deal_score >= 20) {
        dealBadge = document.createElement("span");
        dealBadge.className = "deal-badge absolute top-2.5 left-2.5";
        dealBadge.textContent = `${item.deal_score}% off`;
        imgWrap.appendChild(dealBadge);
    }

    card.appendChild(imgWrap);

    // Info section
    const info = document.createElement("div");
    info.className = "p-3";

    const title = document.createElement("h3");
    title.className = "text-sm font-medium text-gray-800 line-clamp-2 mb-1.5";
    title.textContent = item.title || "";
    info.appendChild(title);

    const priceRow = document.createElement("div");
    priceRow.className = "flex items-baseline gap-2 mb-1";
    if (priceCNY) {
        const cnySpan = document.createElement("span");
        cnySpan.className = "text-base font-bold text-gray-900";
        cnySpan.textContent = priceCNY;
        priceRow.appendChild(cnySpan);
    } else {
        const na = document.createElement("span");
        na.className = "text-sm text-gray-400";
        na.textContent = "Price N/A";
        priceRow.appendChild(na);
    }
    if (priceGBP) {
        const gbpSpan = document.createElement("span");
        gbpSpan.className = "text-xs text-gray-400";
        gbpSpan.textContent = priceGBP;
        priceRow.appendChild(gbpSpan);
    }
    info.appendChild(priceRow);

    // Seller row
    if (item.seller) {
        const sellerRow = document.createElement("div");
        sellerRow.className = "flex items-center gap-1.5 mb-1";
        const sellerName = document.createElement("span");
        sellerName.className = "seller-badge truncate";
        sellerName.textContent = `@${item.seller}`;
        sellerRow.appendChild(sellerName);
        if (item.condition) {
            const condBadge = document.createElement("span");
            condBadge.className = "personal-badge";
            condBadge.textContent = item.condition;
            sellerRow.appendChild(condBadge);
        }
        info.appendChild(sellerRow);
    }

    // Description preview
    const desc = item.description || "";
    if (desc) {
        const descP = document.createElement("p");
        descP.className = "desc-preview line-clamp-2 mb-1";
        descP.textContent = desc;
        info.appendChild(descP);
    }

    const meta = document.createElement("div");
    meta.className = "flex items-center justify-between text-xs text-gray-400";
    const loc = document.createElement("span");
    loc.textContent = item.location || "";
    meta.appendChild(loc);
    const srcSpan = document.createElement("span");
    srcSpan.className = `px-1.5 py-0.5 rounded text-xs font-medium ${srcClass}`;
    srcSpan.textContent = srcText;
    meta.appendChild(srcSpan);
    info.appendChild(meta);

    card.appendChild(info);
    return card;
}

// ── Drawer ──

function openDrawer(item) {
    const container = document.getElementById("drawerContent");
    container.innerHTML = "";

    const showGBP = document.getElementById("showGBP").checked;
    const priceCNY = item.price != null ? `¥${formatNum(item.price)}` : "Price N/A";
    const priceGBP = showGBP && item.price != null ? ` · ~£${formatNum(item.price * cnyGbpRate)}` : "";
    const hasImage = item.images && item.images.length > 0 && item.images[0];

    if (hasImage) {
        const img = document.createElement("img");
        img.src = item.images[0];
        img.className = "w-full rounded-xl mb-4 bg-gray-100";
        img.loading = "lazy";
        container.appendChild(img);
    }

    const h2 = document.createElement("h2");
    h2.className = "text-lg font-bold text-gray-900 mb-2";
    h2.textContent = item.title || "";
    container.appendChild(h2);

    const price = document.createElement("div");
    price.className = "text-2xl font-bold text-gray-900 mb-3";
    price.textContent = priceCNY + priceGBP;
    container.appendChild(price);

    if (item.deal_score && item.deal_score >= 20) {
        const badge = document.createElement("span");
        badge.className = "deal-badge mb-3 inline-block";
        badge.textContent = `${item.deal_score}% below median`;
        container.appendChild(badge);
    }

    const details = document.createElement("div");
    details.className = "space-y-2 text-sm text-gray-600 mb-4";
    if (item.seller) {
        const d = document.createElement("div");
        d.innerHTML = '<span class="font-medium">Seller:</span> ';
        d.appendChild(document.createTextNode(item.seller));
        details.appendChild(d);
    }
    if (item.location) {
        const d = document.createElement("div");
        d.innerHTML = '<span class="font-medium">Location:</span> ';
        d.appendChild(document.createTextNode(item.location));
        details.appendChild(d);
    }
    if (item.condition) {
        const d = document.createElement("div");
        d.innerHTML = '<span class="font-medium">Condition:</span> ';
        d.appendChild(document.createTextNode(item.condition));
        details.appendChild(d);
    }
    if (item.source) {
        const d = document.createElement("div");
        d.innerHTML = '<span class="font-medium">Source:</span> ';
        const srcNames = { goofish_live: "Live Goofish", rapidapi: "RapidAPI Goofish", bing_search: "Bing Web Index" };
        d.appendChild(document.createTextNode(srcNames[item.source] || "Bing Web Index"));
        details.appendChild(d);
    }
    if (item.specs && typeof item.specs === "object") {
        for (const [k, v] of Object.entries(item.specs)) {
            const d = document.createElement("div");
            const label = document.createElement("span");
            label.className = "font-medium";
            label.textContent = k.replace(/_/g, " ") + ": ";
            d.appendChild(label);
            d.appendChild(document.createTextNode(String(v)));
            details.appendChild(d);
        }
    }
    container.appendChild(details);

    if (item.description) {
        const desc = document.createElement("div");
        desc.className = "text-sm text-gray-500 mb-4 p-3 bg-gray-50 rounded-lg whitespace-pre-line";
        desc.textContent = item.description;
        container.appendChild(desc);
    }

    const link = document.createElement("a");
    link.href = item.url || "#";
    link.target = "_blank";
    link.rel = "noopener";
    link.className = "block w-full text-center py-3 rounded-xl font-semibold text-white";
    link.style.background = "var(--primary)";
    link.textContent = "Open on Goofish ↗";
    container.appendChild(link);

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
        await fetch(`/api/deals/${item.id}`, { method: "DELETE", headers: { "X-Requested-With": "XMLHttpRequest" } });
        btn.classList.remove("saved");
        btn.querySelector("svg").setAttribute("fill", "none");
    } else {
        await fetch("/api/deals/save", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest" },
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
                itemStore.set(String(item.id), item);
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

    const connectedDiv = document.getElementById("accountConnected");
    const actionsDiv = document.getElementById("accountActions");
    if (sessionStatus === "connected") {
        actionsDiv?.classList.add("hidden");
        connectedDiv?.classList.remove("hidden");
    } else {
        actionsDiv?.classList.remove("hidden");
        connectedDiv?.classList.add("hidden");
    }

    const lockBanner = document.getElementById("liveLockBanner");
    const liveConnected = document.getElementById("liveConnected");
    if (sessionStatus === "connected") {
        lockBanner?.classList.add("hidden");
        liveConnected?.classList.remove("hidden");
    } else {
        lockBanner?.classList.remove("hidden");
        liveConnected?.classList.add("hidden");
    }
}

async function startLogin() {
    const btn = document.getElementById("connectBtn");
    btn.disabled = true;
    btn.innerHTML = '<svg class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg> Opening login window...';

    try {
        const res = await fetch("/api/session/login", { method: "POST", headers: { "X-Requested-With": "XMLHttpRequest" } });
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
    await fetch("/api/session/logout", { method: "POST", headers: { "X-Requested-With": "XMLHttpRequest" } });
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

document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDrawer();
});

// GBP toggle re-renders
document.getElementById("showGBP").addEventListener("change", () => {
    if (currentQuery && results.children.length > 0) doSearch();
});

// ── RapidAPI Settings ──

function updateRapidApiUI(status) {
    const badge = document.getElementById("rapidapiBadge");
    const calls = document.getElementById("rapidapiCallsToday");
    if (!badge) return;
    if (status.active) {
        badge.textContent = "Active";
        badge.className = "text-xs font-medium px-2 py-0.5 rounded-full";
        badge.style.background = "rgba(9,177,186,0.1)";
        badge.style.color = "var(--primary)";
    } else {
        badge.textContent = "Not Set";
        badge.className = "text-xs font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-500";
        badge.style.background = "";
        badge.style.color = "";
    }
    if (calls) calls.textContent = status.calls_today ?? 0;
    const pageSel = document.getElementById("settingsPageSize");
    if (pageSel && status.page_size) pageSel.value = String(status.page_size);
}

async function loadRapidApiStatus() {
    try {
        const res = await fetch("/api/rapidapi/status");
        if (res.ok) updateRapidApiUI(await res.json());
    } catch {}
}

async function loadMore() {
    if (isLoadingMore) return;
    isLoadingMore = true;
    const btn = document.getElementById("loadMoreBtn");
    btn.textContent = "Loading...";
    btn.disabled = true;
    currentPage++;
    try {
        await doSearch(true);
    } finally {
        isLoadingMore = false;
        btn.textContent = "Load More Items";
        btn.disabled = false;
    }
}

async function saveRapidApiKey() {
    const input = document.getElementById("settingsRapidApiKey");
    const key = input.value.trim();
    try {
        const res = await fetch("/api/rapidapi/settings", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest" },
            body: JSON.stringify({ key }),
        });
        if (res.ok) {
            const status = await res.json();
            updateRapidApiUI(status);
            input.value = "";
            input.placeholder = status.active ? "Key saved (hidden)" : "Paste your RapidAPI key...";
        }
    } catch {}
}

async function saveRapidApiPageSize() {
    const size = parseInt(document.getElementById("settingsPageSize").value, 10);
    try {
        await fetch("/api/rapidapi/settings", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest" },
            body: JSON.stringify({ page_size: size }),
        });
    } catch {}
}

loadRapidApiStatus();
