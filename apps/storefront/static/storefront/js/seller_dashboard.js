(function () {
  const loadingEl = document.getElementById("stats-loading");
  const gridEl = document.getElementById("stats-grid");
  const errorEl = document.getElementById("stats-error");

  function card(label, value) {
    const div = document.createElement("div");
    div.className = "card p-4";
    div.innerHTML = `<p class="text-xs text-black/50">${label}</p><p class="mt-1 text-2xl font-bold">${value}</p>`;
    return div;
  }

  function fmt(amount) {
    return "Rs " + Math.round(Number(amount || 0)).toLocaleString("en-PK");
  }

  Storefront.apiFetch("/analytics/vendor/dashboard/")
    .then((stats) => {
      loadingEl.classList.add("hidden");
      gridEl.classList.remove("hidden");
      gridEl.classList.add("grid");
      gridEl.appendChild(card("Revenue", fmt(stats.revenue)));
      gridEl.appendChild(card("Total Orders", stats.total_orders ?? stats.sales_count ?? 0));
      gridEl.appendChild(card("Pending Orders", stats.pending_orders ?? 0));
      gridEl.appendChild(card("Avg. Order Value", fmt(stats.average_order_value)));
    })
    .catch((err) => {
      loadingEl.classList.add("hidden");
      errorEl.textContent = err.message;
      errorEl.classList.remove("hidden");
    });
})();
