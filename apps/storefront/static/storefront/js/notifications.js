(function () {
  const loadingEl = document.getElementById("notifications-loading");
  const emptyEl = document.getElementById("notifications-empty");
  const listEl = document.getElementById("notifications-list");
  const template = document.getElementById("notification-template");

  function timeAgo(iso) {
    return new Date(iso).toLocaleString();
  }

  function renderRow(notification) {
    const node = template.content.cloneNode(true);
    const row = node.querySelector(".notification-row");
    row.querySelector(".notification-title").textContent = notification.title;
    row.querySelector(".notification-message").textContent = notification.message;
    row.querySelector(".notification-time").textContent = timeAgo(notification.created_at);
    const dot = row.querySelector(".unread-dot");
    if (notification.is_read) dot.classList.add("invisible");

    if (notification.link) {
      row.classList.add("cursor-pointer", "hover:bg-black/[.02]");
      row.addEventListener("click", () => {
        window.location.href = notification.link;
      });
    }

    if (!notification.is_read) {
      row.addEventListener(
        "click",
        () => {
          Storefront.apiFetch(`/notifications/${notification.id}/mark_read/`, { method: "POST" }).catch(() => {});
          dot.classList.add("invisible");
        },
        { once: true }
      );
    }
    return node;
  }

  async function load() {
    try {
      const data = await Storefront.apiFetch("/notifications/");
      loadingEl.classList.add("hidden");
      if (data.results.length === 0) {
        emptyEl.classList.remove("hidden");
        emptyEl.classList.add("flex");
        return;
      }
      data.results.forEach((n) => listEl.appendChild(renderRow(n)));
    } catch (err) {
      loadingEl.textContent = "Could not load notifications.";
    }
  }

  document.getElementById("mark-all-read-btn").addEventListener("click", async () => {
    await Storefront.apiFetch("/notifications/mark_all_read/", { method: "POST" }).catch(() => {});
    document.querySelectorAll(".unread-dot").forEach((dot) => dot.classList.add("invisible"));
  });

  load();
})();
