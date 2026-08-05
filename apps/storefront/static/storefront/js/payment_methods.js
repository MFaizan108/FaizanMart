(function () {
  const loadingEl = document.getElementById("payment-methods-loading");
  const emptyEl = document.getElementById("payment-methods-empty");
  const listEl = document.getElementById("payment-methods-list");
  const errorEl = document.getElementById("payment-methods-error");
  const template = document.getElementById("payment-method-card-template");

  function renderCard(method) {
    const node = template.content.cloneNode(true);
    node.querySelector(".card-brand").textContent = method.card_brand || method.provider;
    node.querySelector(".card-number").textContent = "•••• •••• •••• " + (method.card_last4 || "----");
    node.querySelector(".card-expiry").textContent = method.card_exp_month
      ? `Expires ${String(method.card_exp_month).padStart(2, "0")}/${method.card_exp_year}`
      : "";

    const badges = node.querySelector(".default-badges");
    const setDefaultBtn = node.querySelector(".set-default-btn");
    if (method.is_default) {
      const b = document.createElement("span");
      b.className = "badge badge-new";
      b.textContent = "Default";
      badges.appendChild(b);
      setDefaultBtn.remove();
    } else {
      setDefaultBtn.addEventListener("click", async () => {
        try {
          await Storefront.apiFetch(`/payments/payment-methods/${method.id}/set-default/`, { method: "POST" });
          load();
        } catch (err) {
          Storefront.showError(errorEl, err.message);
        }
      });
    }

    node.querySelector(".remove-btn").addEventListener("click", async (event) => {
      try {
        await Storefront.apiFetch(`/payments/payment-methods/${method.id}/`, { method: "DELETE" });
        event.target.closest(".card").remove();
        if (!listEl.children.length) {
          emptyEl.classList.remove("hidden");
          emptyEl.classList.add("flex");
        }
      } catch (err) {
        Storefront.showError(errorEl, err.message);
      }
    });
    return node;
  }

  async function load() {
    loadingEl.classList.remove("hidden");
    listEl.innerHTML = "";
    emptyEl.classList.add("hidden");
    Storefront.hideError(errorEl);
    try {
      const data = await Storefront.apiFetch("/payments/payment-methods/");
      loadingEl.classList.add("hidden");
      const results = data.results || data;
      if (!results.length) {
        emptyEl.classList.remove("hidden");
        emptyEl.classList.add("flex");
        return;
      }
      results.forEach((method) => listEl.appendChild(renderCard(method)));
    } catch (err) {
      loadingEl.classList.add("hidden");
      Storefront.showError(errorEl, err.message);
    }
  }

  load();
})();
