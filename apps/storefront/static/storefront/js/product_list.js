(function () {
  const PAGE_SIZE = 12;
  const grid = document.getElementById("product-grid");
  const gridSkeleton = document.getElementById("product-grid-skeleton");
  const template = document.getElementById("product-card-template");
  const forms = [document.getElementById("filter-form"), document.getElementById("filter-form-mobile")].filter(Boolean);
  const sortSelect = document.getElementById("sort-select");
  const resultCount = document.getElementById("result-count");
  const emptyMessage = document.getElementById("empty-message");
  const didYouMean = document.getElementById("did-you-mean");
  const pagination = document.getElementById("pagination");
  const pageTitle = document.getElementById("page-title");
  const breadcrumbCurrent = document.getElementById("breadcrumb-current");

  const mobileFilterBtn = document.getElementById("mobile-filter-btn");
  const mobileFilterDrawer = document.getElementById("mobile-filter-drawer");
  const mobileFilterBackdrop = document.getElementById("mobile-filter-backdrop");
  const mobileFilterClose = document.getElementById("mobile-filter-close");

  let wishlistedIds = new Set();

  function openMobileFilters() {
    mobileFilterDrawer.classList.remove("translate-x-full");
    mobileFilterBackdrop.classList.remove("hidden");
  }
  function closeMobileFilters() {
    mobileFilterDrawer.classList.add("translate-x-full");
    mobileFilterBackdrop.classList.add("hidden");
  }
  if (mobileFilterBtn) mobileFilterBtn.addEventListener("click", openMobileFilters);
  if (mobileFilterClose) mobileFilterClose.addEventListener("click", closeMobileFilters);
  if (mobileFilterBackdrop) mobileFilterBackdrop.addEventListener("click", closeMobileFilters);

  function currentFilters() {
    const params = new URLSearchParams(window.location.search);
    return {
      q: params.get("q") || "",
      category: params.get("category") || "",
      brand: params.get("brand") || "",
      min_price: params.get("min_price") || "",
      max_price: params.get("max_price") || "",
      min_rating: params.get("min_rating") || "",
      in_stock: params.get("in_stock") || "",
      sort: params.get("sort") || "",
      page: Number(params.get("page")) || 1,
    };
  }

  function buildQuery(filters) {
    const params = new URLSearchParams();
    if (filters.q) params.set("q", filters.q);
    if (filters.category) params.set("category", filters.category);
    if (filters.brand) params.set("brand", filters.brand);
    if (filters.min_price) params.set("min_price", filters.min_price);
    if (filters.max_price) params.set("max_price", filters.max_price);
    if (filters.min_rating) params.set("min_rating", filters.min_rating);
    if (filters.in_stock) params.set("in_stock", filters.in_stock);
    if (filters.sort) params.set("sort", filters.sort);
    params.set("page", String(filters.page));
    params.set("page_size", String(PAGE_SIZE));
    return params.toString();
  }

  function syncFormInputs(filters) {
    forms.forEach((form) => {
      form.querySelectorAll('[name="category"]').forEach((el) => (el.checked = el.value === filters.category));
      form.querySelectorAll('[name="min_rating"]').forEach((el) => (el.checked = el.value === filters.min_rating));
      const brandEl = form.querySelector('[name="brand"]');
      if (brandEl) brandEl.value = filters.brand;
      const minPriceEl = form.querySelector('[name="min_price"]');
      if (minPriceEl) minPriceEl.value = filters.min_price;
      const maxPriceEl = form.querySelector('[name="max_price"]');
      if (maxPriceEl) maxPriceEl.value = filters.max_price;
      const inStockEl = form.querySelector('[name="in_stock"]');
      if (inStockEl) inStockEl.checked = filters.in_stock === "true";
    });
    if (sortSelect) sortSelect.value = filters.sort;
    if (pageTitle) pageTitle.textContent = filters.category || "All Products";
    if (breadcrumbCurrent) breadcrumbCurrent.textContent = filters.category || "All Products";
  }

  function renderCard(product) {
    const node = template.content.cloneNode(true);
    const wishlistBtn = node.querySelector(".wishlist-btn");
    wishlistBtn.dataset.productId = product.id;
    const wishlisted = wishlistedIds.has(Number(product.id));
    wishlistBtn.dataset.wishlisted = wishlisted ? "true" : "false";
    node.querySelector(".wishlist-icon").textContent = wishlisted ? "❤️" : "🤍";

    const href = "/products/" + product.id + "/";
    const links = node.querySelectorAll(".product-link");
    links[0].href = href;
    links[1].href = href;
    links[1].textContent = product.name;

    node.querySelector(".brand-name").textContent = product.brand_name || "";
    node.querySelector(".seller-name").textContent = product.store_name ? "Sold by " + product.store_name : "";
    node.querySelector(".price").textContent = "Rs " + Math.round(product.price).toLocaleString("en-PK");

    const ratingLine = node.querySelector(".rating-line");
    ratingLine.textContent =
      product.review_count > 0 ? `${product.avg_rating.toFixed(1)} (${product.review_count})` : "No ratings";

    const addToCartBtn = node.querySelector(".card-add-to-cart-btn");
    addToCartBtn.dataset.productId = product.id;
    if (product.is_available === false) {
      node.querySelector(".outofstock-badge").classList.remove("hidden");
      addToCartBtn.disabled = true;
      addToCartBtn.textContent = "Out of Stock";
    }
    return node;
  }

  async function loadWishlistIds() {
    if (!window.IS_AUTHENTICATED) return;
    try {
      const items = await Storefront.apiFetch("/reviews/wishlist/");
      wishlistedIds = new Set(items.results.map((item) => item.product));
    } catch (err) {
      console.error("Could not load wishlist", err);
    }
  }

  function renderPagination(filters, count) {
    pagination.innerHTML = "";
    const totalPages = Math.max(Math.ceil(count / PAGE_SIZE), 1);
    if (totalPages <= 1) return;

    function makeLink(label, page, disabled) {
      const el = document.createElement(disabled ? "span" : "a");
      el.textContent = label;
      el.className = disabled
        ? "rounded-full border px-4 py-1.5 text-black/30"
        : "cursor-pointer rounded-full border px-4 py-1.5 hover:border-brand";
      if (!disabled) {
        el.addEventListener("click", () => {
          const next = Object.assign({}, filters, { page });
          navigate(next);
          window.scrollTo({ top: 0, behavior: "smooth" });
        });
      }
      return el;
    }

    pagination.appendChild(makeLink("Previous", filters.page - 1, filters.page <= 1));
    const span = document.createElement("span");
    span.textContent = `Page ${filters.page} of ${totalPages}`;
    pagination.appendChild(span);
    pagination.appendChild(makeLink("Next", filters.page + 1, filters.page >= totalPages));
  }

  async function fetchAndRender(filters) {
    resultCount.textContent = "Loading...";
    grid.innerHTML = "";
    grid.classList.add("hidden");
    grid.classList.remove("grid");
    gridSkeleton.classList.remove("hidden");
    gridSkeleton.classList.add("grid");
    emptyMessage.classList.add("hidden");
    didYouMean.classList.add("hidden");
    syncFormInputs(filters);

    await loadWishlistIds();

    const query = buildQuery(filters);
    const data = await Storefront.apiFetch("/catalog/products/search/?" + query);

    gridSkeleton.classList.add("hidden");
    gridSkeleton.classList.remove("grid");
    grid.classList.remove("hidden");
    grid.classList.add("grid");

    resultCount.textContent = `${data.count} products found`;
    if (data.did_you_mean) {
      didYouMean.textContent = `Did you mean ${data.did_you_mean}?`;
      didYouMean.classList.remove("hidden");
    }

    if (data.results.length === 0) {
      emptyMessage.classList.remove("hidden");
    } else {
      data.results.forEach((product) => grid.appendChild(renderCard(product)));
    }
    renderPagination(filters, data.count);
  }

  function navigate(filters) {
    const query = buildQuery(filters);
    window.history.pushState({}, "", "?" + query);
    fetchAndRender(filters);
  }

  function readFormFilters(form) {
    const formData = new FormData(form);
    const base = currentFilters();
    return Object.assign({}, base, {
      q: formData.get("q") || "",
      category: formData.get("category") || "",
      brand: formData.get("brand") || "",
      min_price: formData.get("min_price") || "",
      max_price: formData.get("max_price") || "",
      min_rating: formData.get("min_rating") || "",
      in_stock: formData.get("in_stock") === "true" ? "true" : "",
      page: 1,
    });
  }

  forms.forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      navigate(readFormFilters(form));
      closeMobileFilters();
    });
    const resetBtn = form.querySelector(".filter-reset-btn");
    if (resetBtn) {
      resetBtn.addEventListener("click", () => {
        const filters = currentFilters();
        navigate({ q: filters.q, category: "", brand: "", min_price: "", max_price: "", min_rating: "", in_stock: "", sort: filters.sort, page: 1 });
        closeMobileFilters();
      });
    }
  });

  if (sortSelect) {
    sortSelect.addEventListener("change", () => {
      const next = Object.assign({}, currentFilters(), { sort: sortSelect.value, page: 1 });
      navigate(next);
    });
  }

  window.addEventListener("popstate", () => fetchAndRender(currentFilters()));

  fetchAndRender(currentFilters());
})();
