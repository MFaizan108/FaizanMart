(function () {
  const loadingEl = document.getElementById("orders-loading");
  const emptyEl = document.getElementById("orders-empty");
  const listEl = document.getElementById("orders-list");
  const errorEl = document.getElementById("orders-error");
  const template = document.getElementById("seller-order-row-template");

  const NEXT_STATUSES = {
    pending: ["processing", "cancelled"],
    processing: ["packed", "cancelled"],
    packed: ["shipped", "cancelled"],
    shipped: ["delivered"],
    delivered: ["returned"],
    returned: ["refunded"],
    cancelled: [],
    refunded: [],
  };

  const STATUS_BADGE = {
    pending: "badge-warning",
    processing: "badge-warning",
    packed: "badge-warning",
    shipped: "badge-accent",
    delivered: "badge-new",
    returned: "badge-outofstock",
    refunded: "badge-outofstock",
    cancelled: "badge-sale",
  };

  function fmt(amount) {
    return "Rs " + Math.round(Number(amount)).toLocaleString("en-PK");
  }

  function renderRow(order) {
    const node = template.content.cloneNode(true);
    node.querySelector(".order-link").textContent = order.order_number;
    node.querySelector(".order-link").href = "/orders/" + order.id + "/";
    node.querySelector(".order-meta").textContent =
      `${order.customer_email} · ${fmt(order.total_amount)} · ${new Date(order.created_at).toLocaleDateString()}`;

    const badge = node.querySelector(".status-badge");
    badge.textContent = order.status;
    badge.classList.add(STATUS_BADGE[order.status] || "badge-outofstock");

    const select = node.querySelector(".next-status-select");
    const applyBtn = node.querySelector(".apply-status-btn");
    const options = NEXT_STATUSES[order.status] || [];
    if (options.length === 0) {
      select.remove();
      applyBtn.remove();
    } else {
      options.forEach((status) => {
        const opt = document.createElement("option");
        opt.value = status;
        opt.textContent = "Mark as " + status;
        select.appendChild(opt);
      });
      applyBtn.addEventListener("click", async () => {
        applyBtn.disabled = true;
        try {
          await Storefront.apiFetch(`/orders/orders/${order.id}/transition/`, {
            method: "POST",
            body: JSON.stringify({ status: select.value }),
          });
          load();
        } catch (err) {
          Storefront.showError(errorEl, err.message);
          applyBtn.disabled = false;
        }
      });
    }

    return node;
  }

  async function load() {
    loadingEl.classList.remove("hidden");
    listEl.innerHTML = "";
    emptyEl.classList.add("hidden");
    Storefront.hideError(errorEl);
    try {
      const data = await Storefront.apiFetch("/orders/orders/?page_size=100");
      loadingEl.classList.add("hidden");
      const results = data.results || data;
      if (!results.length) {
        emptyEl.classList.remove("hidden");
        emptyEl.classList.add("flex");
        return;
      }
      results.forEach((order) => listEl.appendChild(renderRow(order)));
    } catch (err) {
      loadingEl.classList.add("hidden");
      Storefront.showError(errorEl, err.message);
    }
  }

  load();
})();
