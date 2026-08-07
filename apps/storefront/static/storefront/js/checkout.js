(function () {
  const loadingEl = document.getElementById("checkout-loading");
  const emptyEl = document.getElementById("checkout-empty");
  const contentEl = document.getElementById("checkout-content");
  const addressList = document.getElementById("address-list");
  const addressTemplate = document.getElementById("address-option-template");
  const toggleAddressFormBtn = document.getElementById("toggle-address-form");
  const addressForm = document.getElementById("address-form");
  const summaryItems = document.getElementById("summary-items");
  const summarySubtotal = document.getElementById("summary-subtotal");
  const summaryShipping = document.getElementById("summary-shipping");
  const summaryTotal = document.getElementById("summary-total");
  const summaryShippingNote = document.getElementById("summary-shipping-note");
  const placeOrderBtn = document.getElementById("place-order-btn");
  const errorEl = document.getElementById("checkout-error");
  const reviewAddressEl = document.getElementById("review-address");

  let selectedAddressId = null;
  let selectedAddressText = "";
  let selectedAddress = null;
  let cartByStore = [];

  /* ---- Live delivery-charge estimate ----
   * The server always recomputes shipping for real at checkout (never trusts a client
   * value) — this just previews it here so the customer isn't surprised at placement,
   * using the same per-store shipping-rules engine via /shipping/quote/. */
  async function updateShippingEstimate() {
    if (!selectedAddress || !cartByStore.length) {
      summaryShipping.textContent = "—";
      return;
    }
    summaryShipping.textContent = "Calculating…";
    try {
      const quotes = await Promise.all(
        cartByStore.map((group) =>
          Storefront.apiFetch("/shipping/quote/", {
            method: "POST",
            body: JSON.stringify({
              country: selectedAddress.country,
              province: selectedAddress.state || "",
              city: selectedAddress.city || "",
              store: group.storeId,
              order_amount: group.subtotal,
            }),
          })
        )
      );
      const allMatched = quotes.every((q) => q.matched);
      const shippingTotal = quotes.reduce((sum, q) => sum + Number(q.shipping_cost || 0), 0);
      const cartSubtotal = cartByStore.reduce((sum, g) => sum + g.subtotal, 0);
      summaryShipping.textContent = "Rs " + Math.round(shippingTotal).toLocaleString("en-PK");
      summaryTotal.textContent = Math.round(cartSubtotal + shippingTotal).toLocaleString("en-PK");
      summaryShippingNote.textContent = allMatched
        ? "Delivery charges shown are calculated for your address; any discount is applied when you place the order."
        : "Delivery charges for some items will be confirmed when you place the order.";
    } catch (err) {
      summaryShipping.textContent = "—";
    }
  }
  const STEPS = ["address", "payment", "review"];
  let currentStep = "address";

  /* ---- Step navigation ---- */
  function goToStep(step) {
    currentStep = step;
    document.querySelectorAll(".checkout-panel").forEach((panel) => {
      panel.classList.toggle("hidden", panel.id !== "step-" + step);
      panel.classList.toggle("flex", panel.id === "step-" + step);
    });
    document.querySelectorAll(".checkout-step").forEach((li) => {
      const dot = li.querySelector(".step-dot");
      const label = li.querySelector(".step-label");
      const stepIndex = STEPS.indexOf(li.dataset.step);
      const targetIndex = STEPS.indexOf(step);
      const isActive = li.dataset.step === step;
      const isDone = stepIndex < targetIndex;
      dot.classList.toggle("bg-brand", isActive || isDone);
      dot.classList.toggle("text-white", isActive || isDone);
      dot.classList.toggle("bg-black/10", !isActive && !isDone);
      label.classList.toggle("text-black", isActive);
      label.classList.toggle("text-black/40", !isActive);
    });
    placeOrderBtn.classList.toggle("hidden", step !== "review");
    if (step === "review") {
      reviewAddressEl.textContent = selectedAddressText;
    }
  }

  document.querySelectorAll(".step-next-btn").forEach((btn) => {
    btn.addEventListener("click", () => goToStep(btn.dataset.next));
  });
  document.querySelectorAll(".step-back-btn").forEach((btn) => {
    btn.addEventListener("click", () => goToStep(btn.dataset.back));
  });

  const continueToPaymentBtn = document.querySelector('.step-next-btn[data-next="payment"]');

  function renderAddresses(addresses) {
    addressList.innerHTML = "";
    addresses.forEach((address) => {
      const node = addressTemplate.content.cloneNode(true);
      const radio = node.querySelector(".address-radio");
      radio.checked = address.id === selectedAddressId;
      const lineText = `${address.address_line1}, ${address.city}, ${address.country}`;
      radio.addEventListener("change", () => {
        selectedAddressId = address.id;
        selectedAddressText = `${address.full_name} — ${lineText}`;
        selectedAddress = address;
        continueToPaymentBtn.disabled = false;
        updateShippingEstimate();
      });
      node.querySelector(".address-label").textContent = `${address.label || "Address"} — ${address.full_name}`;
      node.querySelector(".address-line").textContent = lineText;
      addressList.appendChild(node);
    });
  }

  toggleAddressFormBtn.addEventListener("click", () => {
    addressForm.classList.toggle("hidden");
    addressForm.classList.toggle("flex");
  });

  addressForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(addressForm);
    try {
      const address = await Storefront.apiFetch("/auth/addresses/", {
        method: "POST",
        body: JSON.stringify({
          label: "Home",
          full_name: formData.get("full_name"),
          phone_number: formData.get("phone_number"),
          address_line1: formData.get("address_line1"),
          address_line2: "",
          city: formData.get("city"),
          state: formData.get("state") || "",
          postal_code: "",
          country: formData.get("country"),
          address_type: "shipping",
          is_default_shipping: true,
          is_default_billing: true,
        }),
      });
      selectedAddressId = address.id;
      selectedAddressText = `${address.full_name} — ${address.address_line1}, ${address.city}, ${address.country}`;
      selectedAddress = address;
      continueToPaymentBtn.disabled = false;
      addressForm.reset();
      addressForm.classList.add("hidden");
      addressForm.classList.remove("flex");
      const addresses = await Storefront.apiFetch("/auth/addresses/");
      renderAddresses(addresses.results);
      updateShippingEstimate();
    } catch (err) {
      Storefront.showError(errorEl, err.message);
    }
  });

  placeOrderBtn.addEventListener("click", async () => {
    if (!selectedAddressId) return;
    Storefront.hideError(errorEl);
    placeOrderBtn.disabled = true;
    placeOrderBtn.innerHTML = '<span class="spinner"></span> Placing order...';
    try {
      const payload = {
        shipping_address_id: selectedAddressId,
        billing_same_as_shipping: true,
        payment_method: "cod",
      };
      const couponCode = document.getElementById("coupon-code").value.trim();
      if (couponCode) payload.coupon_code = couponCode;

      const result = await Storefront.apiFetch("/orders/checkout/", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      const orders = Array.isArray(result) ? result : result.orders || [];
      sessionStorage.setItem("lastOrderResult", JSON.stringify(orders));
      window.location.href = "/checkout/success/";
    } catch (err) {
      Storefront.showError(errorEl, err.message);
      placeOrderBtn.disabled = false;
      placeOrderBtn.textContent = "Place order";
    }
  });

  async function init() {
    try {
      const [addressesData, cart] = await Promise.all([
        Storefront.apiFetch("/auth/addresses/"),
        Storefront.apiFetch("/cart/"),
      ]);
      loadingEl.classList.add("hidden");

      if (cart.items.length === 0) {
        emptyEl.classList.remove("hidden");
        emptyEl.classList.add("flex");
        return;
      }
      contentEl.classList.remove("hidden");
      contentEl.classList.add("flex");

      cart.items.forEach((item) => {
        const row = document.createElement("div");
        row.className = "flex justify-between";
        row.innerHTML = `<span>${Storefront.escapeHtml(item.product.name)} &times; ${item.quantity}</span><span>Rs ${Math.round(item.line_total).toLocaleString("en-PK")}</span>`;
        summaryItems.appendChild(row);
      });
      summarySubtotal.textContent = Math.round(cart.subtotal).toLocaleString("en-PK");
      summaryTotal.textContent = Math.round(cart.subtotal).toLocaleString("en-PK");

      const storeGroups = new Map();
      cart.items.forEach((item) => {
        const storeId = item.product.store_id;
        storeGroups.set(storeId, (storeGroups.get(storeId) || 0) + Number(item.line_total));
      });
      cartByStore = Array.from(storeGroups, ([storeId, subtotal]) => ({ storeId, subtotal }));

      const addresses = addressesData.results;
      const preferred = addresses.find((a) => a.is_default_shipping) || addresses[0];
      if (preferred) {
        selectedAddressId = preferred.id;
        selectedAddressText = `${preferred.full_name} — ${preferred.address_line1}, ${preferred.city}, ${preferred.country}`;
        selectedAddress = preferred;
        continueToPaymentBtn.disabled = false;
        updateShippingEstimate();
      } else {
        addressForm.classList.remove("hidden");
        addressForm.classList.add("flex");
      }
      renderAddresses(addresses);
      goToStep("address");
    } catch (err) {
      loadingEl.textContent = "Could not load checkout.";
    }
  }

  init();
})();
