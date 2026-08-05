(function () {
  /* ---- Sticky navbar: translucent + blurred once the page scrolls ---- */
  const siteHeader = document.getElementById("site-header");
  if (siteHeader) {
    function onScroll() {
      const scrolled = window.scrollY > 8;
      siteHeader.classList.toggle("bg-white", !scrolled);
      siteHeader.classList.toggle("bg-white/85", scrolled);
      siteHeader.classList.toggle("backdrop-blur-md", scrolled);
      siteHeader.classList.toggle("shadow-md", scrolled);
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

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

  /* ---- Search: autocomplete + recent/trending suggestions + keyboard nav ---- */
  const searchBox = document.getElementById("search-box");
  const searchForm = searchBox ? searchBox.querySelector("form") : null;
  const searchInput = document.getElementById("site-search");
  const suggestionsPanel = document.getElementById("search-suggestions");
  const RECENT_KEY = "faizanmart_recent_searches";
  const RECENT_LIMIT = 5;
  let debounceTimer = null;
  let latestQuery = "";
  let activeIndex = -1;

  function getRecentSearches() {
    try {
      const raw = localStorage.getItem(RECENT_KEY);
      const list = raw ? JSON.parse(raw) : [];
      return Array.isArray(list) ? list : [];
    } catch (err) {
      return [];
    }
  }

  function saveRecentSearch(query) {
    query = query.trim();
    if (!query) return;
    const list = [query, ...getRecentSearches().filter((q) => q.toLowerCase() !== query.toLowerCase())].slice(0, RECENT_LIMIT);
    localStorage.setItem(RECENT_KEY, JSON.stringify(list));
  }

  function clearRecentSearches() {
    localStorage.removeItem(RECENT_KEY);
  }

  function closeSuggestions() {
    suggestionsPanel.classList.add("invisible", "opacity-0");
    suggestionsPanel.innerHTML = "";
    activeIndex = -1;
  }

  function fmtPrice(amount) {
    return "Rs " + Math.round(amount).toLocaleString("en-PK");
  }

  function getOptions() {
    return Array.from(suggestionsPanel.querySelectorAll("[data-search-option]"));
  }

  function highlight(index) {
    const options = getOptions();
    if (!options.length) return;
    activeIndex = (index + options.length) % options.length;
    options.forEach((el, i) => el.classList.toggle("bg-brand/5", i === activeIndex));
    options[activeIndex].scrollIntoView({ block: "nearest" });
  }

  async function renderIdlePanel() {
    const recents = getRecentSearches();
    suggestionsPanel.innerHTML = "";

    if (recents.length) {
      const header = document.createElement("div");
      header.className = "flex items-center justify-between px-4 pt-3 text-xs font-semibold uppercase tracking-wide text-black/40";
      header.innerHTML = `<span>Recent searches</span><button type="button" id="clear-recent-searches" class="normal-case text-brand hover:underline">Clear</button>`;
      suggestionsPanel.appendChild(header);
      recents.forEach((q) => {
        const link = document.createElement("a");
        link.href = window.PRODUCT_LIST_URL + "?q=" + encodeURIComponent(q);
        link.dataset.searchOption = "true";
        link.dataset.query = q;
        link.className = "flex items-center gap-2 px-4 py-2.5 text-sm hover:bg-brand/5";
        link.innerHTML = `<span class="text-black/30">🕒</span><span class="truncate">${q}</span>`;
        suggestionsPanel.appendChild(link);
      });
    }

    try {
      const trending = await Storefront.apiFetch("/analytics/recommendations/trending/?days=7");
      if (trending.length) {
        const header = document.createElement("div");
        header.className = "flex items-center px-4 pt-3 text-xs font-semibold uppercase tracking-wide text-black/40";
        header.textContent = "Trending now";
        suggestionsPanel.appendChild(header);
        trending.slice(0, 5).forEach((product) => {
          const link = document.createElement("a");
          link.href = "/products/" + product.id + "/";
          link.dataset.searchOption = "true";
          link.className = "flex items-center gap-2 px-4 py-2.5 text-sm hover:bg-brand/5";
          link.innerHTML = `<span class="text-accent">🔥</span><span class="truncate">${product.name}</span>`;
          suggestionsPanel.appendChild(link);
        });
      }
    } catch (err) {
      /* trending is a nice-to-have — silently skip if it fails */
    }

    if (!suggestionsPanel.children.length) return;
    suggestionsPanel.appendChild(document.createElement("div")).className = "pb-2";
    suggestionsPanel.classList.remove("invisible", "opacity-0");

    const clearBtn = document.getElementById("clear-recent-searches");
    if (clearBtn) {
      clearBtn.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        clearRecentSearches();
        renderIdlePanel();
      });
    }
  }

  async function runSearch(query) {
    latestQuery = query;
    if (!query.trim()) {
      renderIdlePanel();
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
          link.dataset.searchOption = "true";
          link.className = "flex items-center justify-between gap-3 px-4 py-2.5 text-sm hover:bg-brand/5";
          link.innerHTML = `<span class="truncate">${product.name}</span><span class="shrink-0 font-medium text-black/60">${fmtPrice(product.price)}</span>`;
          suggestionsPanel.appendChild(link);
        });
      }

      const seeAll = document.createElement("a");
      seeAll.href = window.PRODUCT_LIST_URL + "?q=" + encodeURIComponent(query);
      seeAll.dataset.searchOption = "true";
      seeAll.className = "block border-t border-black/5 px-4 py-2.5 text-sm font-medium text-brand hover:bg-brand/5";
      seeAll.textContent = `See all results for "${query}"`;
      suggestionsPanel.appendChild(seeAll);

      activeIndex = -1;
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
    searchInput.addEventListener("focus", () => runSearch(searchInput.value));
    searchInput.addEventListener("keydown", (event) => {
      const options = getOptions();
      if (event.key === "ArrowDown") {
        if (!options.length) return;
        event.preventDefault();
        highlight(activeIndex + 1);
      } else if (event.key === "ArrowUp") {
        if (!options.length) return;
        event.preventDefault();
        highlight(activeIndex - 1);
      } else if (event.key === "Enter" && activeIndex >= 0 && options[activeIndex]) {
        event.preventDefault();
        options[activeIndex].click();
      }
    });
  }
  if (searchForm) {
    searchForm.addEventListener("submit", () => {
      if (searchInput && searchInput.value.trim()) saveRecentSearch(searchInput.value);
    });
  }
  suggestionsPanel.addEventListener("click", (event) => {
    const option = event.target.closest("[data-search-option]");
    if (option && option.dataset.query) saveRecentSearch(option.dataset.query);
    else if (option && option.tagName === "A" && searchInput) saveRecentSearch(searchInput.value);
  });
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
