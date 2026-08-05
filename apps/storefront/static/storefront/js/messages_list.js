(function () {
  const loadingEl = document.getElementById("conversations-loading");
  const emptyEl = document.getElementById("conversations-empty");
  const listEl = document.getElementById("conversations-list");
  const errorEl = document.getElementById("conversations-error");
  const template = document.getElementById("conversation-row-template");

  function renderRow(conv) {
    const isMeCustomer = conv.customer === window.CURRENT_USER_ID;
    const otherEmail = isMeCustomer ? conv.counterpart_email : conv.customer_email;

    const node = template.content.cloneNode(true);
    node.querySelector(".conversation-link").href = "/account/messages/" + conv.id + "/";
    node.querySelector(".avatar").textContent = otherEmail.slice(0, 1).toUpperCase();
    node.querySelector(".counterpart-name").textContent = otherEmail;
    node.querySelector(".last-message").textContent = conv.last_message ? conv.last_message.text : "No messages yet.";
    // counterpart_online always describes conv.counterpart specifically, so it only tells us
    // about the *other* party when we're the customer side of this conversation.
    if (isMeCustomer && conv.counterpart_online) {
      node.querySelector(".online-dot").classList.remove("hidden");
    }
    return node;
  }

  async function load() {
    try {
      const data = await Storefront.apiFetch("/chat/conversations/");
      loadingEl.classList.add("hidden");
      const results = data.results || data;
      if (!results.length) {
        emptyEl.classList.remove("hidden");
        emptyEl.classList.add("flex");
        return;
      }
      results.forEach((conv) => listEl.appendChild(renderRow(conv)));
    } catch (err) {
      loadingEl.classList.add("hidden");
      Storefront.showError(errorEl, err.message);
    }
  }

  load();
})();
