(function () {
  const loadingEl = document.getElementById("store-loading");
  const form = document.getElementById("store-form");
  const errorEl = document.getElementById("store-form-error");
  const successEl = document.getElementById("store-form-success");

  async function load() {
    try {
      const store = await Storefront.apiFetch("/vendors/store/");
      loadingEl.classList.add("hidden");
      form.classList.remove("hidden");
      form.classList.add("flex");
      form.elements.name.value = store.name || "";
      form.elements.description.value = store.description || "";
      form.elements.shipping_policy.value = store.shipping_policy || "";
      form.elements.return_policy.value = store.return_policy || "";
    } catch (err) {
      loadingEl.textContent = "Could not load store settings.";
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    Storefront.hideError(errorEl);
    successEl.classList.add("hidden");
    const formData = new FormData(form);
    if (!formData.get("logo").size) formData.delete("logo");
    if (!formData.get("banner").size) formData.delete("banner");

    const submitBtn = form.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    try {
      await Storefront.apiFetch("/vendors/store/", { method: "PATCH", body: formData });
      successEl.textContent = "Store settings saved.";
      successEl.classList.remove("hidden");
    } catch (err) {
      Storefront.showError(errorEl, err.message);
    } finally {
      submitBtn.disabled = false;
    }
  });

  load();
})();
