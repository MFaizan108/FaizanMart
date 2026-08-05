(function () {
  const raw = sessionStorage.getItem("lastOrderResult");
  sessionStorage.removeItem("lastOrderResult");

  const knownEl = document.getElementById("order-success-known");
  const fallbackEl = document.getElementById("order-success-fallback");
  const orderListEl = document.getElementById("order-list");
  const rowTemplate = document.getElementById("order-row-template");
  const viewOrderBtn = document.getElementById("view-order-btn");

  let orders = [];
  try {
    orders = raw ? JSON.parse(raw) : [];
  } catch (err) {
    orders = [];
  }

  if (!Array.isArray(orders) || orders.length === 0) {
    fallbackEl.classList.remove("hidden");
    fallbackEl.classList.add("flex");
    return;
  }

  knownEl.classList.remove("hidden");
  knownEl.classList.add("flex");

  orders.forEach((order) => {
    const node = rowTemplate.content.cloneNode(true);
    node.querySelector(".order-number").textContent = `${order.order_number} — Sold by ${order.store_name}`;
    node.querySelector(".order-status").textContent = order.status;
    orderListEl.appendChild(node);
  });

  if (orders.length === 1) {
    viewOrderBtn.href = "/orders/" + orders[0].id + "/";
    viewOrderBtn.classList.remove("hidden");
  }
})();
