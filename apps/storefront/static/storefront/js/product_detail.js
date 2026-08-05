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

  /* ---- Product Q&A ---- */
  const qaPanel = document.getElementById("tab-qa");
  if (qaPanel) {
    const productId = qaPanel.dataset.productId;
    const isOwner = qaPanel.dataset.isOwner === "true";
    const qaLoading = document.getElementById("qa-loading");
    const qaList = document.getElementById("qa-list");
    const qaEmpty = document.getElementById("qa-empty");
    const qaTemplate = document.getElementById("qa-row-template");
    const questionForm = document.getElementById("question-form");
    const questionText = document.getElementById("question-text");
    const questionError = document.getElementById("question-error");

    function renderQuestion(q) {
      const node = qaTemplate.content.cloneNode(true);
      node.querySelector(".q-text").textContent = q.question;
      node.querySelector(".q-meta").textContent =
        `Asked by ${q.customer_email} on ${new Date(q.created_at).toLocaleDateString()}`;

      if (q.answer) {
        const aEl = node.querySelector(".a-text");
        aEl.querySelector(".a-text-value").textContent = q.answer;
        aEl.classList.remove("hidden");
      } else if (isOwner) {
        const form = node.querySelector(".owner-answer-form");
        form.classList.remove("hidden");
        form.classList.add("flex");
        form.addEventListener("submit", async (event) => {
          event.preventDefault();
          const textarea = form.querySelector("textarea");
          try {
            await Storefront.apiFetch(`/reviews/questions/${q.id}/answer/`, {
              method: "POST",
              body: JSON.stringify({ answer: textarea.value }),
            });
            loadQuestions();
          } catch (err) {
            alert(err.message);
          }
        });
      }
      return node;
    }

    async function loadQuestions() {
      qaLoading.classList.remove("hidden");
      qaList.innerHTML = "";
      qaEmpty.classList.add("hidden");
      try {
        const data = await Storefront.apiFetch(`/reviews/questions/?product=${productId}`);
        qaLoading.classList.add("hidden");
        const results = data.results || data;
        if (!results.length) {
          qaEmpty.classList.remove("hidden");
          return;
        }
        results.forEach((q) => qaList.appendChild(renderQuestion(q)));
      } catch (err) {
        qaLoading.textContent = "Could not load questions.";
      }
    }

    if (questionForm) {
      questionForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        Storefront.hideError(questionError);
        try {
          await Storefront.apiFetch("/reviews/questions/", {
            method: "POST",
            body: JSON.stringify({ product: Number(productId), question: questionText.value }),
          });
          questionForm.reset();
          loadQuestions();
        } catch (err) {
          Storefront.showError(questionError, err.message);
        }
      });
    }

    loadQuestions();
  }

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
      const originalHtml = addBtn.innerHTML;
      addBtn.innerHTML = '<span class="spinner"></span> Adding...';
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
        setTimeout(() => (addBtn.innerHTML = originalHtml), 2000);
      } catch (err) {
        Storefront.showError(errorEl, err.message);
        addBtn.innerHTML = originalHtml;
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
