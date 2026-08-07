/* Floating AI shopping-assistant widget — talks to apps.assistant's
 * /api/assistant/query/ (grounded in the real catalog, replies in English/Roman Urdu/Urdu
 * script to match whatever the customer typed). Works for guests too, no login needed. */
(function () {
  const toggleBtn = document.getElementById("chatbot-toggle");
  const panel = document.getElementById("chatbot-panel");
  const closeBtn = document.getElementById("chatbot-close");
  const messagesEl = document.getElementById("chatbot-messages");
  const form = document.getElementById("chatbot-form");
  const input = document.getElementById("chatbot-input");
  if (!toggleBtn || !panel || !window.Storefront) return;

  let opened = false;
  let greeted = false;

  function fmtPrice(amount) {
    return "Rs " + Math.round(amount).toLocaleString("en-PK");
  }

  function addBubble(text, who) {
    const bubble = document.createElement("div");
    bubble.className =
      who === "user"
        ? "max-w-[85%] self-end rounded-2xl rounded-br-sm bg-brand px-3 py-2 text-sm text-white"
        : "max-w-[85%] self-start rounded-2xl rounded-bl-sm bg-black/5 px-3 py-2 text-sm text-black/80";
    bubble.textContent = text;
    messagesEl.appendChild(bubble);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return bubble;
  }

  function addProducts(products) {
    if (!products || !products.length) return;
    const grid = document.createElement("div");
    grid.className = "flex flex-col gap-2";
    products.forEach((product) => {
      const card = document.createElement("a");
      card.href = "/products/" + product.id + "/";
      card.className =
        "flex items-center justify-between gap-2 rounded-xl border border-black/10 p-2.5 text-sm transition hover:border-brand/40 hover:bg-brand/5";
      const name = document.createElement("span");
      name.className = "truncate";
      name.textContent = product.name;
      const price = document.createElement("span");
      price.className = "shrink-0 font-medium text-brand";
      price.textContent = fmtPrice(product.price);
      card.append(name, price);
      grid.appendChild(card);
    });
    messagesEl.appendChild(grid);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function addTyping() {
    const bubble = document.createElement("div");
    bubble.className = "flex w-fit max-w-[85%] items-center gap-1 self-start rounded-2xl rounded-bl-sm bg-black/5 px-3 py-3";
    for (let i = 0; i < 3; i++) {
      const dot = document.createElement("span");
      dot.className = "typing-dot";
      bubble.appendChild(dot);
    }
    messagesEl.appendChild(bubble);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return bubble;
  }

  function open() {
    opened = true;
    panel.classList.remove("hidden");
    toggleBtn.setAttribute("aria-expanded", "true");
    if (!greeted) {
      greeted = true;
      addBubble('Hi! Tell me what you’re looking for — e.g. "laptop under 100000" or "sasta phone dikhao".', "bot");
    }
    input.focus();
  }
  function close() {
    opened = false;
    panel.classList.add("hidden");
    toggleBtn.setAttribute("aria-expanded", "false");
  }

  toggleBtn.addEventListener("click", () => (opened ? close() : open()));
  closeBtn.addEventListener("click", close);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && opened) close();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const query = input.value.trim();
    if (!query) return;
    addBubble(query, "user");
    input.value = "";
    input.disabled = true;
    const typing = addTyping();
    try {
      const result = await Storefront.apiFetch("/assistant/query/", {
        method: "POST",
        body: JSON.stringify({ query }),
      });
      typing.remove();
      addBubble(result.message, "bot");
      addProducts(result.products);
    } catch (err) {
      typing.remove();
      addBubble("Sorry, something went wrong. Please try again.", "bot");
    } finally {
      input.disabled = false;
      input.focus();
    }
  });
})();
