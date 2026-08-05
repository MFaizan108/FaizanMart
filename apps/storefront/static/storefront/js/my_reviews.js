(function () {
  const loadingEl = document.getElementById("reviews-loading");
  const emptyEl = document.getElementById("reviews-empty");
  const listEl = document.getElementById("reviews-list");
  const errorEl = document.getElementById("reviews-error");
  const template = document.getElementById("review-card-template");

  function paintStars(container, rating) {
    container.querySelectorAll(".star").forEach((star) => {
      star.classList.toggle("text-amber-500", Number(star.dataset.value) <= rating);
      star.classList.toggle("text-black/20", Number(star.dataset.value) > rating);
    });
  }

  function renderCard(review) {
    const node = template.content.cloneNode(true);
    const root = node.querySelector(".card");

    node.querySelector(".product-link").textContent = review.product_name;
    node.querySelector(".product-link").href = "/products/" + review.product + "/";
    node.querySelector(".review-date").textContent = new Date(review.created_at).toLocaleDateString();
    node.querySelector(".star-display").textContent = "★".repeat(review.rating) + "☆".repeat(5 - review.rating);
    node.querySelector(".review-title").textContent = review.title || "";
    node.querySelector(".review-comment").textContent = review.comment || "";

    if (review.vendor_reply) {
      const replyEl = node.querySelector(".vendor-reply");
      replyEl.textContent = "Seller reply: " + review.vendor_reply;
      replyEl.classList.remove("hidden");
    }

    const viewMode = node.querySelector(".view-mode");
    const editMode = node.querySelector(".edit-mode");
    const starPicker = editMode.querySelector(".star-picker");
    const titleInput = editMode.querySelector('[name="title"]');
    const commentInput = editMode.querySelector('[name="comment"]');

    node.querySelector(".edit-btn").addEventListener("click", () => {
      starPicker.dataset.rating = review.rating;
      paintStars(starPicker, review.rating);
      titleInput.value = review.title || "";
      commentInput.value = review.comment || "";
      viewMode.classList.add("hidden");
      editMode.classList.remove("hidden");
      editMode.classList.add("flex");
    });

    editMode.querySelector(".cancel-edit-btn").addEventListener("click", () => {
      editMode.classList.add("hidden");
      editMode.classList.remove("flex");
      viewMode.classList.remove("hidden");
    });

    starPicker.addEventListener("click", (event) => {
      const star = event.target.closest(".star");
      if (!star) return;
      starPicker.dataset.rating = star.dataset.value;
      paintStars(starPicker, Number(star.dataset.value));
    });

    editMode.addEventListener("submit", async (event) => {
      event.preventDefault();
      Storefront.hideError(errorEl);
      try {
        const updated = await Storefront.apiFetch(`/reviews/reviews/${review.id}/`, {
          method: "PATCH",
          body: JSON.stringify({
            rating: Number(starPicker.dataset.rating),
            title: titleInput.value,
            comment: commentInput.value,
          }),
        });
        review = Object.assign(review, updated);
        root.replaceWith(renderCard(review));
      } catch (err) {
        Storefront.showError(errorEl, err.message);
      }
    });

    node.querySelector(".delete-btn").addEventListener("click", async () => {
      try {
        await Storefront.apiFetch(`/reviews/reviews/${review.id}/`, { method: "DELETE" });
        root.remove();
        if (!listEl.children.length) {
          emptyEl.classList.remove("hidden");
          emptyEl.classList.add("flex");
        }
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
    try {
      const data = await Storefront.apiFetch("/reviews/reviews/?mine=true");
      loadingEl.classList.add("hidden");
      const results = data.results || data;
      if (!results.length) {
        emptyEl.classList.remove("hidden");
        emptyEl.classList.add("flex");
        return;
      }
      results.forEach((review) => listEl.appendChild(renderCard(review)));
    } catch (err) {
      loadingEl.classList.add("hidden");
      Storefront.showError(errorEl, err.message);
    }
  }

  load();
})();
