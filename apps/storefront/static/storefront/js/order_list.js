(function () {
  const loadingEl = document.getElementById("orders-loading");
  const emptyEl = document.getElementById("orders-empty");
  const listEl = document.getElementById("orders-list");
  const template = document.getElementById("order-row-template");
  const placedBanner = document.getElementById("placed-banner");

  const placed = new URLSearchParams(window.location.search).get("placed");
  if (placed) {
    placedBanner.textContent = `Order${placed.includes(",") ? "s" : ""} placed: ${placed}`;
    placedBanner.classList.remove("hidden");
  }

  function renderRow(order) {
    const node = template.content.cloneNode(true);
    node.querySelector(".order-link").href = "/orders/" + order.id + "/";
    node.querySelector(".order-number").textContent = order.order_number;
    node.querySelector(".order-meta").textContent =
      order.store_name + " · " + new Date(order.created_at).toLocaleDateString();
    node.querySelector(".order-total").textContent = "Rs " + Math.round(order.total_amount).toLocaleString("en-PK");
    node.querySelector(".order-status").textContent = order.status;
    return node;
  }

  async function load() {
    try {
      const data = await Storefront.apiFetch("/orders/orders/");
      loadingEl.classList.add("hidden");
      if (data.results.length === 0) {
        emptyEl.classList.remove("hidden");
        emptyEl.classList.add("flex");
        return;
      }
      data.results.forEach((order) => listEl.appendChild(renderRow(order)));
    } catch (err) {
      loadingEl.textContent = "Could not load orders.";
    }
  }

  load();
})();
