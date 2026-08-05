(function () {
  /* ---- Generic dropdown panel (category menu, account menu) ---- */
  function setupDropdown(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const button = container.querySelector("button");
    const panel = container.querySelector(".category-panel, .account-panel, .notification-panel");
    if (!button || !panel) return;

    function open() {
      panel.classList.remove("invisible", "opacity-0");
      panel.classList.add("translate-y-0");
      button.setAttribute("aria-expanded", "true");
    }
    function close() {
      panel.classList.add("invisible", "opacity-0");
      button.setAttribute("aria-expanded", "false");
    }
    function isOpen() {
      return !panel.classList.contains("invisible");
    }

    button.addEventListener("click", (event) => {
      event.stopPropagation();
      isOpen() ? close() : open();
    });
    document.addEventListener("click", (event) => {
      if (!container.contains(event.target)) close();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") close();
    });
  }

  setupDropdown("category-menu");
  setupDropdown("account-menu");
  setupDropdown("notification-menu");

  /* ---- Notifications dropdown ---- */
  const notificationBadge = document.getElementById("notification-badge-count");
  const notificationList = document.getElementById("notification-dropdown-list");

  function timeAgo(isoDate) {
    const seconds = Math.floor((Date.now() - new Date(isoDate).getTime()) / 1000);
    if (seconds < 60) return "just now";
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  }

  async function loadNotificationDropdown() {
    if (!notificationBadge || !notificationList) return;
    try {
      const [countData, listData] = await Promise.all([
        Storefront.apiFetch("/notifications/unread_count/"),
        Storefront.apiFetch("/notifications/?page_size=6"),
      ]);

      if (countData.count > 0) {
        notificationBadge.textContent = countData.count > 9 ? "9+" : countData.count;
        notificationBadge.classList.remove("hidden");
        notificationBadge.classList.add("flex");
      }

      notificationList.innerHTML = "";
      const items = listData.results || [];
      if (items.length === 0) {
        notificationList.innerHTML = '<p class="p-4 text-sm text-black/40">No notifications yet.</p>';
        return;
      }
      items.forEach((n) => {
        const row = document.createElement(n.link ? "a" : "div");
        if (n.link) row.href = n.link;
        row.className = "flex items-start gap-2 px-4 py-3 text-sm hover:bg-brand/5" + (n.is_read ? "" : " bg-brand/[.03]");
        row.innerHTML = `
          ${n.is_read ? "" : '<span class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand"></span>'}
          <span class="flex-1">
            <span class="block font-medium">${n.title}</span>
            <span class="block text-black/50">${n.message}</span>
            <span class="block text-xs text-black/30">${timeAgo(n.created_at)}</span>
          </span>`;
        notificationList.appendChild(row);
      });
    } catch (err) {
      notificationList.innerHTML = '<p class="p-4 text-sm text-black/40">Could not load notifications.</p>';
    }
  }

  if (window.IS_AUTHENTICATED) loadNotificationDropdown();

  /* ---- Mobile drawer ---- */
  const drawer = document.getElementById("mobile-drawer");
  const backdrop = document.getElementById("mobile-drawer-backdrop");
  const openBtn = document.getElementById("mobile-menu-btn");
  const closeBtn = document.getElementById("mobile-drawer-close");

  function openDrawer() {
    drawer.classList.remove("-translate-x-full");
    backdrop.classList.remove("invisible", "opacity-0");
    openBtn.setAttribute("aria-expanded", "true");
  }
  function closeDrawer() {
    drawer.classList.add("-translate-x-full");
    backdrop.classList.add("invisible", "opacity-0");
    openBtn.setAttribute("aria-expanded", "false");
  }
  if (openBtn) openBtn.addEventListener("click", openDrawer);
  if (closeBtn) closeBtn.addEventListener("click", closeDrawer);
  if (backdrop) backdrop.addEventListener("click", closeDrawer);

  /* ---- Search autocomplete ---- */
  const searchBox = document.getElementById("search-box");
  const searchInput = document.getElementById("site-search");
  const suggestionsPanel = document.getElementById("search-suggestions");
  let debounceTimer = null;
  let latestQuery = "";

  function closeSuggestions() {
    suggestionsPanel.classList.add("invisible", "opacity-0");
    suggestionsPanel.innerHTML = "";
  }

  function fmtPrice(amount) {
    return "Rs " + Math.round(amount).toLocaleString("en-PK");
  }

  async function runSearch(query) {
    latestQuery = query;
    if (!query.trim()) {
      closeSuggestions();
      return;
    }
    try {
      const data = await Storefront.apiFetch(
        "/catalog/products/search/?q=" + encodeURIComponent(query) + "&page_size=5"
      );
      if (query !== latestQuery) return; // a newer keystroke already superseded this response

      suggestionsPanel.innerHTML = "";
      if (data.results.length === 0) {
        const empty = document.createElement("p");
        empty.className = "px-4 py-3 text-sm text-black/40";
        empty.textContent = "No products found.";
        suggestionsPanel.appendChild(empty);
      } else {
        data.results.forEach((product) => {
          const link = document.createElement("a");
          link.href = "/products/" + product.id + "/";
          link.className = "flex items-center justify-between gap-3 px-4 py-2.5 text-sm hover:bg-brand/5";
          link.innerHTML = `<span class="truncate">${product.name}</span><span class="shrink-0 font-medium text-black/60">${fmtPrice(product.price)}</span>`;
          suggestionsPanel.appendChild(link);
        });
      }

      const seeAll = document.createElement("a");
      seeAll.href = window.PRODUCT_LIST_URL + "?q=" + encodeURIComponent(query);
      seeAll.className = "block border-t border-black/5 px-4 py-2.5 text-sm font-medium text-brand hover:bg-brand/5";
      seeAll.textContent = `See all results for "${query}"`;
      suggestionsPanel.appendChild(seeAll);

      suggestionsPanel.classList.remove("invisible", "opacity-0");
    } catch (err) {
      closeSuggestions();
    }
  }

  if (searchInput) {
    searchInput.addEventListener("input", (event) => {
      clearTimeout(debounceTimer);
      const query = event.target.value;
      debounceTimer = setTimeout(() => runSearch(query), 250);
    });
    searchInput.addEventListener("focus", () => {
      if (searchInput.value.trim()) runSearch(searchInput.value);
    });
  }
  document.addEventListener("click", (event) => {
    if (searchBox && !searchBox.contains(event.target)) closeSuggestions();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeSuggestions();
  });

  /* ---- Newsletter subscribe (footer + any homepage promo forms) ---- */
  document.querySelectorAll(".newsletter-form").forEach((newsletterForm) => {
    newsletterForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const messageEl = newsletterForm.querySelector(".newsletter-message");
      const emailInput = newsletterForm.querySelector("input[name=email]");
      try {
        await Storefront.apiFetch("/marketing/newsletter/subscribe/", {
          method: "POST",
          body: JSON.stringify({ email: emailInput.value }),
        });
        messageEl.textContent = "Subscribed! Thanks for joining.";
        messageEl.className = "newsletter-message text-xs text-brand";
        emailInput.value = "";
      } catch (err) {
        messageEl.textContent = err.message || "Could not subscribe.";
        messageEl.className = "newsletter-message text-xs text-red-600";
      }
    });
  });
})();
