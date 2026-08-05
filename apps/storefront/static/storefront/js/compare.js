/* Client-side product comparison list (localStorage only — no backend model,
 * this is purely a browsing convenience, not business data). Max 4 products. */
(function () {
  const STORAGE_KEY = "faizanmart_compare";
  const MAX_ITEMS = 4;

  function getList() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      const list = raw ? JSON.parse(raw) : [];
      return Array.isArray(list) ? list : [];
    } catch (err) {
      return [];
    }
  }

  function setList(list) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
    renderBar();
    syncButtons();
  }

  function isCompared(id) {
    return getList().includes(Number(id));
  }

  function toggle(id) {
    id = Number(id);
    let list = getList();
    if (list.includes(id)) {
      list = list.filter((x) => x !== id);
      setList(list);
      if (window.Storefront) Storefront.toast("Removed from compare", "info");
      return true;
    }
    if (list.length >= MAX_ITEMS) {
      if (window.Storefront) Storefront.toast(`You can compare up to ${MAX_ITEMS} products at a time.`, "error");
      return false;
    }
    list.push(id);
    setList(list);
    if (window.Storefront) Storefront.toast("Added to compare", "success");
    return true;
  }

  function clearAll() {
    setList([]);
  }

  function syncButtons() {
    const list = getList();
    document.querySelectorAll(".compare-btn").forEach((btn) => {
      const id = Number(btn.dataset.productId);
      const active = list.includes(id);
      btn.classList.toggle("text-brand", active);
      btn.setAttribute("aria-pressed", active ? "true" : "false");
    });
  }

  function renderBar() {
    const bar = document.getElementById("compare-bar");
    const itemsEl = document.getElementById("compare-bar-items");
    if (!bar || !itemsEl) return;
    const list = getList();

    if (list.length === 0) {
      bar.classList.add("hidden", "translate-y-full");
      return;
    }
    bar.classList.remove("hidden");
    requestAnimationFrame(() => bar.classList.remove("translate-y-full"));
    itemsEl.textContent = `${list.length} product${list.length > 1 ? "s" : ""} selected`;
  }

  document.addEventListener("click", (event) => {
    const btn = event.target.closest(".compare-btn");
    if (btn) {
      event.preventDefault();
      event.stopPropagation();
      toggle(btn.dataset.productId);
      return;
    }
    if (event.target.closest("#compare-clear-btn")) {
      clearAll();
    }
  });

  renderBar();
  syncButtons();

  window.Compare = { getList, toggle, isCompared, clearAll };
})();
