(function () {
  /* ---- Gallery thumbnails ---- */
  const galleryMainImg = document.getElementById("gallery-main-img");
  document.querySelectorAll(".gallery-thumb").forEach((thumb) => {
    thumb.addEventListener("click", () => {
      if (galleryMainImg && galleryMainImg.tagName === "IMG") {
        galleryMainImg.src = thumb.dataset.full;
      }
      document.querySelectorAll(".gallery-thumb").forEach((el) => {
        el.classList.toggle("border-brand", el === thumb);
        el.classList.toggle("border-transparent", el !== thumb);
      });
    });
  });

  /* ---- Description / Specifications / Reviews tabs ---- */
  const tabButtons = document.querySelectorAll(".detail-tab-btn");
  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabButtons.forEach((other) => {
        const active = other === btn;
        other.classList.toggle("border-brand", active);
        other.classList.toggle("text-brand", active);
        other.classList.toggle("border-transparent", !active);
        other.classList.toggle("text-black/50", !active);
        other.setAttribute("aria-selected", active ? "true" : "false");
      });
      document.querySelectorAll(".detail-tab-panel").forEach((panel) => {
        panel.classList.toggle("hidden", panel.id !== "tab-" + btn.dataset.tab);
      });
    });
  });

  const actions = document.getElementById("product-actions");
  if (actions) {
    const productId = Number(actions.dataset.productId);
    const addBtn = document.getElementById("add-to-cart-btn");
    const variantSelect = document.getElementById("variant");
    const quantityInput = document.getElementById("quantity");
    const errorEl = document.getElementById("add-to-cart-error");

    addBtn.addEventListener("click", async () => {
      Storefront.hideError(errorEl);
      addBtn.disabled = true;
      const originalText = addBtn.textContent;
      addBtn.textContent = "Adding...";
      try {
        await Storefront.apiFetch("/cart/items/", {
          method: "POST",
          body: JSON.stringify({
            product: productId,
            variant: variantSelect ? Number(variantSelect.value) : null,
            quantity: Math.max(1, Number(quantityInput.value) || 1),
          }),
        });
        addBtn.textContent = "Added ✓";
        setTimeout(() => (addBtn.textContent = originalText), 2000);
      } catch (err) {
        Storefront.showError(errorEl, err.message);
        addBtn.textContent = originalText;
      } finally {
        addBtn.disabled = false;
      }
    });
  }

  const starPicker = document.getElementById("star-picker");
  if (starPicker) {
    function paintStars(rating) {
      starPicker.querySelectorAll(".star").forEach((star) => {
        star.classList.toggle("text-amber-500", Number(star.dataset.value) <= rating);
        star.classList.toggle("text-black/20", Number(star.dataset.value) > rating);
      });
    }
    starPicker.addEventListener("click", (event) => {
      const star = event.target.closest(".star");
      if (!star) return;
      starPicker.dataset.rating = star.dataset.value;
      paintStars(Number(star.dataset.value));
    });
    paintStars(5);
  }

  const reviewForm = document.getElementById("review-form");
  if (reviewForm) {
    reviewForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const errorEl = document.getElementById("review-error");
      Storefront.hideError(errorEl);
      const formData = new FormData(reviewForm);
      try {
        await Storefront.apiFetch("/reviews/reviews/", {
          method: "POST",
          body: JSON.stringify({
            product: Number(reviewForm.dataset.productId),
            rating: Number(starPicker.dataset.rating),
            title: formData.get("title") || "",
            comment: formData.get("comment") || "",
          }),
        });
        window.location.reload();
      } catch (err) {
        Storefront.showError(errorEl, err.message);
      }
    });
  }
})();
