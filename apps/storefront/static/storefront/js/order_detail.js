(function () {
  const root = document.getElementById("order-root");
  const orderId = root.dataset.orderId;
  const loadingEl = document.getElementById("order-loading");
  const errorEl = document.getElementById("order-error");
  const contentEl = document.getElementById("order-content");
  const template = document.getElementById("order-content-template");

  function fmt(amount) {
    return "Rs " + Math.round(Number(amount)).toLocaleString("en-PK");
  }

  const CANCELLABLE_STATUSES = ["pending", "processing", "packed"];

  /* ---- Cancel-order modal ---- */
  const cancelBackdrop = document.getElementById("cancel-modal-backdrop");
  const cancelReasonForm = document.getElementById("cancel-reason-form");
  const cancelReasonOther = document.getElementById("cancel-reason-other");
  const cancelModalError = document.getElementById("cancel-modal-error");
  const cancelModalConfirm = document.getElementById("cancel-modal-confirm");
  const cancelModalClose = document.getElementById("cancel-modal-close");

  function openCancelModal() {
    cancelReasonForm.reset();
    cancelReasonOther.value = "";
    cancelReasonOther.classList.add("hidden");
    Storefront.hideError(cancelModalError);
    cancelBackdrop.classList.remove("invisible", "opacity-0");
  }
  function closeCancelModal() {
    cancelBackdrop.classList.add("invisible", "opacity-0");
  }
  cancelModalClose.addEventListener("click", closeCancelModal);
  cancelBackdrop.addEventListener("click", (event) => {
    if (event.target === cancelBackdrop) closeCancelModal();
  });
  cancelReasonForm.addEventListener("change", (event) => {
    if (event.target.name === "cancel_reason") {
      cancelReasonOther.classList.toggle("hidden", event.target.value !== "other");
    }
  });

  /* ---- Post-delivery review widget ---- */
  function renderStars(container, selected, onSelect) {
    container.innerHTML = "";
    for (let i = 1; i <= 5; i++) {
      const star = document.createElement("button");
      star.type = "button";
      star.textContent = i <= selected ? "★" : "☆";
      star.className = "text-accent";
      star.setAttribute("aria-label", `${i} star${i > 1 ? "s" : ""}`);
      star.addEventListener("click", () => onSelect(i));
      container.appendChild(star);
    }
  }

  function openReviewForm(widget, productId, existing) {
    widget.innerHTML = `
      <div class="flex flex-col gap-2 rounded-lg border border-black/10 p-3">
        <div class="review-stars flex gap-0.5 text-lg leading-none"></div>
        <textarea class="review-comment w-full rounded-md border border-black/15 px-2 py-1.5 text-sm" rows="2" placeholder="Share your experience (optional)"></textarea>
        <div class="flex gap-2">
          <button type="button" class="review-submit-btn btn-primary !px-3 !py-1 text-xs"></button>
          <button type="button" class="review-cancel-btn btn-secondary !px-3 !py-1 text-xs">Cancel</button>
        </div>
        <p class="review-error hidden text-xs text-danger"></p>
      </div>`;
    const starsEl = widget.querySelector(".review-stars");
    const commentEl = widget.querySelector(".review-comment");
    const submitBtn = widget.querySelector(".review-submit-btn");
    commentEl.value = existing ? existing.comment : "";
    submitBtn.textContent = existing ? "Update review" : "Submit review";
    let selected = existing ? existing.rating : 5;
    function updateStars() {
      renderStars(starsEl, selected, (value) => {
        selected = value;
        updateStars();
      });
    }
    updateStars();

    widget.querySelector(".review-cancel-btn").addEventListener("click", () => setupReviewWidget(widget, productId));
    submitBtn.addEventListener("click", async () => {
      const errorEl = widget.querySelector(".review-error");
      Storefront.hideError(errorEl);
      submitBtn.disabled = true;
      try {
        if (existing) {
          await Storefront.apiFetch(`/reviews/reviews/${existing.id}/`, {
            method: "PATCH",
            body: JSON.stringify({ rating: selected, comment: commentEl.value.trim() }),
          });
        } else {
          await Storefront.apiFetch("/reviews/reviews/", {
            method: "POST",
            body: JSON.stringify({ product: productId, rating: selected, comment: commentEl.value.trim() }),
          });
        }
        Storefront.toast("Thanks for your review!", "success");
        setupReviewWidget(widget, productId);
      } catch (err) {
        Storefront.showError(errorEl, err.message);
      } finally {
        submitBtn.disabled = false;
      }
    });
  }

  function setupReviewWidget(widget, productId) {
    widget.innerHTML = '<button type="button" class="review-toggle-btn text-xs font-medium text-brand hover:underline">Write a review</button>';
    const toggleBtn = widget.querySelector(".review-toggle-btn");
    Storefront.apiFetch(`/reviews/reviews/?product=${productId}&mine=true`)
      .then((data) => {
        const existing = (data.results || data)[0] || null;
        if (existing) {
          toggleBtn.textContent = "★".repeat(existing.rating) + "☆".repeat(5 - existing.rating) + " · Edit your review";
        }
        toggleBtn.addEventListener("click", () => openReviewForm(widget, productId, existing));
      })
      .catch(() => {
        toggleBtn.addEventListener("click", () => openReviewForm(widget, productId, null));
      });
  }

  function render(order) {
    const node = template.content.cloneNode(true);
    node.querySelector(".order-number").textContent = order.order_number;
    node.querySelector(".order-status").textContent = order.status;

    if (order.status === "delivered") {
      node.querySelector(".request-return-link").classList.remove("hidden");
    }

    if (CANCELLABLE_STATUSES.includes(order.status)) {
      const cancelBtn = node.querySelector(".cancel-order-btn");
      cancelBtn.classList.remove("hidden");
      cancelBtn.addEventListener("click", openCancelModal);

      cancelModalConfirm.onclick = async () => {
        const checked = cancelReasonForm.querySelector('input[name="cancel_reason"]:checked');
        if (!checked) {
          Storefront.showError(cancelModalError, "Please select a reason.");
          return;
        }
        const reason = checked.value === "other" ? cancelReasonOther.value.trim() : checked.value;
        if (checked.value === "other" && !reason) {
          Storefront.showError(cancelModalError, "Please tell us your reason.");
          return;
        }
        Storefront.hideError(cancelModalError);
        cancelModalConfirm.disabled = true;
        try {
          await Storefront.apiFetch(`/orders/orders/${orderId}/cancel/`, {
            method: "POST",
            body: JSON.stringify({ reason }),
          });
          closeCancelModal();
          Storefront.toast("Order cancelled — a confirmation email is on its way.", "success");
          window.location.reload();
        } catch (err) {
          Storefront.showError(cancelModalError, err.message);
        } finally {
          cancelModalConfirm.disabled = false;
        }
      };
    }

    node.querySelector(".items-heading").textContent = "Items from " + order.store_name;
    const itemsList = node.querySelector(".items-list");
    order.items.forEach((item) => {
      const itemWrap = document.createElement("div");
      itemWrap.className = "py-2";
      const row = document.createElement("div");
      row.className = "flex justify-between text-sm";
      row.innerHTML = `<span>${Storefront.escapeHtml(item.product_name)} &times; ${item.quantity}</span><span>${fmt(item.line_total)}</span>`;
      itemWrap.appendChild(row);
      if (order.status === "delivered" && item.product) {
        const widget = document.createElement("div");
        widget.className = "mt-1";
        itemWrap.appendChild(widget);
        setupReviewWidget(widget, item.product);
      }
      itemsList.appendChild(itemWrap);
    });

    const totals = node.querySelector(".totals");
    const rows = [["Subtotal", fmt(order.subtotal)], ["Shipping", fmt(order.shipping_cost)]];
    if (Number(order.discount_amount) > 0) rows.push(["Discount", "-" + fmt(order.discount_amount)]);
    rows.push(["Total", fmt(order.total_amount)]);
    rows.forEach(([label, value], index) => {
      const row = document.createElement("div");
      row.className = "flex justify-between" + (index === rows.length - 1 ? " font-semibold" : "");
      row.innerHTML = `<span>${label}</span><span>${value}</span>`;
      totals.appendChild(row);
    });

    const esc = Storefront.escapeHtml;
    node.querySelector(".shipping-address").innerHTML =
      `${esc(order.shipping_full_name)} &middot; ${esc(order.shipping_phone)}<br>` +
      `${esc(order.shipping_address_line)}, ${esc(order.shipping_city)} ${esc(order.shipping_state)}<br>${esc(order.shipping_country)}`;
    node.querySelector(".payment-line").innerHTML =
      `Payment: <span class="capitalize">${esc(order.payment_method)}</span> &middot; <span class="capitalize">${esc(order.payment_status)}</span>`;

    const historyEl = node.querySelector(".status-history");
    order.status_history.forEach((entry) => {
      const row = document.createElement("div");
      row.className = "flex justify-between";
      row.innerHTML = `<span class="capitalize">${esc(entry.status)}</span><span class="text-black/50">${new Date(entry.created_at).toLocaleString()}</span>`;
      historyEl.appendChild(row);
    });

    contentEl.innerHTML = "";
    contentEl.appendChild(node);
    contentEl.classList.remove("hidden");
    contentEl.classList.add("flex");
  }

  Storefront.apiFetch(`/orders/orders/${orderId}/`)
    .then((order) => {
      loadingEl.classList.add("hidden");
      render(order);
    })
    .catch((err) => {
      loadingEl.classList.add("hidden");
      errorEl.textContent = err.status === 404 ? "Order not found." : err.message;
      errorEl.classList.remove("hidden");
    });
})();
