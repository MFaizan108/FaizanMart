(function () {
  const loadingEl = document.getElementById("products-loading");
  const emptyEl = document.getElementById("products-empty");
  const listEl = document.getElementById("products-list");
  const errorEl = document.getElementById("products-error");
  const template = document.getElementById("product-row-template");

  const toggleBtn = document.getElementById("toggle-product-form");
  const form = document.getElementById("product-form");
  const formErrorEl = document.getElementById("product-form-error");

  toggleBtn.addEventListener("click", () => {
    form.classList.toggle("hidden");
    form.classList.toggle("flex");
  });

  const STATUS_BADGE = {
    published: "badge-new",
    pending_review: "badge-warning",
    rejected: "badge-sale",
    draft: "badge-outofstock",
    archived: "badge-outofstock",
  };
  const STATUS_LABEL = {
    published: "Live",
    pending_review: "Pending review",
    rejected: "Rejected",
    draft: "Draft",
    archived: "Archived",
  };

  function renderRow(product) {
    const node = template.content.cloneNode(true);
    const link = node.querySelector(".product-link");
    link.textContent = product.name;
    link.href = "/products/" + product.id + "/";
    node.querySelector(".product-meta").textContent =
      `SKU ${product.sku} · Rs ${Math.round(product.price).toLocaleString("en-PK")}`;

    if (product.images && product.images.length) {
      const thumb = node.querySelector(".product-thumb");
      thumb.textContent = "";
      const img = document.createElement("img");
      img.src = product.images[0].image;
      img.className = "h-full w-full object-cover";
      thumb.appendChild(img);
    }

    if (product.status === "rejected" && product.rejection_reason) {
      const reasonEl = node.querySelector(".rejection-reason");
      reasonEl.textContent = "Rejected: " + product.rejection_reason;
      reasonEl.classList.remove("hidden");
    }

    const badge = node.querySelector(".status-badge");
    badge.textContent = STATUS_LABEL[product.status] || product.status;
    badge.classList.add(STATUS_BADGE[product.status] || "badge-outofstock");

    const toggleStatusBtn = node.querySelector(".toggle-status-btn");
    if (product.status === "published") {
      toggleStatusBtn.textContent = "Unpublish";
      toggleStatusBtn.addEventListener("click", async () => {
        try {
          await Storefront.apiFetch(`/catalog/products/${product.id}/`, {
            method: "PATCH",
            body: JSON.stringify({ status: "draft" }),
          });
          load();
        } catch (err) {
          Storefront.showError(errorEl, err.message);
        }
      });
    } else if (product.status === "pending_review") {
      toggleStatusBtn.remove();
    } else {
      toggleStatusBtn.textContent = "Submit for review";
      toggleStatusBtn.addEventListener("click", async () => {
        try {
          await Storefront.apiFetch(`/catalog/products/${product.id}/`, {
            method: "PATCH",
            body: JSON.stringify({ status: "published" }),
          });
          load();
        } catch (err) {
          Storefront.showError(errorEl, err.message);
        }
      });
    }

    node.querySelector(".delete-btn").addEventListener("click", async () => {
      if (!confirm(`Delete "${product.name}"? This cannot be undone.`)) return;
      try {
        await Storefront.apiFetch(`/catalog/products/${product.id}/`, { method: "DELETE" });
        load();
      } catch (err) {
        Storefront.showError(errorEl, err.message);
      }
    });

    return node;
  }

  async function load() {
    loadingEl.classList.remove("hidden");
    listEl.innerHTML = "";
    emptyEl.classList.add("hidden");
    Storefront.hideError(errorEl);
    try {
      const data = await Storefront.apiFetch(`/catalog/products/?store=${window.STORE_ID}&page_size=100`);
      loadingEl.classList.add("hidden");
      const results = data.results || data;
      if (!results.length) {
        emptyEl.classList.remove("hidden");
        emptyEl.classList.add("flex");
        return;
      }
      results.forEach((product) => listEl.appendChild(renderRow(product)));
    } catch (err) {
      loadingEl.classList.add("hidden");
      Storefront.showError(errorEl, err.message);
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    Storefront.hideError(formErrorEl);
    const formData = new FormData(form);
    const submitBtn = form.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    try {
      const product = await Storefront.apiFetch("/catalog/products/", {
        method: "POST",
        body: JSON.stringify({
          category: Number(formData.get("category")),
          brand: formData.get("brand") ? Number(formData.get("brand")) : null,
          name: formData.get("name"),
          sku: formData.get("sku"),
          price: formData.get("price"),
          compare_at_price: formData.get("compare_at_price") || null,
          description: formData.get("description") || "",
          video_url: formData.get("video_url") || "",
          quantity: formData.get("quantity") || 0,
          status: formData.get("status"),
        }),
      });

      const images = form.querySelector('input[name="images"]').files;
      for (let i = 0; i < images.length; i++) {
        const imageData = new FormData();
        imageData.append("product", product.id);
        imageData.append("image", images[i]);
        imageData.append("is_primary", i === 0 ? "true" : "false");
        imageData.append("sort_order", String(i));
        try {
          await Storefront.apiFetch("/catalog/product-images/", { method: "POST", body: imageData });
        } catch (err) {
          Storefront.toast(`Product saved, but "${images[i].name}" failed to upload: ${err.message}`, "error");
        }
      }

      form.reset();
      form.classList.add("hidden");
      form.classList.remove("flex");
      load();
    } catch (err) {
      Storefront.showError(formErrorEl, err.message);
    } finally {
      submitBtn.disabled = false;
    }
  });

  load();
})();
