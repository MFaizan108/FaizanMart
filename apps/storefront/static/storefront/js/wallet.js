(function () {
  const balanceEl = document.getElementById("wallet-balance");
  const errorEl = document.getElementById("wallet-error");
  const loadingEl = document.getElementById("transactions-loading");
  const emptyEl = document.getElementById("transactions-empty");
  const listEl = document.getElementById("transactions-list");
  const template = document.getElementById("transaction-template");

  function fmt(amount) {
    return "Rs " + Math.round(Number(amount)).toLocaleString("en-PK");
  }

  function renderTx(tx) {
    const node = template.content.cloneNode(true);
    node.querySelector(".tx-reason").textContent = tx.reason || tx.transaction_type;
    node.querySelector(".tx-date").textContent = new Date(tx.created_at).toLocaleString();
    const amountEl = node.querySelector(".tx-amount");
    const credit = tx.transaction_type === "credit";
    amountEl.textContent = (credit ? "+ " : "- ") + fmt(tx.amount);
    amountEl.className = "tx-amount font-semibold " + (credit ? "text-brand" : "text-red-600");
    return node;
  }

  async function loadWallet() {
    try {
      const wallet = await Storefront.apiFetch("/payments/wallet/");
      balanceEl.textContent = fmt(wallet.balance);
    } catch (err) {
      Storefront.showError(errorEl, err.message);
    }
  }

  async function loadTransactions() {
    try {
      const data = await Storefront.apiFetch("/payments/wallet/transactions/");
      loadingEl.classList.add("hidden");
      if (data.results.length === 0) {
        emptyEl.classList.remove("hidden");
        emptyEl.classList.add("flex");
        return;
      }
      data.results.forEach((tx) => listEl.appendChild(renderTx(tx)));
    } catch (err) {
      loadingEl.textContent = "Could not load transactions.";
    }
  }

  document.getElementById("add-money-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    Storefront.hideError(errorEl);
    const input = document.getElementById("add-money-amount");
    const amount = Number(input.value);
    if (!amount || amount <= 0) return;
    try {
      await Storefront.apiFetch("/payments/wallet/add-money/", {
        method: "POST",
        body: JSON.stringify({ amount, reason: "Wallet top-up" }),
      });
      input.value = "";
      listEl.innerHTML = "";
      emptyEl.classList.add("hidden");
      emptyEl.classList.remove("flex");
      await Promise.all([loadWallet(), loadTransactions()]);
    } catch (err) {
      Storefront.showError(errorEl, err.message);
    }
  });

  loadWallet();
  loadTransactions();
})();
