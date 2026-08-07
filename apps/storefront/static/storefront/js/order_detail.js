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
      cancelBtn.addEventListener("click", async () => {
        if (!confirm("Cancel this order? This cannot be undone.")) return;
        const reason = prompt("Reason for cancelling (optional):") || "";
        const cancelErrorEl = document.getElementById("cancel-error");
        cancelBtn.disabled = true;
        try {
          await Storefront.apiFetch(`/orders/orders/${orderId}/cancel/`, {
            method: "POST",
            body: JSON.stringify({ reason }),
          });
          Storefront.toast("Order cancelled", "success");
          window.location.reload();
        } catch (err) {
          cancelErrorEl.textContent = err.message;
          cancelErrorEl.classList.remove("hidden");
          cancelBtn.disabled = false;
        }
      });
    }

    node.querySelector(".items-heading").textContent = "Items from " + order.store_name;
    const itemsList = node.querySelector(".items-list");
    order.items.forEach((item) => {
      const row = document.createElement("div");
      row.className = "flex justify-between py-2 text-sm";
      row.innerHTML = `<span>${Storefront.escapeHtml(item.product_name)} &times; ${item.quantity}</span><span>${fmt(item.line_total)}</span>`;
      itemsList.appendChild(row);
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
