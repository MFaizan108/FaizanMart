(function () {
  const root = document.querySelector("[data-conversation-id]");
  const conversationId = root.dataset.conversationId;
  const titleEl = document.getElementById("thread-title");
  const loadingEl = document.getElementById("thread-loading");
  const errorEl = document.getElementById("thread-error");
  const messagesEl = document.getElementById("thread-messages");
  const template = document.getElementById("message-bubble-template");
  const sendForm = document.getElementById("thread-send-form");
  const sendInput = document.getElementById("thread-input");

  const renderedIds = new Set();
  let pollTimer = null;

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function appendMessage(message) {
    if (renderedIds.has(message.id)) return;
    renderedIds.add(message.id);

    const node = template.content.cloneNode(true);
    const row = node.querySelector(".message-row");
    const bubble = node.querySelector(".message-bubble");
    const isMine = message.sender === window.CURRENT_USER_ID;

    row.classList.add(isMine ? "items-end" : "items-start");
    bubble.classList.add(isMine ? "bg-brand" : "bg-white", isMine ? "text-white" : "text-black/80");
    if (!isMine) bubble.classList.add("border", "border-black/10");
    bubble.textContent = message.text;
    node.querySelector(".message-time").textContent = new Date(message.created_at).toLocaleString();

    messagesEl.appendChild(node);
  }

  async function loadTitle() {
    try {
      const data = await Storefront.apiFetch("/chat/conversations/");
      const conv = (data.results || data).find((c) => c.id === Number(conversationId));
      if (conv) {
        const isMeCustomer = conv.customer === window.CURRENT_USER_ID;
        titleEl.textContent = isMeCustomer ? conv.counterpart_email : conv.customer_email;
      }
    } catch (err) {
      // Title is a nice-to-have; message history still loads independently.
    }
  }

  async function poll() {
    try {
      const data = await Storefront.apiFetch(`/chat/conversations/${conversationId}/messages/`);
      const results = data.results || data;
      const wasAtBottom = messagesEl.scrollTop + messagesEl.clientHeight >= messagesEl.scrollHeight - 40;
      const hadNoMessages = renderedIds.size === 0;
      results.forEach(appendMessage);
      if (hadNoMessages || wasAtBottom) scrollToBottom();
    } catch (err) {
      Storefront.showError(errorEl, err.message);
    }
  }

  async function init() {
    await loadTitle();
    await poll();
    loadingEl.classList.add("hidden");
    scrollToBottom();
    try {
      await Storefront.apiFetch(`/chat/conversations/${conversationId}/mark-read/`, { method: "POST" });
    } catch (err) {
      // Non-critical — read receipts aren't essential to viewing the thread.
    }
    pollTimer = setInterval(poll, 4000);
  }

  sendForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = sendInput.value.trim();
    if (!text) return;
    Storefront.hideError(errorEl);
    sendInput.value = "";
    try {
      const message = await Storefront.apiFetch(`/chat/conversations/${conversationId}/messages/`, {
        method: "POST",
        body: JSON.stringify({ text }),
      });
      appendMessage(message);
      scrollToBottom();
    } catch (err) {
      sendInput.value = text;
      Storefront.showError(errorEl, err.message);
    }
  });

  window.addEventListener("beforeunload", () => {
    if (pollTimer) clearInterval(pollTimer);
  });

  init();
})();
