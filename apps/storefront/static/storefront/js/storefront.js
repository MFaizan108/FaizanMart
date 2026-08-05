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

    if (options.body) headers["Content-Type"] = "application/json";
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

  window.Storefront = { apiFetch, updateCartBadge, showError, hideError, getCookie };
})();
