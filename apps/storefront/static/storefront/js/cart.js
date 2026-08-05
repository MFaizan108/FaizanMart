(function () {
  const loadingEl = document.getElementById("cart-loading");
  const emptyEl = document.getElementById("cart-empty");
  const contentEl = document.getElementById("cart-content");
  const groupsEl = document.getElementById("cart-groups");
  const itemsCountEl = document.getElementById("cart-items-count");
  const subtotalEl = document.getElementById("cart-subtotal");
  const errorEl = document.getElementById("cart-error");
  const groupTemplate = document.getElementById("cart-group-template");
  const itemTemplate = document.getElementById("cart-item-template");

  function renderItem(item) {
    const node = itemTemplate.content.cloneNode(true);
    const href = "/products/" + item.product.id + "/";

    const imageEl = node.querySelector(".item-image");
    imageEl.href = href;
    if (item.product.image_url) {
      imageEl.textContent = "";
      const img = document.createElement("img");
      img.src = item.product.image_url;
      img.alt = item.product.name;
      img.className = "h-full w-full object-cover";
      imageEl.appendChild(img);
    }

    const nameLink = node.querySelector(".item-name");
    nameLink.textContent = item.product.name;
    nameLink.href = href;

    const variantEl = node.querySelector(".item-variant");
    if (item.variant && (item.variant.color || item.variant.size)) {
      variantEl.textContent = [item.variant.color, item.variant.size].filter(Boolean).join(" / ");
    } else {
      variantEl.remove();
    }

    node.querySelector(".item-unit-price").textContent = "Rs " + Math.round(item.unit_price).toLocaleString("en-PK") + " each";
    node.querySelector(".item-line-total").textContent = "Rs " + Math.round(item.line_total).toLocaleString("en-PK");

    const qtyInput = node.querySelector(".item-quantity");
    qtyInput.value = item.quantity;
    qtyInput.addEventListener("change", () => updateQuantity(item.id, Math.max(1, Number(qtyInput.value) || 1)));

    node.querySelector(".item-remove").addEventListener("click", () => removeItem(item.id));

    const wishlistBtn = node.querySelector(".item-wishlist-btn");
    wishlistBtn.addEventListener("click", async () => {
      if (!window.IS_AUTHENTICATED) {
        window.location.href = window.LOGIN_URL + "?next=" + encodeURIComponent(window.location.pathname);
        return;
      }
      wishlistBtn.disabled = true;
      try {
        await Storefront.apiFetch("/reviews/wishlist/toggle/", {
          method: "POST",
          body: JSON.stringify({ product: item.product.id }),
        });
        wishlistBtn.textContent = "❤️";
      } catch (err) {
        Storefront.showError(errorEl, err.message);
      } finally {
        wishlistBtn.disabled = false;
      }
    });

    return node;
  }

  function render(cart) {
    Storefront.updateCartBadge(cart.items_count);
    if (cart.items.length === 0) {
      emptyEl.classList.remove("hidden");
      emptyEl.classList.add("flex");
      contentEl.classList.add("hidden");
      return;
    }
    emptyEl.classList.add("hidden");
    contentEl.classList.remove("hidden");
    contentEl.classList.add("flex");

    groupsEl.innerHTML = "";
    const groups = new Map();
    cart.items.forEach((item) => {
      const storeId = item.product.store_id;
      if (!groups.has(storeId)) groups.set(storeId, { name: item.product.store_name || "FaizanMart Seller", items: [] });
      groups.get(storeId).items.push(item);
    });

    groups.forEach((group) => {
      const node = groupTemplate.content.cloneNode(true);
      node.querySelector(".seller-name-text").textContent = "Sold by " + group.name;
      const itemsContainer = node.querySelector(".group-items");
      group.items.forEach((item) => itemsContainer.appendChild(renderItem(item)));
      groupsEl.appendChild(node);
    });

    itemsCountEl.textContent = cart.items_count;
    subtotalEl.textContent = Math.round(cart.subtotal).toLocaleString("en-PK");
  }

  async function load() {
    try {
      const cart = await Storefront.apiFetch("/cart/");
      loadingEl.classList.add("hidden");
      render(cart);
    } catch (err) {
      loadingEl.classList.add("hidden");
      Storefront.showError(errorEl, err.message);
    }
  }

  async function updateQuantity(itemId, quantity) {
    try {
      const cart = await Storefront.apiFetch(`/cart/items/${itemId}/`, {
        method: "PATCH",
        body: JSON.stringify({ quantity }),
      });
      render(cart);
    } catch (err) {
      Storefront.showError(errorEl, err.message);
    }
  }

  async function removeItem(itemId) {
    try {
      const cart = await Storefront.apiFetch(`/cart/items/${itemId}/`, { method: "DELETE" });
      render(cart);
    } catch (err) {
      Storefront.showError(errorEl, err.message);
    }
  }

  document.getElementById("clear-cart-btn").addEventListener("click", async () => {
    try {
      const cart = await Storefront.apiFetch("/cart/clear/", { method: "POST" });
      render(cart);
    } catch (err) {
      Storefront.showError(errorEl, err.message);
    }
  });

  load();
})();
