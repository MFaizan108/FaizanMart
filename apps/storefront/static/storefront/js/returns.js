(function () {
  const loadingEl = document.getElementById("returns-loading");
  const emptyEl = document.getElementById("returns-empty");
  const listEl = document.getElementById("returns-list");
  const errorEl = document.getElementById("returns-error");
  const template = document.getElementById("return-card-template");

  const toggleBtn = document.getElementById("toggle-return-form");
  const form = document.getElementById("return-form");
  const orderSelect = document.getElementById("return-order");
  const reasonInput = document.getElementById("return-reason");
  const formErrorEl = document.getElementById("return-form-error");

  const STATUS_BADGE = {
    requested: "badge-warning",
    approved: "badge-new",
    refunded: "badge-new",
    rejected: "badge-sale",
  };

  toggleBtn.addEventListener("click", async () => {
    const opening = form.classList.contains("hidden");
    form.classList.toggle("hidden");
    form.classList.toggle("flex");
    if (opening) await loadEligibleOrders();
  });

  async function loadEligibleOrders() {
    orderSelect.innerHTML = '<option value="">Loading orders…</option>';
    try {
      const data = await Storefront.apiFetch("/orders/orders/?page_size=100");
      const delivered = (data.results || data).filter((o) => o.status === "delivered");
      orderSelect.innerHTML = '<option value="">Select a delivered order…</option>';
      delivered.forEach((order) => {
        const opt = document.createElement("option");
        opt.value = order.id;
        opt.textContent = `${order.order_number} — ${order.store_name} — Rs ${Math.round(order.total_amount).toLocaleString("en-PK")}`;
        orderSelect.appendChild(opt);
      });
      if (delivered.length === 0) {
        orderSelect.innerHTML = '<option value="">No delivered orders eligible for return</option>';
      }
    } catch (err) {
      orderSelect.innerHTML = '<option value="">Could not load orders</option>';
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    Storefront.hideError(formErrorEl);
    if (!orderSelect.value) return;
    try {
      await Storefront.apiFetch("/orders/returns/", {
        method: "POST",
        body: JSON.stringify({ order: Number(orderSelect.value), reason: reasonInput.value }),
      });
      form.reset();
      form.classList.add("hidden");
      form.classList.remove("flex");
      load();
    } catch (err) {
      Storefront.showError(formErrorEl, err.message);
    }
  });

  function renderCard(request) {
    const node = template.content.cloneNode(true);
    node.querySelector(".order-number").textContent = request.order_number;
    node.querySelector(".store-name").textContent = "Sold by " + request.store_name;
    node.querySelector(".reason-text").textContent = request.reason;
    node.querySelector(".request-date").textContent = new Date(request.created_at).toLocaleDateString();

    const badge = node.querySelector(".status-badge");
    badge.textContent = request.status;
    badge.classList.add(STATUS_BADGE[request.status] || "badge-outofstock");

    if (request.staff_note) {
      const noteEl = node.querySelector(".staff-note");
      noteEl.textContent = "Note from seller/support: " + request.staff_note;
      noteEl.classList.remove("hidden");
    }
    return node;
  }

  async function load() {
    loadingEl.classList.remove("hidden");
    listEl.innerHTML = "";
    emptyEl.classList.add("hidden");
    Storefront.hideError(errorEl);
    try {
      const data = await Storefront.apiFetch("/orders/returns/");
      loadingEl.classList.add("hidden");
      const results = data.results || data;
      if (!results.length) {
        emptyEl.classList.remove("hidden");
        emptyEl.classList.add("flex");
        return;
      }
      results.forEach((request) => listEl.appendChild(renderCard(request)));
    } catch (err) {
      loadingEl.classList.add("hidden");
      Storefront.showError(errorEl, err.message);
    }
  }

  load();
})();
