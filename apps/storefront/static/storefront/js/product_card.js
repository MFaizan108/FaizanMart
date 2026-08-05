/* "Quick add to cart" from any product card — event-delegated so it works for cards
 * rendered server-side (_product_card.html) and cards rendered dynamically by
 * product_list.js after a fetch(), same pattern as wishlist.js. */
(function () {
  document.addEventListener("click", async function (event) {
    const btn = event.target.closest(".card-add-to-cart-btn");
    if (!btn || btn.disabled) return;
    event.preventDefault();
    event.stopPropagation();

    const productId = Number(btn.dataset.productId);
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>';

    try {
      const cart = await Storefront.apiFetch("/cart/items/", {
        method: "POST",
        body: JSON.stringify({ product: productId, quantity: 1 }),
      });
      Storefront.updateCartBadge(cart.items_count);
      btn.textContent = "Added ✓";
      setTimeout(() => {
        btn.textContent = originalText;
        btn.disabled = false;
      }, 1500);
    } catch (err) {
      btn.textContent = "Error";
      setTimeout(() => {
        btn.textContent = originalText;
        btn.disabled = false;
      }, 1500);
    }
  });
})();
