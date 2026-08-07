(function () {
  /* ---- Pending sellers ---- */
  const storesLoading = document.getElementById("stores-loading");
  const storesEmpty = document.getElementById("stores-empty");
  const storesList = document.getElementById("stores-list");
  const storeTemplate = document.getElementById("store-row-template");

  function renderStoreRow(store) {
    const node = storeTemplate.content.cloneNode(true);
    node.querySelector(".store-name").textContent = store.name;
    node.querySelector(".store-meta").textContent =
      `${store.owner_email} · applied ${new Date(store.created_at).toLocaleDateString()}`;

    node.querySelector(".approve-btn").addEventListener("click", async (event) => {
      const btn = event.currentTarget;
      btn.disabled = true;
      try {
        await Storefront.apiFetch(`/vendors/admin/applications/${store.id}/approve/`, { method: "POST" });
        Storefront.toast(`${store.name} approved`, "success");
        loadStores();
      } catch (err) {
        Storefront.toast(err.message || "Could not approve", "error");
        btn.disabled = false;
      }
    });

    node.querySelector(".reject-btn").addEventListener("click", async (event) => {
      const reason = prompt(`Reason for rejecting "${store.name}"?`);
      if (reason === null) return;
      const btn = event.currentTarget;
      btn.disabled = true;
      try {
        await Storefront.apiFetch(`/vendors/admin/applications/${store.id}/reject/`, {
          method: "POST",
          body: JSON.stringify({ reason }),
        });
        Storefront.toast(`${store.name} rejected`, "info");
        loadStores();
      } catch (err) {
        Storefront.toast(err.message || "Could not reject", "error");
        btn.disabled = false;
      }
    });

    return node;
  }

  async function loadStores() {
    storesLoading.classList.remove("hidden");
    storesEmpty.classList.add("hidden");
    storesList.innerHTML = "";
    try {
      const data = await Storefront.apiFetch("/vendors/admin/applications/?status=pending");
      storesLoading.classList.add("hidden");
      const results = data.results || data;
      if (!results.length) {
        storesEmpty.classList.remove("hidden");
        storesEmpty.classList.add("flex");
        return;
      }
      results.forEach((store) => storesList.appendChild(renderStoreRow(store)));
    } catch (err) {
      storesLoading.classList.add("hidden");
      Storefront.toast(err.message || "Could not load pending sellers", "error");
    }
  }

  /* ---- Pending products ---- */
  const productsLoading = document.getElementById("products-loading");
  const productsEmpty = document.getElementById("products-empty");
  const productsList = document.getElementById("products-list");
  const productTemplate = document.getElementById("product-row-template");

  function renderProductRow(product) {
    const node = productTemplate.content.cloneNode(true);
    const link = node.querySelector(".product-name");
    link.textContent = product.name;
    link.href = "/products/" + product.id + "/";
    node.querySelector(".product-meta").textContent =
      `${product.store_name} · Rs ${Math.round(product.price).toLocaleString("en-PK")}`;

    node.querySelector(".approve-btn").addEventListener("click", async (event) => {
      const btn = event.currentTarget;
      btn.disabled = true;
      try {
        await Storefront.apiFetch(`/catalog/products/${product.id}/approve/`, { method: "POST" });
        Storefront.toast(`${product.name} approved`, "success");
        loadProducts();
      } catch (err) {
        Storefront.toast(err.message || "Could not approve", "error");
        btn.disabled = false;
      }
    });

    node.querySelector(".reject-btn").addEventListener("click", async (event) => {
      const reason = prompt(`Reason for rejecting "${product.name}"?`);
      if (reason === null) return;
      const btn = event.currentTarget;
      btn.disabled = true;
      try {
        await Storefront.apiFetch(`/catalog/products/${product.id}/reject/`, {
          method: "POST",
          body: JSON.stringify({ reason }),
        });
        Storefront.toast(`${product.name} rejected`, "info");
        loadProducts();
      } catch (err) {
        Storefront.toast(err.message || "Could not reject", "error");
        btn.disabled = false;
      }
    });

    return node;
  }

  async function loadProducts() {
    productsLoading.classList.remove("hidden");
    productsEmpty.classList.add("hidden");
    productsList.innerHTML = "";
    try {
      const data = await Storefront.apiFetch("/catalog/products/pending/?page_size=100");
      productsLoading.classList.add("hidden");
      const results = data.results || data;
      if (!results.length) {
        productsEmpty.classList.remove("hidden");
        productsEmpty.classList.add("flex");
        return;
      }
      results.forEach((product) => productsList.appendChild(renderProductRow(product)));
    } catch (err) {
      productsLoading.classList.add("hidden");
      Storefront.toast(err.message || "Could not load pending products", "error");
    }
  }

  loadStores();
  loadProducts();
})();
