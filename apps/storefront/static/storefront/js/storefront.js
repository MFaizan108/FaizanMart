/* Shared helpers used by every storefront page — CSRF-aware fetch wrapper for the
 * existing DRF API (session-authenticated, same origin) and small cart/wishlist
 * utilities. Loaded on every page via templates/base.html. */
(function () {
  function getCookie(name) {
    const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
    return match ? decodeURIComponent(match[2]) : null;
  }

  function getCsrfToken() {
    // CSRF_COOKIE_HTTPONLY=True (FaizanMart/settings/base.py) means the csrftoken
    // cookie is deliberately unreadable from JS — read the token Django already
    // rendered into <meta name="csrf-token"> (templates/base.html) instead.
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : getCookie("csrftoken");
  }

  const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

  async function apiFetch(path, options) {
    options = options || {};
    const method = (options.method || "GET").toUpperCase();
    const headers = Object.assign({ Accept: "application/json" }, options.headers || {});

    if (options.body && !(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
    if (UNSAFE_METHODS.has(method)) headers["X-CSRFToken"] = getCsrfToken();
    if (window.CART_TOKEN) headers["X-Cart-Token"] = window.CART_TOKEN;

    const res = await fetch("/api" + path, { ...options, method, headers, credentials: "same-origin" });
    const contentType = res.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await res.json().catch(() => ({})) : null;

    if (!res.ok) {
      const message = (data && (data.detail || firstFieldError(data))) || `Request failed (${res.status})`;
      const error = new Error(message);
      error.status = res.status;
      error.body = data;
      throw error;
    }
    return data;
  }

  function firstFieldError(data) {
    for (const key of Object.keys(data)) {
      if (Array.isArray(data[key]) && data[key].length) return data[key][0];
    }
    return null;
  }

  function updateCartBadge(count) {
    const badge = document.getElementById("cart-badge-count");
    if (!badge) return;
    badge.textContent = String(count);
    badge.classList.toggle("hidden", !count);
  }

  function showError(el, message) {
    if (!el) return;
    el.textContent = message;
    el.classList.remove("hidden");
  }

  function hideError(el) {
    if (!el) return;
    el.classList.add("hidden");
    el.textContent = "";
  }

  /* ---- HTML escaping ----
   * For the handful of spots that build markup via template-literal innerHTML (rather than
   * textContent) but still need to interpolate server/user-supplied text (product names,
   * descriptions, addresses, ...) — wrap that text in this before it goes into the template
   * literal, so it can never be interpreted as markup. */
  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]
    ));
  }

  /* ---- Toast notifications ---- */
  const ICONS = { success: "✓", error: "✕", info: "ℹ" };

  function toast(message, type) {
    const container = document.getElementById("toast-container");
    if (!container) return;
    type = type || "info";
    const el = document.createElement("div");
    el.className = "toast toast-" + type;
    el.setAttribute("role", "status");
    const icon = document.createElement("span");
    icon.textContent = ICONS[type] || ICONS.info;
    const text = document.createElement("span");
    text.textContent = message;
    el.append(icon, text);
    container.appendChild(el);
    setTimeout(() => {
      el.classList.add("toast-leaving");
      el.addEventListener("animationend", () => el.remove());
    }, 3000);
  }

  /* ---- Searchable <select> ----
   * Turns a plain <select> into a type-to-filter combobox — for long option lists (e.g.
   * 100+ categories) where scrolling a native dropdown is painful. Keeps the original
   * <select> in the DOM (visually hidden, still driving form submission via .value); the
   * "required" attribute moves to the visible text input so native validation still works
   * on the field the user actually sees. */
  function makeSearchableSelect(select) {
    if (!select || select.dataset.searchableInit) return;
    select.dataset.searchableInit = "true";

    const options = Array.from(select.options).filter((o) => o.value !== "");
    const placeholder = select.options[0] && select.options[0].value === "" ? select.options[0].textContent : "Select…";

    const wrapper = document.createElement("div");
    wrapper.className = "relative";
    select.style.cssText = "position:absolute;opacity:0;height:0;width:0;pointer-events:none;";
    select.tabIndex = -1;

    const input = document.createElement("input");
    input.type = "text";
    input.autocomplete = "off";
    input.placeholder = placeholder;
    input.className = select.dataset.inputClass || "w-full rounded-md border border-black/15 px-3 py-2 text-sm";
    if (select.required) {
      input.required = true;
      select.required = false;
    }

    const panel = document.createElement("div");
    panel.className = "invisible absolute left-0 right-0 top-full z-30 mt-1 max-h-56 overflow-y-auto rounded-md border border-black/10 bg-white opacity-0 shadow-lg transition";

    select.parentNode.insertBefore(wrapper, select);
    wrapper.append(select, input, panel);

    let matches = [];
    let activeIndex = -1;

    function choose(option) {
      select.value = option.value;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      input.value = option.textContent;
      close();
    }

    function highlight(index) {
      const rows = Array.from(panel.children);
      activeIndex = index;
      rows.forEach((row, i) => row.classList.toggle("bg-brand/5", i === activeIndex));
      if (rows[activeIndex]) rows[activeIndex].scrollIntoView({ block: "nearest" });
    }

    function renderOptions() {
      const term = input.value.trim().toLowerCase();
      matches = options.filter((o) => o.textContent.toLowerCase().includes(term));
      panel.innerHTML = "";
      activeIndex = -1;
      if (!matches.length) {
        panel.innerHTML = '<p class="px-3 py-2 text-sm text-black/40">No matches.</p>';
        return;
      }
      matches.forEach((option) => {
        const row = document.createElement("div");
        row.className = "cursor-pointer px-3 py-2 text-sm hover:bg-brand/5";
        row.textContent = option.textContent;
        row.addEventListener("mousedown", (event) => {
          event.preventDefault();
          choose(option);
        });
        panel.appendChild(row);
      });
    }

    function open() {
      renderOptions();
      panel.classList.remove("invisible", "opacity-0");
    }
    function close() {
      panel.classList.add("invisible", "opacity-0");
    }

    input.addEventListener("focus", open);
    input.addEventListener("input", () => {
      if (select.value) {
        select.value = "";
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }
      open();
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        if (matches.length) highlight((activeIndex + 1) % matches.length);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        if (matches.length) highlight((activeIndex - 1 + matches.length) % matches.length);
      } else if (event.key === "Enter") {
        event.preventDefault();
        if (activeIndex >= 0 && matches[activeIndex]) choose(matches[activeIndex]);
      } else if (event.key === "Escape") {
        close();
      }
    });
    document.addEventListener("click", (event) => {
      if (!wrapper.contains(event.target)) close();
    });

    if (select.value) {
      const selected = options.find((o) => o.value === select.value);
      if (selected) input.value = selected.textContent;
    }
  }

  window.Storefront = {
    apiFetch, updateCartBadge, showError, hideError, getCookie, toast, escapeHtml, makeSearchableSelect,
  };

  /* ---- Button click ripple (design system micro-animation) ---- */
  document.addEventListener("click", (event) => {
    const btn = event.target.closest(".btn-primary, .btn-accent, .btn-secondary");
    if (!btn || btn.disabled) return;
    const rect = btn.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    const ripple = document.createElement("span");
    ripple.className = "ripple";
    ripple.style.width = ripple.style.height = size + "px";
    ripple.style.left = event.clientX - rect.left - size / 2 + "px";
    ripple.style.top = event.clientY - rect.top - size / 2 + "px";
    btn.appendChild(ripple);
    ripple.addEventListener("animationend", () => ripple.remove());
  });
})();
