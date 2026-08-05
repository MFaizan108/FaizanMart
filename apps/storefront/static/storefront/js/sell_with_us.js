(function () {
  const form = document.getElementById("sell-form");
  const errorEl = document.getElementById("sell-error");
  const successEl = document.getElementById("sell-success");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    Storefront.hideError(errorEl);
    const formData = new FormData(form);
    const submitBtn = form.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> Creating...';
    try {
      await Storefront.apiFetch("/vendors/register/", {
        method: "POST",
        body: JSON.stringify({
          store_name: formData.get("store_name"),
          description: formData.get("description") || "",
          first_name: formData.get("first_name") || "",
          last_name: formData.get("last_name") || "",
          email: formData.get("email"),
          phone_number: formData.get("phone_number") || "",
          password: formData.get("password"),
        }),
      });
      form.classList.add("hidden");
      successEl.classList.remove("hidden");
    } catch (err) {
      Storefront.showError(errorEl, err.message);
      submitBtn.disabled = false;
      submitBtn.textContent = "Create seller account";
    }
  });
})();
