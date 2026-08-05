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
  const placeOrderBtn = document.getElementById("place-order-btn");
  const errorEl = document.getElementById("checkout-error");
  const reviewAddressEl = document.getElementById("review-address");

  let selectedAddressId = null;
  let selectedAddressText = "";
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
        continueToPaymentBtn.disabled = false;
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
      continueToPaymentBtn.disabled = false;
      addressForm.reset();
      addressForm.classList.add("hidden");
      addressForm.classList.remove("flex");
      const addresses = await Storefront.apiFetch("/auth/addresses/");
      renderAddresses(addresses.results);
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
        row.innerHTML = `<span>${item.product.name} &times; ${item.quantity}</span><span>Rs ${Math.round(item.line_total).toLocaleString("en-PK")}</span>`;
        summaryItems.appendChild(row);
      });
      summarySubtotal.textContent = Math.round(cart.subtotal).toLocaleString("en-PK");

      const addresses = addressesData.results;
      const preferred = addresses.find((a) => a.is_default_shipping) || addresses[0];
      if (preferred) {
        selectedAddressId = preferred.id;
        selectedAddressText = `${preferred.full_name} — ${preferred.address_line1}, ${preferred.city}, ${preferred.country}`;
        continueToPaymentBtn.disabled = false;
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
