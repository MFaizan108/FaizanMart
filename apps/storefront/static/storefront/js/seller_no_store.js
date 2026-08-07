(function () {
  const form = document.getElementById("apply-form");
  const errorEl = document.getElementById("apply-error");
  const successEl = document.getElementById("apply-success");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    Storefront.hideError(errorEl);
    const formData = new FormData(form);
    const submitBtn = form.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> Submitting...';
    try {
      await Storefront.apiFetch("/vendors/apply/", {
        method: "POST",
        body: JSON.stringify({
          store_name: formData.get("store_name"),
          description: formData.get("description") || "",
        }),
      });
      form.classList.add("hidden");
      successEl.classList.remove("hidden");
      Storefront.toast("Seller application submitted", "success");
      setTimeout(() => window.location.reload(), 1500);
    } catch (err) {
      Storefront.showError(errorEl, err.message);
      submitBtn.disabled = false;
      submitBtn.textContent = "Submit Seller Application";
    }
  });
})();
