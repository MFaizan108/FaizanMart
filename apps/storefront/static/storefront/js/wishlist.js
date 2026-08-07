/* Wishlist heart-toggle — event-delegated so it also works on cards rendered
 * dynamically by product_list.js after a fetch(), not just server-rendered ones. */
(function () {
  document.addEventListener("click", async function (event) {
    const btn = event.target.closest(".wishlist-btn");
    if (!btn) return;
    event.preventDefault();
    event.stopPropagation();

    if (!window.IS_AUTHENTICATED) {
      window.location.href = (window.LOGIN_URL || "/accounts/login/") + "?next=" + encodeURIComponent(window.location.pathname + window.location.search);
      return;
    }

    const productId = Number(btn.dataset.productId);
    const icon = btn.querySelector(".wishlist-icon");
    btn.disabled = true;
    try {
      const result = await Storefront.apiFetch("/reviews/wishlist/toggle/", {
        method: "POST",
        body: JSON.stringify({ product: productId }),
      });
      btn.dataset.wishlisted = result.added ? "true" : "false";
      if (icon) icon.textContent = result.added ? "❤️" : "🤍";
      document.dispatchEvent(
        new CustomEvent("wishlist:changed", { detail: { productId, added: result.added } })
      );
      Storefront.toast(result.added ? "Added to wishlist" : "Removed from wishlist", "success");
    } catch (err) {
      console.error("Wishlist toggle failed", err);
      Storefront.toast("Could not update wishlist", "error");
    } finally {
      btn.disabled = false;
    }
  });
})();
