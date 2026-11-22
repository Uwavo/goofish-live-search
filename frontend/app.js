let currentPage = 1;
let currentQuery = "";

const form = document.getElementById("searchForm");
const resultsDiv = document.getElementById("results");
const statusDiv = document.getElementById("status");
const loadMoreDiv = document.getElementById("loadMore");
const modal = document.getElementById("imageModal");
const modalImages = document.getElementById("modalImages");

form.addEventListener("submit", (e) => {
    e.preventDefault();
    currentPage = 1;
    currentQuery = document.getElementById("queryInput").value.trim();
    if (currentQuery) fetchResults(false);
});

async function fetchResults(append) {
    const minPrice = document.getElementById("minPrice").value;
    const maxPrice = document.getElementById("maxPrice").value;
    const sort = document.getElementById("sortOrder").value;

    if (!append) {
        resultsDiv.innerHTML = Array(8).fill('<div class="skeleton rounded-xl h-72"></div>').join("");
    }

    showStatus("Searching Goofish...", "bg-blue-100 text-blue-800");

    const params = new URLSearchParams({ q: currentQuery, sort, page: currentPage });
    if (minPrice) params.set("min_price", minPrice);
    if (maxPrice) params.set("max_price", maxPrice);

    try {
        const res = await fetch(`/api/search?${params}`);
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP ${res.status}`);
        }
        const data = await res.json();

        if (!append) resultsDiv.innerHTML = "";

        if (data.items.length === 0 && !append) {
            showStatus("No results found.", "bg-yellow-100 text-yellow-800");
            loadMoreDiv.classList.add("hidden");
            return;
        }

        data.items.forEach((item) => resultsDiv.appendChild(createCard(item)));
        loadMoreDiv.classList.toggle("hidden", data.items.length < 10);
        if (data.source === "feed") {
            showStatus(`Showing ${data.total} recommended items — Goofish requires login for search-specific results.`, "bg-yellow-100 text-yellow-800");
        } else {
            showStatus(`Found ${data.total} items (page ${data.page})`, "bg-green-100 text-green-800");
        }
    } catch (err) {
        if (!append) resultsDiv.innerHTML = "";
        showStatus(`Error: ${err.message}`, "bg-red-100 text-red-800");
        loadMoreDiv.classList.add("hidden");
    }
}

function loadNextPage() {
    currentPage++;
    fetchResults(true);
}

function createCard(item) {
    const card = document.createElement("div");
    card.className = "card bg-white rounded-xl shadow-sm overflow-hidden border border-gray-100 cursor-pointer";

    const thumb = item.images && item.images[0] ? item.images[0] : "";
    const price = item.price != null ? `¥${item.price.toFixed(2)}` : "N/A";
    const badgeClass = item.status === "sold" ? "badge-sold" : "badge-sale";
    const badgeText = item.status === "sold" ? "Sold" : "On Sale";

    card.innerHTML = `
        <div class="relative">
            ${thumb ? `<img src="${escapeHtml(thumb)}" alt="" class="w-full h-48 object-cover bg-gray-100" loading="lazy"
                onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 1 1%22><rect fill=%22%23eee%22 width=%221%22 height=%221%22/></svg>'"
                onclick="showImages(${escapeAttr(JSON.stringify(item.images || []))}); event.stopPropagation()">` :
                `<div class="w-full h-48 bg-gray-100 flex items-center justify-center text-gray-400">No Image</div>`}
            <span class="absolute top-2 right-2 ${badgeClass} text-white text-xs px-2 py-1 rounded-full">${badgeText}</span>
        </div>
        <div class="p-3">
            <h3 class="text-sm font-medium text-gray-800 line-clamp-2 mb-2" style="-webkit-line-clamp:2; display:-webkit-box; -webkit-box-orient:vertical; overflow:hidden;">${escapeHtml(item.title)}</h3>
            <p class="text-lg font-bold text-red-500 mb-1">${price}</p>
            <p class="text-xs text-gray-500 mb-2">${escapeHtml(item.location || "")} · ${escapeHtml(item.seller || "")}</p>
            <a href="${escapeHtml(item.url)}" target="_blank" rel="noopener"
               class="block text-center text-sm bg-orange-50 text-orange-600 py-1.5 rounded-lg hover:bg-orange-100 font-medium"
               onclick="event.stopPropagation()">View on Goofish ↗</a>
        </div>
    `;
    return card;
}

function showImages(images) {
    modalImages.innerHTML = images.map(
        (src) => `<img src="${escapeHtml(src)}" class="max-w-full rounded" loading="lazy">`
    ).join("");
    modal.classList.remove("hidden");
}

function closeModal(e) {
    if (!e || e.target === modal) modal.classList.add("hidden");
}

function showStatus(msg, cls) {
    statusDiv.className = `mb-4 p-3 rounded-lg text-center ${cls}`;
    statusDiv.textContent = msg;
    statusDiv.classList.remove("hidden");
}

function escapeHtml(str) {
    const d = document.createElement("div");
    d.textContent = str || "";
    return d.innerHTML;
}

function escapeAttr(str) {
    return str.replace(/'/g, "\\'").replace(/"/g, "&quot;");
}

document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
});
