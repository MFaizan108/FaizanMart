(function () {
  const backdrop = document.getElementById("quick-view-backdrop");
  const body = document.getElementById("quick-view-body");
  const closeBtn = document.getElementById("quick-view-close");
  if (!backdrop || !body) return;

  function open() {
    backdrop.classList.remove("invisible", "opacity-0");
  }
  function close() {
    backdrop.classList.add("invisible", "opacity-0");
    body.innerHTML = "";
  }

  function fmt(amount) {
    return "Rs " + Math.round(Number(amount)).toLocaleString("en-PK");
  }

  async function openProduct(productId) {
    body.innerHTML = '<div class="flex justify-center py-12"><span class="spinner !border-black/20 !border-t-brand !h-8 !w-8"></span></div>';
    open();
    try {
      const product = await Storefront.apiFetch(`/catalog/products/${productId}/`);
      const image = product.images && product.images[0] ? product.images[0].image : null;
      body.innerHTML = `
        <div class="grid grid-cols-1 gap-6 sm:grid-cols-2">
          <div class="flex aspect-square items-center justify-center overflow-hidden rounded-xl bg-black/5">
            ${image ? `<img src="${image}" alt="" class="h-full w-full object-cover">` : '<span class="text-5xl text-black/20">📦</span>'}
          </div>
          <div class="flex flex-col gap-2">
            ${product.brand ? `<span class="text-xs text-black/40">${product.brand.name}</span>` : ""}
            <h2 class="text-lg font-bold">${product.name}</h2>
            <div class="flex items-baseline gap-2">
              <span class="text-xl font-bold text-brand">${fmt(product.price)}</span>
              ${product.compare_at_price ? `<span class="text-sm text-black/40 line-through">${fmt(product.compare_at_price)}</span>` : ""}
            </div>
            <p class="text-sm text-black/40">Sold by ${product.store_name}</p>
            ${product.description ? `<p class="mt-2 line-clamp-4 text-sm text-black/70">${product.description}</p>` : ""}
            <div class="mt-4 flex gap-2">
              <button type="button" class="btn-primary quick-view-add-btn flex-1" data-product-id="${product.id}">Add to Cart</button>
              <a href="/products/${product.id}/" class="btn-secondary">View Details</a>
            </div>
            <p class="quick-view-error hidden text-sm text-danger"></p>
          </div>
        </div>`;

      body.querySelector(".quick-view-add-btn").addEventListener("click", async (event) => {
        const btn = event.currentTarget;
        btn.disabled = true;
        const original = btn.textContent;
        btn.innerHTML = '<span class="spinner"></span>';
        try {
          const cart = await Storefront.apiFetch("/cart/items/", {
            method: "POST",
            body: JSON.stringify({ product: product.id, quantity: 1 }),
          });
          Storefront.updateCartBadge(cart.items_count);
          btn.textContent = "Added ✓";
          setTimeout(close, 900);
        } catch (err) {
          Storefront.showError(body.querySelector(".quick-view-error"), err.message);
          btn.disabled = false;
          btn.textContent = original;
        }
      });
    } catch (err) {
      body.innerHTML = `<p class="py-12 text-center text-sm text-danger">${err.message}</p>`;
    }
  }

  document.addEventListener("click", (event) => {
    const trigger = event.target.closest(".quick-view-btn");
    if (trigger) {
      event.preventDefault();
      event.stopPropagation();
      openProduct(trigger.dataset.productId);
    }
  });

  if (closeBtn) closeBtn.addEventListener("click", close);
  backdrop.addEventListener("click", (event) => {
    if (event.target === backdrop) close();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") close();
  });
})();
