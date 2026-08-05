(function () {
  const loadingEl = document.getElementById("addresses-loading");
  const emptyEl = document.getElementById("addresses-empty");
  const listEl = document.getElementById("addresses-list");
  const template = document.getElementById("address-card-template");
  const toggleBtn = document.getElementById("toggle-address-form");
  const form = document.getElementById("address-form");
  const errorEl = document.getElementById("address-error");

  toggleBtn.addEventListener("click", () => {
    form.classList.toggle("hidden");
    form.classList.toggle("flex");
  });

  function renderCard(address) {
    const node = template.content.cloneNode(true);
    node.querySelector(".address-label").textContent = address.label || "Address";
    node.querySelector(".address-name").textContent = address.full_name;
    node.querySelector(".address-phone").textContent = address.phone_number;
    node.querySelector(".address-lines").textContent =
      [address.address_line1, address.address_line2, address.city, address.state, address.country]
        .filter(Boolean)
        .join(", ");

    const badges = node.querySelector(".default-badges");
    if (address.is_default_shipping) {
      const b = document.createElement("span");
      b.className = "badge badge-new";
      b.textContent = "Default shipping";
      badges.appendChild(b);
    }
    if (address.is_default_billing) {
      const b = document.createElement("span");
      b.className = "badge badge-new";
      b.textContent = "Default billing";
      badges.appendChild(b);
    }

    node.querySelector(".remove-btn").addEventListener("click", async (event) => {
      try {
        await Storefront.apiFetch(`/auth/addresses/${address.id}/`, { method: "DELETE" });
        event.target.closest(".card").remove();
        if (!listEl.children.length) {
          emptyEl.classList.remove("hidden");
          emptyEl.classList.add("flex");
        }
      } catch (err) {
        Storefront.toast(err.message || "Could not delete address", "error");
      }
    });
    return node;
  }

  async function load() {
    loadingEl.classList.remove("hidden");
    listEl.innerHTML = "";
    emptyEl.classList.add("hidden");
    try {
      const data = await Storefront.apiFetch("/auth/addresses/");
      loadingEl.classList.add("hidden");
      if (data.results.length === 0) {
        emptyEl.classList.remove("hidden");
        emptyEl.classList.add("flex");
        return;
      }
      data.results.forEach((address) => listEl.appendChild(renderCard(address)));
    } catch (err) {
      loadingEl.textContent = "Could not load addresses.";
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    Storefront.hideError(errorEl);
    const formData = new FormData(form);
    try {
      await Storefront.apiFetch("/auth/addresses/", {
        method: "POST",
        body: JSON.stringify({
          label: formData.get("label") || "Address",
          full_name: formData.get("full_name"),
          phone_number: formData.get("phone_number"),
          address_line1: formData.get("address_line1"),
          address_line2: formData.get("address_line2") || "",
          city: formData.get("city"),
          state: formData.get("state") || "",
          postal_code: formData.get("postal_code") || "",
          country: formData.get("country"),
          address_type: "both",
          is_default_shipping: false,
          is_default_billing: false,
        }),
      });
      form.reset();
      form.classList.add("hidden");
      form.classList.remove("flex");
      load();
    } catch (err) {
      Storefront.showError(errorEl, err.message);
    }
  });

  load();
})();
