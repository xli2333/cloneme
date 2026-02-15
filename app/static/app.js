const chatPane = document.getElementById("chatPane");
const sendBtn = document.getElementById("sendBtn");
const input = document.getElementById("messageInput");
const statusText = document.getElementById("statusText");
const activeConvTitle = document.getElementById("activeConvTitle");
const newConvBtn = document.getElementById("newConvBtn");
const convList = document.getElementById("convList");
const msgTpl = document.getElementById("msgTpl");
const feedbackBar = document.getElementById("feedbackBar");
const selectedCount = document.getElementById("selectedCount");
const feedbackComment = document.getElementById("feedbackComment");
const clearSelectedBtn = document.getElementById("clearSelectedBtn");
const submitFeedbackBtn = document.getElementById("submitFeedbackBtn");
const ctxMenu = document.getElementById("ctxMenu");
const ctxPickBtn = document.getElementById("ctxPickBtn");
const ctxMarkSelectedBtn = document.getElementById("ctxMarkSelectedBtn");
const ctxLikeBtn = document.getElementById("ctxLikeBtn");

const STORAGE_LIST = "doppel_conversation_list";
const STORAGE_ACTIVE = "doppel_active_conversation_id";

let conversations = [];
let conversationId = "";
let selectedMessageIds = new Set();
let activeCtxMessageId = null;
const messageNodeMap = new Map();

function createConversationId() {
  return `conv_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function nowTs() {
  return Date.now();
}

function fmtTime(ts) {
  const d = new Date(ts || Date.now());
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}

function shortText(text, n = 16) {
  const t = String(text || "").replace(/\s+/g, " ").trim();
  if (!t) return "暂无消息";
  if (t.length <= n) return t;
  return `${t.slice(0, n)}…`;
}

function saveConversations() {
  localStorage.setItem(STORAGE_LIST, JSON.stringify(conversations));
  localStorage.setItem(STORAGE_ACTIVE, conversationId);
}

function ensureConversationList() {
  let list = [];
  try {
    list = JSON.parse(localStorage.getItem(STORAGE_LIST) || "[]");
    if (!Array.isArray(list)) list = [];
  } catch (_) {
    list = [];
  }

  list = list
    .map((x) => ({
      id: String(x.id || "").trim(),
      title: String(x.title || "新会话"),
      preview: String(x.preview || ""),
      updatedAt: Number(x.updatedAt || 0),
    }))
    .filter((x) => x.id);

  if (!list.length) {
    const legacy = localStorage.getItem("doppel_conversation_id");
    const firstId = legacy && legacy.trim() ? legacy.trim() : createConversationId();
    list = [{ id: firstId, title: "新会话", preview: "", updatedAt: nowTs() }];
  }

  conversations = list.sort((a, b) => b.updatedAt - a.updatedAt);

  const activeSaved = localStorage.getItem(STORAGE_ACTIVE);
  if (activeSaved && conversations.some((c) => c.id === activeSaved)) {
    conversationId = activeSaved;
  } else {
    conversationId = conversations[0].id;
  }

  saveConversations();
}

function renderConversationList() {
  convList.innerHTML = "";

  conversations
    .sort((a, b) => b.updatedAt - a.updatedAt)
    .forEach((conv) => {
      const item = document.createElement("button");
      item.type = "button";
      item.className = `conv-item${conv.id === conversationId ? " active" : ""}`;
      item.dataset.id = conv.id;
      item.innerHTML = `
        <div class="conv-name">${escapeHtml(conv.title || "新会话")}</div>
        <div class="conv-preview">${escapeHtml(shortText(conv.preview || ""))}</div>
        <div class="conv-time">${fmtTime(conv.updatedAt)}</div>
      `;
      item.addEventListener("click", () => switchConversation(conv.id));
      convList.appendChild(item);
    });

  const active = conversations.find((x) => x.id === conversationId);
  activeConvTitle.textContent = active ? active.title : "Doppelganger";
}

function addConversation() {
  const id = createConversationId();
  conversations.unshift({
    id,
    title: `会话 ${conversations.length + 1}`,
    preview: "",
    updatedAt: nowTs(),
  });
  conversationId = id;
  saveConversations();
  renderConversationList();
  resetConversationView();
}

function touchConversation(id, lastText = "", role = "user") {
  const conv = conversations.find((x) => x.id === id);
  if (!conv) return;

  conv.updatedAt = nowTs();
  if (lastText) conv.preview = String(lastText);

  if (role === "user" && (!conv.title || conv.title.startsWith("会话") || conv.title === "新会话")) {
    conv.title = shortText(lastText || "新会话", 12);
  }

  conversations.sort((a, b) => b.updatedAt - a.updatedAt);
  saveConversations();
  renderConversationList();
}

function switchConversation(id) {
  if (!id || id === conversationId) return;
  conversationId = id;
  saveConversations();
  renderConversationList();
  resetConversationView();
  loadConversation();
}

function resetConversationView() {
  selectedMessageIds = new Set();
  messageNodeMap.clear();
  chatPane.innerHTML = "";
  syncFeedbackBar();
  closeContextMenu();
}

function scrollToBottom() {
  chatPane.scrollTop = chatPane.scrollHeight;
}

function setStatus(text) {
  statusText.textContent = text;
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function closeContextMenu() {
  activeCtxMessageId = null;
  ctxMenu.classList.add("hidden");
}

function toggleSelectMessage(messageId) {
  if (!messageId || messageId <= 0) return;
  if (selectedMessageIds.has(messageId)) selectedMessageIds.delete(messageId);
  else selectedMessageIds.add(messageId);

  const node = messageNodeMap.get(messageId);
  if (node) node.classList.toggle("selected", selectedMessageIds.has(messageId));

  syncFeedbackBar();
}

function clearSelected() {
  for (const id of selectedMessageIds) {
    const node = messageNodeMap.get(id);
    if (node) node.classList.remove("selected");
  }
  selectedMessageIds = new Set();
  syncFeedbackBar();
}

function showContextMenu(x, y, messageId) {
  activeCtxMessageId = messageId;
  ctxPickBtn.textContent = selectedMessageIds.has(messageId) ? "取消多选这条" : "加入多选这条";
  ctxMenu.style.left = `${x}px`;
  ctxMenu.style.top = `${y}px`;
  ctxMenu.classList.remove("hidden");
}

function bindAssistantContextMenu(target, messageId) {
  target.addEventListener("contextmenu", (e) => {
    e.preventDefault();
    e.stopPropagation();
    const x = Math.min(e.clientX, window.innerWidth - 210);
    const y = Math.min(e.clientY, window.innerHeight - 160);
    showContextMenu(x, y, messageId);
  });
}

function renderMessage(msg) {
  const node = msgTpl.content.firstElementChild.cloneNode(true);
  node.classList.add(msg.role);
  node.dataset.messageId = String(msg.id || "");

  const bubble = node.querySelector(".bubble");
  bubble.innerHTML = escapeHtml(msg.content);

  if (msg.role === "assistant" && Number(msg.id) > 0) {
    const messageId = Number(msg.id);
    messageNodeMap.set(messageId, node);
    node.classList.toggle("selected", selectedMessageIds.has(messageId));
    bindAssistantContextMenu(node, messageId);
    bindAssistantContextMenu(bubble, messageId);
  }

  chatPane.appendChild(node);
  scrollToBottom();
}

function renderTyping() {
  const wrapper = document.createElement("div");
  wrapper.className = "msg-row assistant";
  wrapper.id = "typingRow";
  wrapper.innerHTML = `<div class="bubble-wrap"><div class="bubble typing"><i></i><i></i><i></i></div></div>`;
  chatPane.appendChild(wrapper);
  scrollToBottom();
}

function clearTyping() {
  const row = document.getElementById("typingRow");
  if (row) row.remove();
}

async function loadConversation() {
  try {
    const res = await fetch(`/api/conversation/${conversationId}`);
    if (!res.ok) return;
    const data = await res.json();

    resetConversationView();
    for (const msg of data.messages) {
      renderMessage(msg);
    }

    const last = data.messages[data.messages.length - 1];
    if (last) touchConversation(conversationId, last.content, last.role);
  } catch (err) {
    console.error(err);
  }
}

function syncFeedbackBar() {
  const count = selectedMessageIds.size;
  selectedCount.textContent = `已选中 ${count} 条`;
  feedbackBar.classList.toggle("hidden", count === 0);
}

async function submitFeedback(messageIds, comment) {
  if (!messageIds.length) return;
  try {
    const res = await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: conversationId,
        message_ids: messageIds,
        comment: comment || "",
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || "反馈提交失败");
      return;
    }

    alert(`已采纳 ${data.accepted_count} 条，偏好版本 v${data.preference_version}\n${data.summary}`);
    feedbackComment.value = "";
    clearSelected();
    await loadConversation();
  } catch (err) {
    console.error(err);
    alert("反馈提交异常");
  }
}

async function sendMessage() {
  const text = input.value.trim();
  if (!text) return;

  input.value = "";
  input.style.height = "40px";

  renderMessage({
    id: -Date.now(),
    role: "user",
    content: text,
  });
  touchConversation(conversationId, text, "user");

  setStatus("输入中...");
  renderTyping();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: conversationId,
        message: text,
      }),
    });

    const data = await res.json();
    clearTyping();

    if (!res.ok) {
      alert(data.detail || "发送失败");
      setStatus("在线");
      return;
    }

    const bubbles = data.bubbles || [];
    const ids = data.assistant_message_ids || [];

    for (let i = 0; i < bubbles.length; i++) {
      const bubble = bubbles[i];
      const msg = {
        id: ids[i] || i + 1,
        role: "assistant",
        content: bubble.text,
      };
      const delay = Math.max(0, Number(bubble.delay_ms || 0));
      setTimeout(() => {
        renderMessage(msg);
        touchConversation(conversationId, bubble.text, "assistant");
      }, delay);
    }

    const maxDelay = bubbles.length ? Math.max(...bubbles.map((x) => Number(x.delay_ms || 0))) : 0;
    setTimeout(() => setStatus("在线"), maxDelay + 120);
  } catch (err) {
    clearTyping();
    setStatus("在线");
    console.error(err);
    alert("发送异常");
  }
}

sendBtn.addEventListener("click", sendMessage);

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

input.addEventListener("input", () => {
  input.style.height = "40px";
  input.style.height = `${Math.min(input.scrollHeight, 150)}px`;
});

submitFeedbackBtn.addEventListener("click", () => {
  submitFeedback([...selectedMessageIds], feedbackComment.value.trim());
});

clearSelectedBtn.addEventListener("click", () => {
  clearSelected();
});

ctxPickBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  if (!activeCtxMessageId) return;
  toggleSelectMessage(activeCtxMessageId);
  closeContextMenu();
});

ctxMarkSelectedBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  if (activeCtxMessageId && !selectedMessageIds.has(activeCtxMessageId)) {
    toggleSelectMessage(activeCtxMessageId);
  }
  const ids = [...selectedMessageIds];
  closeContextMenu();
  submitFeedback(ids, feedbackComment.value.trim());
});

ctxLikeBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  if (!activeCtxMessageId) return;
  const id = activeCtxMessageId;
  closeContextMenu();
  submitFeedback([id], "");
});

ctxMenu.addEventListener("pointerdown", (e) => {
  e.stopPropagation();
});

document.addEventListener("pointerdown", (e) => {
  if (!ctxMenu.classList.contains("hidden") && !ctxMenu.contains(e.target)) {
    closeContextMenu();
  }
});

window.addEventListener("resize", closeContextMenu);
chatPane.addEventListener("scroll", closeContextMenu);

newConvBtn.addEventListener("click", () => {
  addConversation();
});

function boot() {
  ensureConversationList();
  renderConversationList();
  resetConversationView();
  loadConversation();
}

boot();
