/* ═══════════════════════════════════════════════
   🧠 AI 智能助理 — 前端逻辑 v1.1
   会话管理 + 文件上传 + 记忆管理 + 流式对话
   ═══════════════════════════════════════════════ */

const API_BASE = "";
const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);

// ─── DOM ───
const messagesEl = $("#messages");
const chatInput = $("#chatInput");
const sendBtn = $("#sendBtn");
const uploadBtn = $("#uploadBtn");
const fileInput = $("#fileInput");
const uploadStatus = $("#uploadStatus");
const sessionsPanel = $("#sessionsPanel");
const sessionsList = $("#sessionsList");
const sidebar = $("#sidebar");
const overlay = $("#overlay");
const memoryList = $("#memoryList");
const memorySearch = $("#memorySearch");
const memoryBadge = $("#memoryBadge");
const memoryCount = $("#memoryCount");
const addMemoryBtn = $("#addMemoryBtn");
const newMemoryInput = $("#newMemoryInput");
const newMemoryType = $("#newMemoryType");
const modelSelect = $("#modelSelect");
const clearBtn = $("#clearBtn");
const editModal = $("#editModal");
const editContent = $("#editContent");
const editType = $("#editType");
const editImportance = $("#editImportance");
const saveEdit = $("#saveEdit");
const cancelEdit = $("#cancelEdit");
const inputStatus = $("#inputStatus");
const newChatBtn = $("#newChatBtn");

// ─── 状态 ───
let streaming = false;
let editMemoryId = null;
let currentSessionId = "default";
let uploadedContent = "";   // 上传的文件文本内容
let uploadedFileInfo = "";  // 上传的文件名

// ─── 工具函数 ───
function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

/* Markdown 渲染 */
function renderMarkdown(text) {
  let html = escapeHtml(text);
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) =>
    `<pre><code class="lang-${lang}">${code.trim()}</code></pre>`);
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/^#### (.+)$/gm, "<h4>$1</h4>");
  html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^## (.+)$/gm, "<h2>$1</h2>");
  html = html.replace(/^# (.+)$/gm, "<h1>$1</h1>");
  html = html.replace(/^---\s*$/gm, "<hr>");
  html = html.replace(/^\*\*\*\s*$/gm, "<hr>");
  html = html.replace(/^> (.+)$/gm, "<blockquote><p>$1</p></blockquote>");
  html = html.replace(/\|(.+)\|/g, m => {
    if (/^\|[\s:]?-{3,}[\s:]?\|/.test(m)) return "";
    const cells = m.split("|").filter(c => c.trim()).map(c => c.trim());
    return cells.length ? "<tr>" + cells.map(c => `<td>${c}</td>`).join("") + "</tr>" : "";
  });
  html = html.replace(/(<tr>[\s\S]*?<\/tr>\n?)+/g, "<table>$&</table>");
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/__(.+?)__/g, "<strong>$1</strong>");
  html = html.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, "<em>$1</em>");
  html = html.replace(/_(.+?)_/g, "<em>$1</em>");
  html = html.replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  html = html.replace(/^[\*-] (.+)$/gm, "<li>$1</li>");
  html = html.replace(/(<li>.*<\/li>\n?)+/g, "<ul>$&</ul>");
  html = html.replace(/^\d+[.)] (.+)$/gm, "<li>$1</li>");
  html = html.replace(/<p><\/(h[1-4]|ul|ol|table|pre|blockquote|hr)>/g, "</$1>");
  html = html.replace(/<(h[1-4]|ul|ol|table|pre|blockquote|hr)><\/p>/g, "<$1>");
  html = html.replace(/\n\n/g, "</p><p>");
  html = "<p>" + html + "</p>";
  html = html.replace(/<p><\/p>/g, "");
  html = html.replace(/<p>\s*<p>/g, "<p>");
  html = html.replace(/<\/p>\s*<\/p>/g, "</p>");
  return html;
}

// ═══════════════════════════════════════════════
//  💬 会话管理
// ═══════════════════════════════════════════════

async function loadSessions() {
  try {
    const resp = await fetch(`${API_BASE}/api/sessions`);
    const data = await resp.json();
    renderSessions(data.sessions);
  } catch (e) { console.warn("加载会话失败:", e); }
}

function renderSessions(sessions) {
  sessionsList.innerHTML = "";
  for (const s of sessions) {
    const div = document.createElement("div");
    div.className = "session-item" + (s.id === currentSessionId ? " active" : "");
    div.innerHTML = `
      <span class="title">${escapeHtml(s.title || "新对话")}</span>
      <button class="del-session" data-id="${s.id}">✕</button>`;
    div.querySelector(".title").addEventListener("click", () => switchSession(s.id));
    div.querySelector(".del-session").addEventListener("click", async e => {
      e.stopPropagation();
      if (!confirm("删除此会话？")) return;
      await fetch(`${API_BASE}/api/sessions/${s.id}`, { method: "DELETE" });
      if (s.id === currentSessionId) {
        currentSessionId = "default";
        clearMessages();
      }
      loadSessions();
    });
    sessionsList.appendChild(div);
  }
}

async function switchSession(sessionId) {
  currentSessionId = sessionId;
  // 高亮当前会话
  $$(".session-item").forEach(el => el.classList.toggle("active", el.dataset.id === sessionId));
  // 加载消息
  try {
    const resp = await fetch(`${API_BASE}/api/sessions/${sessionId}/messages`);
    const data = await resp.json();
    renderMessages(data.messages);
  } catch (e) {
    clearMessages();
  }
}

async function createNewSession() {
  try {
    const resp = await fetch(`${API_BASE}/api/sessions`, { method: "POST" });
    const session = await resp.json();
    currentSessionId = session.id;
    clearMessages();
    loadSessions();
  } catch (e) { console.warn("创建会话失败:", e); }
}

function renderMessages(messages) {
  messagesEl.innerHTML = "";
  for (const m of messages) {
    if (m.role === "user" || m.role === "assistant") {
      const div = document.createElement("div");
      div.className = `message ${m.role}`;
      div.innerHTML = `
        <div class="avatar">${m.role === "user" ? "👤" : "🧠"}</div>
        <div class="bubble">${m.role === "assistant" ? renderMarkdown(m.content) : escapeHtml(m.content)}</div>`;
      messagesEl.appendChild(div);
    }
  }
  if (messages.length === 0) showWelcome();
  scrollToBottom();
}

function clearMessages() {
  messagesEl.innerHTML = "";
  showWelcome();
  scrollToBottom();
}

function showWelcome() {
  messagesEl.innerHTML = `
    <div class="welcome-message">
      <div class="welcome-icon">🧠</div>
      <h2>你好！我是 AI 智能助理</h2>
      <p>长期记忆 · 联网搜索 · 天气查询 · 文件上传</p>
      <div class="welcome-suggestions">
        <button class="suggestion-btn" data-msg="记住我喜欢喝冰美式，正在找实习">📝 记住我的信息</button>
        <button class="suggestion-btn" data-msg="今天北京天气怎么样？">🌤️ 查天气</button>
        <button class="suggestion-btn" data-msg="搜索一下2026年最新科技趋势">🔍 搜索科技趋势</button>
      </div>
    </div>`;
}

// ═══════════════════════════════════════════════
//  📁 文件上传
// ═══════════════════════════════════════════════

uploadBtn.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", async () => {
  const file = fileInput.files[0];
  if (!file) return;

  uploadStatus.textContent = `📤 正在上传 ${file.name}...`;

  try {
    const formData = new FormData();
    formData.append("file", file);

    const resp = await fetch(`${API_BASE}/api/upload`, { method: "POST", body: formData });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

    const data = await resp.json();
    uploadedContent = data.content;
    uploadedFileInfo = `📎 ${data.filename} (${(data.size/1024).toFixed(0)}KB)`;
    uploadStatus.textContent = `✅ ${uploadedFileInfo}`;
    uploadBtn.classList.add("has-file");
    fileInput.value = "";

    // 自动填入提示
    if (data.type === "image") {
      chatInput.value += `[图片: ${data.filename}] `;
    } else {
      chatInput.value += `我上传了文件「${data.filename}」，请阅读并回答相关问题：\n`;
    }
    autoResize();
    sendBtn.disabled = false;

  } catch (e) {
    uploadStatus.textContent = `❌ 上传失败: ${e.message}`;
  }
});

// ═══════════════════════════════════════════════
//  📝 消息 / 流式对话
// ═══════════════════════════════════════════════

let streamingMessageEl = null;

function addMessage(role, content) {
  const welcome = messagesEl.querySelector(".welcome-message");
  if (welcome) welcome.remove();
  const div = document.createElement("div");
  div.className = `message ${role}`;
  div.innerHTML = `
    <div class="avatar">${role === "user" ? "👤" : "🧠"}</div>
    <div class="bubble">${role === "assistant" ? renderMarkdown(content) : escapeHtml(content)}</div>`;
  messagesEl.appendChild(div);
  scrollToBottom();
}

function updateStreaming(rawContent) {
  removeTypingIndicator();
  if (!streamingMessageEl) {
    const div = document.createElement("div");
    div.className = "message assistant";
    div.innerHTML = `<div class="avatar">🧠</div><div class="bubble"></div>`;
    messagesEl.appendChild(div);
    streamingMessageEl = div.querySelector(".bubble");
  }
  // 流式清理：隐藏未闭合的 markdown 符号
  let d = rawContent;
  d = d.replace(/^<p>[#]+ /gm, "<p>");
  d = d.replace(/\*\*(.+?)(\*\*|$)/g, (_, t, c) => c ? `<strong>${t}</strong>` : t);
  d = d.replace(/__(.+?)(__|$)/g, (_, t, c) => c ? `<strong>${t}</strong>` : t);
  d = d.replace(/(?<!\*)\*(?!\*)(.+?)((?<!\*)\*(?!\*)|$)/g, (_, t, c) => c ? `<em>${t}</em>` : t);
  d = d.replace(/`([^`]*)`/g, (_, t) => t ? `<code>${t}</code>` : "");
  d = d.replace(/<tr><td>[-:\s]+<\/td>(<td>[-:\s]+<\/td>)*<\/tr>/g, "");
  d = d.replace(/\|([^|]*)\|/g, (_, t) => t || "");
  streamingMessageEl.innerHTML = d + '<span class="cursor">▍</span>';
  scrollToBottom();
}

function finalizeStreaming(content) {
  if (streamingMessageEl) {
    streamingMessageEl.innerHTML = content;
    streamingMessageEl = null;
    scrollToBottom();
  } else {
    addMessage("assistant", content);
  }
}

function removeTypingIndicator() {
  const t = messagesEl.querySelector(".typing-indicator");
  if (t) t.remove();
}

function scrollToBottom() {
  requestAnimationFrame(() => messagesEl.scrollTop = messagesEl.scrollHeight);
}

function addTypingIndicator() {
  removeTypingIndicator();
  const div = document.createElement("div");
  div.className = "typing-indicator";
  div.innerHTML = `<div class="avatar">🧠</div><div class="typing-dots"><span></span><span></span><span></span></div>`;
  messagesEl.appendChild(div);
  scrollToBottom();
}

function addErrorMessage(text) {
  removeTypingIndicator();
  streamingMessageEl = null;
  const div = document.createElement("div");
  div.className = "message error";
  div.innerHTML = `<div class="avatar">⚠️</div><div class="bubble">${escapeHtml(text)}</div>`;
  messagesEl.appendChild(div);
  scrollToBottom();
}

async function sendMessage(message) {
  if (streaming || !message.trim()) return;
  streaming = true;
  sendBtn.disabled = true;
  inputStatus.textContent = "🤖 AI 思考中...";

  // 如果上传了文件内容，附加到消息里
  let finalMsg = message;
  if (uploadedContent) {
    finalMsg = `${message}\n\n---\n📎 用户上传的文件内容：\n${uploadedContent}`;
  }

  addMessage("user", message);
  chatInput.value = "";
  autoResize();
  addTypingIndicator();

  try {
    const resp = await fetch(`${API_BASE}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: finalMsg, session_id: currentSessionId }),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "", fullContent = "", started = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const data = JSON.parse(line.slice(6));
          if (data.type === "chunk") {
            fullContent += data.content;
            if (!started) { started = true; removeTypingIndicator(); }
            updateStreaming(renderMarkdown(fullContent));
          } else if (data.type === "done") {
            fullContent = data.content;
            finalizeStreaming(renderMarkdown(fullContent));
          } else if (data.type === "error") {
            throw new Error(data.content);
          }
        } catch (e) {
          if (e.message === "error") break;
        }
      }
    }
    if (fullContent && streamingMessageEl) finalizeStreaming(renderMarkdown(fullContent));
  } catch (err) {
    removeTypingIndicator();
    streamingMessageEl = null;
    addErrorMessage(`连接失败: ${err.message}。请确保后端服务已启动。`);
  } finally {
    streaming = false;
    streamingMessageEl = null;
    sendBtn.disabled = false;
    inputStatus.textContent = "";
    // 清理上传状态
    uploadedContent = "";
    uploadedFileInfo = "";
    uploadStatus.textContent = "";
    uploadBtn.classList.remove("has-file");
    // 刷新
    loadSessions();
    refreshMemories();
  }
}

// ─── 输入框 ───
function autoResize() {
  chatInput.style.height = "auto";
  chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + "px";
}

chatInput.addEventListener("input", () => {
  sendBtn.disabled = !chatInput.value.trim() || streaming;
  autoResize();
});
chatInput.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(chatInput.value); }
});
sendBtn.addEventListener("click", () => sendMessage(chatInput.value));
clearBtn.addEventListener("click", () => {
  if (confirm("确定清空当前对话？记忆不会被删除。")) clearMessages();
});
newChatBtn.addEventListener("click", createNewSession);

document.querySelector(".welcome-suggestions")?.addEventListener("click", e => {
  const btn = e.target.closest(".suggestion-btn");
  if (btn) sendMessage(btn.dataset.msg);
});

// ═══════════════════════════════════════════════
//  🧠 记忆管理
// ═══════════════════════════════════════════════

async function refreshMemories(keyword = "") {
  try {
    const url = keyword
      ? `${API_BASE}/api/memories/search?q=${encodeURIComponent(keyword)}`
      : `${API_BASE}/api/memories`;
    const resp = await fetch(url);
    const data = await resp.json();
    const memories = keyword ? data.results : data.memories;
    renderMemoryList(memories);
    if (!keyword) updateMemoryBadge(memories.length);
    const stats = await (await fetch(`${API_BASE}/api/memories/stats`)).json();
    const c = stats.total || 0;
    if (memoryCount) memoryCount.textContent = `📝 ${c} 条`;
    const label = document.getElementById("memCountLabel");
    if (label) label.textContent = `· ${c} 条`;
  } catch (e) { console.warn(e); }
}

function renderMemoryList(memories) {
  memoryList.innerHTML = "";
  if (!memories || memories.length === 0) {
    memoryList.innerHTML = `<div class="empty-state"><div class="empty-state-icon">📝</div><p>还没有任何记忆</p></div>`;
    return;
  }
  const labels = { general: "一般", user_info: "用户信息", preference: "偏好", fact: "事实", task: "任务" };
  for (const m of memories) {
    const card = document.createElement("div");
    card.className = "memory-card";
    card.innerHTML = `
      <div class="memory-card-header">
        <span class="memory-type-badge ${m.memory_type}">${labels[m.memory_type] || m.memory_type}</span>
        <span class="memory-importance">${"★".repeat(Math.min(m.importance,5))}${"☆".repeat(Math.max(5-m.importance,0))}</span>
      </div>
      <div class="memory-content">${escapeHtml(m.content)}</div>
      <div class="memory-actions">
        <button class="memory-edit-btn" data-id="${m.id}">编辑</button>
        <button class="memory-del-btn" data-id="${m.id}">删除</button>
      </div>`;
    card.querySelector(".memory-edit-btn").onclick = e => { e.stopPropagation(); openEditModal(m); };
    card.querySelector(".memory-del-btn").onclick = async e => {
      e.stopPropagation();
      if (confirm(`删除？\n"${m.content.slice(0,50)}"`)) {
        await fetch(`${API_BASE}/api/memories/${m.id}`, { method: "DELETE" });
        refreshMemories(memorySearch.value);
      }
    };
    memoryList.appendChild(card);
  }
}

function updateMemoryBadge(count) { memoryBadge.textContent = `💾 ${count} 条记忆`; }

addMemoryBtn.addEventListener("click", async () => {
  const c = newMemoryInput.value.trim();
  if (!c) return;
  await fetch(`${API_BASE}/api/memories`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content: c, memory_type: newMemoryType.value, importance: 5 }) });
  newMemoryInput.value = "";
  refreshMemories(memorySearch.value);
});
newMemoryInput.addEventListener("keydown", e => { if (e.key === "Enter") addMemoryBtn.click(); });

let searchTimer;
memorySearch.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => refreshMemories(memorySearch.value), 300);
});

// ─── 编辑弹窗 ───
function openEditModal(m) {
  editMemoryId = m.id;
  editContent.value = m.content;
  editType.value = m.memory_type;
  editImportance.value = m.importance;
  editModal.classList.remove("hidden");
}
cancelEdit.onclick = () => { editModal.classList.add("hidden"); editMemoryId = null; };
saveEdit.onclick = async () => {
  if (!editMemoryId) return;
  await fetch(`${API_BASE}/api/memories/${editMemoryId}`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content: editContent.value, memory_type: editType.value, importance: parseInt(editImportance.value) || 5 }),
  });
  editModal.classList.add("hidden");
  editMemoryId = null;
  refreshMemories(memorySearch.value);
};
editModal.addEventListener("click", e => { if (e.target === editModal) { editModal.classList.add("hidden"); editMemoryId = null; } });

// ═══════════════════════════════════════════════
//  侧边栏切换
// ═══════════════════════════════════════════════

$("#sidebarToggle").addEventListener("click", () => sessionsPanel.classList.toggle("open"));
$("#closeSidebar").addEventListener("click", () => sidebar.classList.remove("open"));
overlay.addEventListener("click", () => { sidebar.classList.remove("open"); sessionsPanel.classList.remove("open"); });

// ═══════════════════════════════════════════════
//  模型切换
// ═══════════════════════════════════════════════

modelSelect.addEventListener("change", async () => {
  const [provider, model] = modelSelect.value.split("/");
  const resp = await fetch(`${API_BASE}/api/model/switch?provider=${provider}&model=${model}`);
  const data = await resp.json();
  addMessage("assistant", `🔄 ${data.tip}\n\n当前: ${data.current.provider}/${data.current.model}`);
});

// ═══════════════════════════════════════════════
//  初始化
// ═══════════════════════════════════════════════

async function init() {
  try {
    const statusResp = await fetch(`${API_BASE}/api/status`);
    if (statusResp.ok) {
      const status = await statusResp.json();
      if (status.ready) {
        inputStatus.textContent = `✅ ${status.provider} / ${status.model}`;
        updateMemoryBadge(status.memory_stats.total);
        refreshMemories();
        loadSessions();
      } else {
        inputStatus.textContent = "⚠️ 需要配置 API Key";
        showSetupGuide();
      }
    }
  } catch (e) {
    inputStatus.textContent = "⚠️ 后端未连接";
  }
}

function showSetupGuide() {
  const w = messagesEl.querySelector(".welcome-message");
  if (w) w.remove();
  const div = document.createElement("div");
  div.className = "welcome-message";
  div.innerHTML = `<div class="welcome-icon">⚙️</div><h2>需要配置 API Key</h2><p>AI 模型尚未配置</p>
    <div class="setup-card"><p><strong>方式一：API Key</strong></p>
    <code class="setup-code">cp .env.example .env\n# 编辑 .env 填入 Key\nLLM_PROVIDER=openai\nOPENAI_API_KEY=sk-xxx</code>
    <p><strong>方式二：Ollama 本地（免费）</strong></p>
    <code class="setup-code">ollama pull qwen2.5\n# .env:\nLLM_PROVIDER=ollama</code></div>
    <button class="suggestion-btn" onclick="location.reload()">🔄 刷新</button>`;
  messagesEl.prepend(div);
}

init();
