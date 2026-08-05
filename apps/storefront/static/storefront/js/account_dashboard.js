(function () {
  const loadingEl = document.getElementById("coupons-loading");
  const emptyEl = document.getElementById("coupons-empty");
  const listEl = document.getElementById("coupons-list");
  const template = document.getElementById("coupon-card-template");
  if (!listEl) return;

  function describe(coupon) {
    if (coupon.discount_type === "percentage") return `${Number(coupon.value)}% off`;
    if (coupon.discount_type === "fixed") return `Rs ${Math.round(coupon.value)} off`;
    return "Free shipping";
  }

  function isCurrentlyValid(coupon) {
    const now = new Date();
    return (
      coupon.is_active &&
      !coupon.store &&
      new Date(coupon.valid_from) <= now &&
      new Date(coupon.valid_until) >= now &&
      (coupon.usage_limit == null || coupon.used_count < coupon.usage_limit)
    );
  }

  async function load() {
    try {
      const data = await Storefront.apiFetch("/coupons/coupons/");
      const results = (data.results || data).filter(isCurrentlyValid);
      loadingEl.classList.add("hidden");
      if (!results.length) {
        emptyEl.classList.remove("hidden");
        emptyEl.classList.add("flex");
        return;
      }
      results.forEach((coupon) => {
        const node = template.content.cloneNode(true);
        node.querySelector(".coupon-code").textContent = coupon.code;
        node.querySelector(".coupon-desc").textContent =
          describe(coupon) + (coupon.min_order_amount > 0 ? ` on orders over Rs ${Math.round(coupon.min_order_amount)}` : "");
        const copyBtn = node.querySelector(".coupon-copy-btn");
        copyBtn.addEventListener("click", async () => {
          try {
            await navigator.clipboard.writeText(coupon.code);
            copyBtn.textContent = "Copied";
            setTimeout(() => (copyBtn.textContent = "Copy"), 1500);
          } catch (err) {
            window.prompt("Copy this coupon code:", coupon.code);
          }
        });
        listEl.appendChild(node);
      });
    } catch (err) {
      loadingEl.textContent = "Could not load coupons.";
    }
  }

  load();
})();
