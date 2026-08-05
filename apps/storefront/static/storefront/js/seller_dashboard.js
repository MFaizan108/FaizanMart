(function () {
  const loadingEl = document.getElementById("stats-loading");
  const gridEl = document.getElementById("stats-grid");
  const errorEl = document.getElementById("stats-error");

  function card(label, value, accentClass) {
    const div = document.createElement("div");
    div.className = "card hover-lift p-4";
    div.innerHTML = `<p class="text-xs text-black/50">${label}</p><p class="mt-1 text-2xl font-bold ${accentClass || "text-secondary"}">${value}</p>`;
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
      gridEl.appendChild(card("Revenue", fmt(stats.revenue), "text-brand"));
      gridEl.appendChild(card("Total Orders", stats.total_orders ?? 0));
      gridEl.appendChild(card("Pending Orders", stats.pending_orders ?? 0, "text-accent"));
      gridEl.appendChild(card("Avg. Order Value", fmt(stats.average_order_value)));
      gridEl.appendChild(card("Products", stats.product_count ?? 0));
      gridEl.appendChild(card("Customers", stats.customer_count ?? 0));

      renderSalesChart(stats.monthly_sales || []);
    })
    .catch((err) => {
      loadingEl.classList.add("hidden");
      errorEl.textContent = err.message;
      errorEl.classList.remove("hidden");
    });

  function renderSalesChart(months) {
    const chartLoading = document.getElementById("sales-chart-loading");
    const chartEl = document.getElementById("sales-chart");
    chartLoading.classList.add("hidden");
    chartEl.classList.remove("hidden");
    chartEl.classList.add("flex");

    const max = Math.max(...months.map((m) => m.total), 1);
    months.forEach((month) => {
      const col = document.createElement("div");
      col.className = "flex flex-1 flex-col items-center gap-2";
      const barWrap = document.createElement("div");
      barWrap.className = "flex h-32 w-full items-end";
      const bar = document.createElement("div");
      bar.className = "hover-lift w-full rounded-t-md bg-gradient-to-t from-brand to-brand-dark";
      bar.style.height = Math.max((month.total / max) * 100, month.total > 0 ? 4 : 0) + "%";
      bar.title = fmt(month.total);
      barWrap.appendChild(bar);
      const label = document.createElement("span");
      label.className = "text-[11px] text-black/40";
      label.textContent = month.label;
      col.append(barWrap, label);
      chartEl.appendChild(col);
    });
  }

  /* ---- Low stock ---- */
  (function loadLowStock() {
    const loading = document.getElementById("low-stock-loading");
    const emptyEl = document.getElementById("low-stock-empty");
    const listEl = document.getElementById("low-stock-list");
    const template = document.getElementById("low-stock-row-template");

    Storefront.apiFetch("/inventory/stock/?page_size=200")
      .then((data) => {
        loading.classList.add("hidden");
        const rows = (data.results || data).filter((s) => s.is_low_stock);
        if (!rows.length) {
          emptyEl.classList.remove("hidden");
          emptyEl.classList.add("flex");
          return;
        }
        rows.slice(0, 8).forEach((stock) => {
          const node = template.content.cloneNode(true);
          node.querySelector(".low-stock-name").textContent = stock.product_name;
          node.querySelector(".low-stock-qty").textContent = stock.available_quantity + " left";
          listEl.appendChild(node);
        });
      })
      .catch(() => {
        loading.textContent = "Could not load stock levels.";
      });
  })();

  /* ---- Best selling products ---- */
  (function loadBestSelling() {
    const loading = document.getElementById("best-selling-loading");
    const emptyEl = document.getElementById("best-selling-empty");
    const wrapEl = document.getElementById("best-selling-wrap");
    const bodyEl = document.getElementById("best-selling-body");
    const template = document.getElementById("best-selling-row-template");

    Storefront.apiFetch("/analytics/reports/products/")
      .then((rows) => {
        loading.classList.add("hidden");
        if (!rows.length) {
          emptyEl.classList.remove("hidden");
          emptyEl.classList.add("flex");
          return;
        }
        wrapEl.classList.remove("hidden");
        rows.slice(0, 10).forEach((row) => {
          const node = template.content.cloneNode(true);
          const cells = node.querySelectorAll("td");
          cells[0].textContent = row.product_name;
          cells[1].textContent = row.units_sold;
          cells[2].textContent = fmt(row.revenue);
          bodyEl.appendChild(node);
        });
      })
      .catch(() => {
        loading.textContent = "Could not load product performance.";
      });
  })();
})();
