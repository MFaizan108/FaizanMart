(function () {
  const loadingEl = document.getElementById("wishlist-loading");
  const emptyEl = document.getElementById("wishlist-empty");
  const itemsEl = document.getElementById("wishlist-items");
  const template = document.getElementById("wishlist-item-template");

  function renderItem(item) {
    const node = template.content.cloneNode(true);
    const link = node.querySelector(".item-name");
    link.textContent = item.product_name;
    link.href = "/products/" + item.product + "/";
    node.querySelector(".item-price").textContent = "Rs " + Math.round(item.product_price).toLocaleString("en-PK");

    const moveBtn = node.querySelector(".move-to-cart-btn");
    moveBtn.addEventListener("click", async () => {
      moveBtn.disabled = true;
      try {
        const cart = await Storefront.apiFetch("/cart/items/", {
          method: "POST",
          body: JSON.stringify({ product: item.product, quantity: 1 }),
        });
        Storefront.updateCartBadge(cart.items_count);
        await Storefront.apiFetch("/reviews/wishlist/toggle/", {
          method: "POST",
          body: JSON.stringify({ product: item.product }),
        });
        load();
      } catch (err) {
        console.error(err);
        moveBtn.disabled = false;
      }
    });

    node.querySelector(".remove-btn").addEventListener("click", async (event) => {
      const row = event.target.closest("div.flex.items-center.justify-between");
      try {
        await Storefront.apiFetch("/reviews/wishlist/toggle/", {
          method: "POST",
          body: JSON.stringify({ product: item.product }),
        });
        row.remove();
        if (!itemsEl.children.length) {
          emptyEl.classList.remove("hidden");
          emptyEl.classList.add("flex");
        }
      } catch (err) {
        console.error(err);
      }
    });

    return node;
  }

  async function load() {
    loadingEl.classList.remove("hidden");
    emptyEl.classList.add("hidden");
    itemsEl.innerHTML = "";
    try {
      const data = await Storefront.apiFetch("/reviews/wishlist/");
      loadingEl.classList.add("hidden");
      if (data.results.length === 0) {
        emptyEl.classList.remove("hidden");
        emptyEl.classList.add("flex");
        return;
      }
      data.results.forEach((item) => itemsEl.appendChild(renderItem(item)));
    } catch (err) {
      loadingEl.textContent = "Could not load wishlist.";
    }
  }

  load();
})();
