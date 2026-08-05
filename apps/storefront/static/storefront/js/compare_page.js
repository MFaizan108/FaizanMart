(function () {
  const emptyEl = document.getElementById("compare-empty");
  const loadingEl = document.getElementById("compare-loading");
  const wrapEl = document.getElementById("compare-table-wrap");
  const bodyEl = document.getElementById("compare-table-body");

  function fmt(amount) {
    return amount == null ? "—" : "Rs " + Math.round(Number(amount)).toLocaleString("en-PK");
  }

  function cell(content, opts) {
    opts = opts || {};
    const td = document.createElement(opts.header ? "th" : "td");
    td.className =
      (opts.header ? "sticky left-0 z-10 bg-page text-left font-semibold text-black/60 " : "bg-white ") +
      "border-b border-black/8 px-4 py-3 align-top " +
      (opts.first ? "w-40 " : "min-w-[220px] ");
    if (typeof content === "string") td.innerHTML = content;
    else if (content) td.appendChild(content);
    return td;
  }

  function row(label, renderCell, products) {
    const tr = document.createElement("tr");
    tr.appendChild(cell(label, { header: true, first: true }));
    products.forEach((p) => tr.appendChild(cell(renderCell(p))));
    return tr;
  }

  async function load() {
    const ids = window.Compare ? window.Compare.getList() : [];
    if (!ids.length) {
      loadingEl.classList.add("hidden");
      emptyEl.classList.remove("hidden");
      emptyEl.classList.add("flex");
      return;
    }

    let products;
    try {
      products = await Promise.all(ids.map((id) => Storefront.apiFetch(`/catalog/products/${id}/`)));
    } catch (err) {
      loadingEl.textContent = "Could not load one or more products.";
      return;
    }
    loadingEl.classList.add("hidden");
    wrapEl.classList.remove("hidden");

    bodyEl.innerHTML = "";
    bodyEl.appendChild(
      row(
        "",
        (p) => {
          const wrap = document.createElement("div");
          wrap.className = "flex flex-col items-start gap-2";
          const img = document.createElement("div");
          img.className = "flex h-28 w-28 items-center justify-center overflow-hidden rounded-lg bg-black/5 text-3xl";
          if (p.images && p.images[0]) {
            const image = document.createElement("img");
            image.src = p.images[0].image;
            image.className = "h-full w-full object-cover";
            img.appendChild(image);
          } else {
            img.textContent = "📦";
          }
          const removeBtn = document.createElement("button");
          removeBtn.type = "button";
          removeBtn.textContent = "Remove";
          removeBtn.className = "text-xs text-danger hover:underline";
          removeBtn.addEventListener("click", () => {
            window.Compare.toggle(p.id);
            load();
          });
          wrap.append(img, removeBtn);
          return wrap;
        },
        products
      )
    );
    bodyEl.appendChild(row("Product", (p) => `<a href="/products/${p.id}/" class="font-medium hover:text-brand">${p.name}</a>`, products));
    bodyEl.appendChild(row("Brand", (p) => (p.brand ? p.brand.name : "—"), products));
    bodyEl.appendChild(row("Category", (p) => (p.category ? p.category.name : "—"), products));
    bodyEl.appendChild(row("Price", (p) => `<span class="font-semibold text-brand">${fmt(p.price)}</span>`, products));
    bodyEl.appendChild(row("Compare-at price", (p) => (p.compare_at_price ? `<span class="line-through text-black/40">${fmt(p.compare_at_price)}</span>` : "—"), products));
    bodyEl.appendChild(row("Sold by", (p) => `<a href="/store/${p.store_slug}/" class="hover:text-brand">${p.store_name}</a>`, products));
    bodyEl.appendChild(row("Description", (p) => `<span class="line-clamp-4 text-black/70">${p.description || "—"}</span>`, products));
    bodyEl.appendChild(
      row(
        "",
        (p) => {
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "btn-primary w-full";
          btn.textContent = "Add to Cart";
          btn.addEventListener("click", async () => {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span>';
            try {
              const cart = await Storefront.apiFetch("/cart/items/", {
                method: "POST",
                body: JSON.stringify({ product: p.id, quantity: 1 }),
              });
              Storefront.updateCartBadge(cart.items_count);
              btn.textContent = "Added ✓";
            } catch (err) {
              btn.textContent = "Error";
              btn.disabled = false;
            }
          });
          return btn;
        },
        products
      )
    );
  }

  document.getElementById("compare-page-clear-btn").addEventListener("click", () => {
    if (window.Compare) window.Compare.clearAll();
    load();
  });

  load();
})();
