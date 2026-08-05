(function () {
  const PAGE_SIZE = 12;
  const grid = document.getElementById("product-grid");
  const gridSkeleton = document.getElementById("product-grid-skeleton");
  const template = document.getElementById("product-card-template");
  const sortSelect = document.getElementById("sort-select");
  const emptyMessage = document.getElementById("empty-message");
  const pagination = document.getElementById("pagination");

  let wishlistedIds = new Set();
  let currentPage = 1;

  function buildQuery(page, sort) {
    const params = new URLSearchParams();
    if (window.STORE_ID != null) params.set("store", String(window.STORE_ID));
    if (sort) params.set("sort", sort);
    params.set("page", String(page));
    params.set("page_size", String(PAGE_SIZE));
    return params.toString();
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
    node.querySelector(".price").textContent = "Rs " + Math.round(product.price).toLocaleString("en-PK");

    const ratingLine = node.querySelector(".rating-line");
    ratingLine.textContent =
      product.review_count > 0 ? `${product.avg_rating.toFixed(1)} (${product.review_count})` : "No ratings";

    const addToCartBtn = node.querySelector(".card-add-to-cart-btn");
    addToCartBtn.dataset.productId = product.id;
    const buyNowBtn = node.querySelector(".card-buy-now-btn");
    buyNowBtn.dataset.productId = product.id;
    if (product.is_available === false) {
      node.querySelector(".outofstock-badge").classList.remove("hidden");
      addToCartBtn.disabled = true;
      addToCartBtn.textContent = "Out of Stock";
      buyNowBtn.remove();
    }

    const quickViewBtn = node.querySelector(".quick-view-btn");
    quickViewBtn.dataset.productId = product.id;
    const compareBtn = node.querySelector(".compare-btn");
    compareBtn.dataset.productId = product.id;
    if (window.Compare && window.Compare.isCompared(product.id)) {
      compareBtn.classList.add("text-brand");
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

  function renderPagination(count) {
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
          currentPage = page;
          fetchAndRender();
          window.scrollTo({ top: 0, behavior: "smooth" });
        });
      }
      return el;
    }

    pagination.appendChild(makeLink("Previous", currentPage - 1, currentPage <= 1));
    const span = document.createElement("span");
    span.textContent = `Page ${currentPage} of ${totalPages}`;
    pagination.appendChild(span);
    pagination.appendChild(makeLink("Next", currentPage + 1, currentPage >= totalPages));
  }

  async function fetchAndRender() {
    grid.innerHTML = "";
    grid.classList.add("hidden");
    grid.classList.remove("grid");
    gridSkeleton.classList.remove("hidden");
    gridSkeleton.classList.add("grid");
    emptyMessage.classList.add("hidden");

    await loadWishlistIds();

    const query = buildQuery(currentPage, sortSelect.value);
    const data = await Storefront.apiFetch("/catalog/products/search/?" + query);

    gridSkeleton.classList.add("hidden");
    gridSkeleton.classList.remove("grid");
    grid.classList.remove("hidden");
    grid.classList.add("grid");

    if (data.results.length === 0) {
      emptyMessage.classList.remove("hidden");
    } else {
      data.results.forEach((product) => grid.appendChild(renderCard(product)));
    }
    renderPagination(data.count);
  }

  sortSelect.addEventListener("change", () => {
    currentPage = 1;
    fetchAndRender();
  });

  const chatBtn = document.getElementById("chat-with-seller-btn");
  if (chatBtn) {
    chatBtn.addEventListener("click", async () => {
      chatBtn.disabled = true;
      try {
        const conversation = await Storefront.apiFetch("/chat/conversations/start/", {
          method: "POST",
          body: JSON.stringify({
            kind: "customer_vendor",
            counterpart_id: Number(chatBtn.dataset.ownerId),
            store_id: Number(chatBtn.dataset.storeId),
          }),
        });
        window.location.href = "/account/messages/" + conversation.id + "/";
      } catch (err) {
        Storefront.toast(err.message || "Could not start conversation", "error");
        chatBtn.disabled = false;
      }
    });
  }

  fetchAndRender();
})();
