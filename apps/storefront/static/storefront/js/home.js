(function () {
  /* ---- Hero carousel ---- */
  const carousel = document.getElementById("hero-carousel");
  if (carousel) {
    const slides = Array.from(carousel.querySelectorAll(".hero-slide"));
    const dots = Array.from(carousel.querySelectorAll(".hero-dot"));
    let index = 0;
    let timer = null;

    function show(newIndex) {
      index = (newIndex + slides.length) % slides.length;
      slides.forEach((slide, i) => slide.classList.toggle("hidden", i !== index));
      dots.forEach((dot, i) => {
        dot.classList.toggle("bg-white", i === index);
        dot.classList.toggle("bg-white/50", i !== index);
      });
    }

    function restartAutoplay() {
      if (timer) clearInterval(timer);
      if (slides.length > 1) timer = setInterval(() => show(index + 1), 6000);
    }

    carousel.querySelectorAll(".hero-nav").forEach((btn) => {
      btn.addEventListener("click", () => {
        show(index + Number(btn.dataset.dir));
        restartAutoplay();
      });
    });
    dots.forEach((dot) => {
      dot.addEventListener("click", () => {
        show(Number(dot.dataset.slide));
        restartAutoplay();
      });
    });

    restartAutoplay();
  }

  /* ---- Flash deals countdown ---- */
  const countdownEl = document.getElementById("flash-countdown");
  if (countdownEl) {
    const endsAt = new Date(countdownEl.dataset.endsAt).getTime();

    function tick() {
      const remaining = endsAt - Date.now();
      if (remaining <= 0) {
        countdownEl.textContent = "Deal ended";
        clearInterval(intervalId);
        return;
      }
      const hours = Math.floor(remaining / 3600000);
      const minutes = Math.floor((remaining % 3600000) / 60000);
      const seconds = Math.floor((remaining % 60000) / 1000);
      countdownEl.textContent = `${hours}h ${minutes}m ${seconds}s left`;
    }

    tick();
    const intervalId = setInterval(tick, 1000);
  }
})();
