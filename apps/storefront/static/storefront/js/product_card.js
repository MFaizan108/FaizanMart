/* "Quick add to cart" / "Buy now" from any product card — event-delegated so it works
 * for cards rendered server-side (_product_card.html) and cards rendered dynamically by
 * product_list.js / seller_storefront.js after a fetch(), same pattern as wishlist.js. */
(function () {
  document.addEventListener("click", async function (event) {
    const addBtn = event.target.closest(".card-add-to-cart-btn");
    if (addBtn && !addBtn.disabled) {
      event.preventDefault();
      event.stopPropagation();

      const productId = Number(addBtn.dataset.productId);
      const originalText = addBtn.textContent;
      addBtn.disabled = true;
      addBtn.innerHTML = '<span class="spinner-dark"></span>';

      try {
        const cart = await Storefront.apiFetch("/cart/items/", {
          method: "POST",
          body: JSON.stringify({ product: productId, quantity: 1 }),
        });
        Storefront.updateCartBadge(cart.items_count);
        addBtn.textContent = "Added ✓";
        Storefront.toast("Added to cart", "success");
        setTimeout(() => {
          addBtn.textContent = originalText;
          addBtn.disabled = false;
        }, 1500);
      } catch (err) {
        addBtn.textContent = "Error";
        Storefront.toast(err.message || "Could not add to cart", "error");
        setTimeout(() => {
          addBtn.textContent = originalText;
          addBtn.disabled = false;
        }, 1500);
      }
      return;
    }

    const buyBtn = event.target.closest(".card-buy-now-btn");
    if (buyBtn && !buyBtn.disabled) {
      event.preventDefault();
      event.stopPropagation();

      const productId = Number(buyBtn.dataset.productId);
      buyBtn.disabled = true;
      const originalText = buyBtn.textContent;
      buyBtn.innerHTML = '<span class="spinner"></span>';

      try {
        await Storefront.apiFetch("/cart/items/", {
          method: "POST",
          body: JSON.stringify({ product: productId, quantity: 1 }),
        });
        window.location.href = window.CHECKOUT_URL;
      } catch (err) {
        buyBtn.textContent = "Error";
        setTimeout(() => {
          buyBtn.textContent = originalText;
          buyBtn.disabled = false;
        }, 1500);
      }
    }
  });
})();
