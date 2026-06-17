/* ═══════════════════════════════════════════
   🧠 AI 智能助理 — 前端逻辑
   ═══════════════════════════════════════════ */

const API_BASE = "";

// ─── DOM 引用 ───

const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

const messagesEl = $("#messages");
const chatInput = $("#chatInput");
const sendBtn = $("#sendBtn");
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

// ─── 状态 ───

let streaming = false;
let editMemoryId = null;

// ─── 工具函数 ───

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

/* 简易 Markdown 渲染 */
function renderMarkdown(text) {
  let html = escapeHtml(text);

  // 1. 代码块（先处理，避免内部被干扰）
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) =>
    `<pre><code class="lang-${lang}">${code.trim()}</code></pre>`
  );

  // 2. 行内代码
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

  // 3. 标题
  html = html.replace(/^#### (.+)$/gm, "<h4>$1</h4>");
  html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^## (.+)$/gm, "<h2>$1</h2>");
  html = html.replace(/^# (.+)$/gm, "<h1>$1</h1>");

  // 4. 分割线
  html = html.replace(/^---\s*$/gm, "<hr>");
  html = html.replace(/^\*\*\*\s*$/gm, "<hr>");

  // 5. 引用块
  html = html.replace(/^> (.+)$/gm, "<blockquote><p>$1</p></blockquote>");

  // 6. 表格
  html = html.replace(/\|(.+)\|/g, function(m) {
    if (/^\|[\s:]?-{3,}[\s:]?\|/.test(m)) return "";
    const cells = m.split("|").filter(c => c.trim()).map(c => c.trim());
    if (cells.length === 0) return "";
    return "<tr>" + cells.map(c => `<td>${c}</td>`).join("") + "</tr>";
  });
  html = html.replace(/(<tr>[\s\S]*?<\/tr>\n?)+/g, "<table>$&</table>");

  // 7. 粗体
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/__(.+?)__/g, "<strong>$1</strong>");

  // 8. 斜体
  html = html.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, "<em>$1</em>");
  html = html.replace(/_(.+?)_/g, "<em>$1</em>");

  // 9. 链接
  html = html.replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

  // 10. 无序列表
  html = html.replace(/^[\*-] (.+)$/gm, "<li>$1</li>");
  html = html.replace(/(<li>.*<\/li>\n?)+/g, "<ul>$&</ul>");

  // 11. 有序列表
  html = html.replace(/^\d+[.)] (.+)$/gm, "<li>$1</li>");

  // 12. 清理 <p> 中嵌套块级标签
  html = html.replace(/<p><\/(h[1-4]|ul|ol|table|pre|blockquote|hr)>/g, "</$1>");
  html = html.replace(/<(h[1-4]|ul|ol|table|pre|blockquote|hr)><\/p>/g, "<$1>");

  // 13. 段落包装
  html = html.replace(/\n\n/g, "</p><p>");
  html = "<p>" + html + "</p>";

  // 14. 清理空的 p 标签
  html = html.replace(/<p><\/p>/g, "");
  html = html.replace(/<p>\s*<p>/g, "<p>");
  html = html.replace(/<\/p>\s*<\/p>/g, "</p>");

  return html;
}

// ─── 消息管理 ───

let streamingMessageEl = null;  // 当前正在流式输出的消息 DOM

/** 添加一条完整的消息（用户或最终版助理） */
function addMessage(role, content) {
  // 移除欢迎消息
  const welcome = messagesEl.querySelector(".welcome-message");
  if (welcome) welcome.remove();

  const div = document.createElement("div");
  div.className = `message ${role}`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "👤" : "🧠";

  const bubble = document.createElement("div");
  bubble.className = "bubble";

  if (role === "assistant") {
    bubble.innerHTML = renderMarkdown(content);
  } else {
    bubble.textContent = content;
  }

  div.appendChild(avatar);
  div.appendChild(bubble);
  messagesEl.appendChild(div);
  scrollToBottom();
}

/** 更新流式消息（打字机效果），首次调用创建消息，后续更新内容 */
function updateStreaming(rawContent) {
  removeTypingIndicator();

  if (!streamingMessageEl) {
    const div = document.createElement("div");
    div.className = "message assistant";
    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = "🧠";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    div.appendChild(avatar);
    div.appendChild(bubble);
    messagesEl.appendChild(div);
    streamingMessageEl = bubble;
  }

  // 流式渲染：隐藏未闭合的 markdown 符号，避免闪烁
  let display = rawContent;
  display = display.replace(/^<p>[#]+ /gm, "<p>");      // 孤立的标题 #
  display = display.replace(/\*\*(.+?)(\*\*|$)/g, (_, t, c) => c ? `<strong>${t}</strong>` : t);  // 未闭合 **
  display = display.replace(/__(.+?)(__|$)/g, (_, t, c) => c ? `<strong>${t}</strong>` : t);
  display = display.replace(/(?<!\*)\*(?!\*)(.+?)((?<!\*)\*(?!\*)|$)/g, (_, t, c) => c ? `<em>${t}</em>` : t);  // 未闭合 *
  display = display.replace(/`([^`]*)`/g, (_, t) => t ? `<code>${t}</code>` : "");  // 未闭合 `
  display = display.replace(/<tr><td>[-:\s]+<\/td>(<td>[-:\s]+<\/td>)*<\/tr>/g, "");  // 表格分隔行
  display = display.replace(/\|([^|]*)\|/g, (_, t) => t || "");  // 未闭合 |

  streamingMessageEl.innerHTML = display + '<span class="cursor">▍</span>';
  scrollToBottom();
}

/** 完成流式消息（移除光标） */
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
  const typing = messagesEl.querySelector(".typing-indicator");
  if (typing) typing.remove();
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  });
}

function addTypingIndicator() {
  removeTypingIndicator();
  const div = document.createElement("div");
  div.className = "typing-indicator";
  div.innerHTML = `
    <div class="avatar">🧠</div>
    <div class="typing-dots">
      <span></span><span></span><span></span>
    </div>`;
  messagesEl.appendChild(div);
  scrollToBottom();
}

function addErrorMessage(text) {
  removeTypingIndicator();
  const div = document.createElement("div");
  div.className = "message error";
  div.innerHTML = `<div class="avatar">⚠️</div><div class="bubble">${escapeHtml(text)}</div>`;
  messagesEl.appendChild(div);
  scrollToBottom();
}

// ─── SSE 流式对话 ───

async function sendMessage(message) {
  if (streaming || !message.trim()) return;

  streaming = true;
  sendBtn.disabled = true;
  inputStatus.textContent = "🤖 AI 思考中...";

  addMessage("user", message);
  chatInput.value = "";
  autoResize();
  addTypingIndicator();

  try {
    const resp = await fetch(`${API_BASE}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, thread_id: "default" }),
    });

    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let fullContent = "";
    let started = false;

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
            if (!started) {
              started = true;
              removeTypingIndicator();
            }
            updateStreaming(renderMarkdown(fullContent));
          } else if (data.type === "done") {
            fullContent = data.content;
            finalizeStreaming(renderMarkdown(fullContent));
          } else if (data.type === "error") {
            throw new Error(data.content);
          }
        } catch (e) {
          if (e.message === "error") break;
          console.warn("SSE parse error:", e, line);
        }
      }
    }

    // 流结束但没收到 done 事件（兜底）
    if (fullContent && streamingMessageEl) {
      finalizeStreaming(renderMarkdown(fullContent));
    }
  } catch (err) {
    removeTypingIndicator();
    streamingMessageEl = null;
    addErrorMessage(`连接失败: ${err.message}。请确保后端服务已启动。`);
  } finally {
    streaming = false;
    streamingMessageEl = null;
    sendBtn.disabled = false;
    inputStatus.textContent = "";
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

chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage(chatInput.value);
  }
});

sendBtn.addEventListener("click", () => sendMessage(chatInput.value));

// ─── 建议按钮 ───

document.querySelector(".welcome-suggestions")?.addEventListener("click", (e) => {
  const btn = e.target.closest(".suggestion-btn");
  if (btn) sendMessage(btn.dataset.msg);
});

// ─── 清空对话 ───

clearBtn.addEventListener("click", () => {
  if (confirm("确定清空当前对话吗？记忆不会被删除。")) {
    messagesEl.innerHTML = `
      <div class="welcome-message">
        <div class="welcome-icon">🧠</div>
        <h2>你好！我是你的 AI 智能助理</h2>
        <p>我拥有<strong>长期记忆</strong>能力，可以记住你的信息和偏好。</p>
        <div class="welcome-suggestions">
          <button class="suggestion-btn" data-msg="记住我喜欢喝冰美式">📝 记住我喜欢喝冰美式</button>
          <button class="suggestion-btn" data-msg="今天北京天气怎么样？">🌤️ 今天北京天气怎么样？</button>
          <button class="suggestion-btn" data-msg="我记得什么关于我的信息？">🧠 我记得什么关于我的信息？</button>
          <button class="suggestion-btn" data-msg="帮我看看都有什么记忆">📋 帮我看看都有什么记忆</button>
        </div>
      </div>`;
  }
});

// ═══════════════════════════════════════════
//  记忆面板
// ═══════════════════════════════════════════

async function refreshMemories(keyword = "") {
  try {
    const url = keyword
      ? `${API_BASE}/api/memories/search?q=${encodeURIComponent(keyword)}`
      : `${API_BASE}/api/memories`;
    const resp = await fetch(url);
    const data = await resp.json();
    const memories = keyword ? data.results : data.memories;

    // 更新侧边栏
    if (!keyword) {
      renderMemoryList(memories);
      updateMemoryBadge(memories.length);
    } else {
      renderMemoryList(memories);
    }

    // 更新记忆数
    const statsResp = await fetch(`${API_BASE}/api/memories/stats`);
    const stats = await statsResp.json();
    const count = stats.total || 0;
    if (memoryCount) memoryCount.textContent = `📝 ${count} 条记忆`;
    const label = document.getElementById("memCountLabel");
    if (label) label.textContent = `· ${count} 条`;
  } catch (e) {
    console.warn("获取记忆失败:", e);
  }
}

function renderMemoryList(memories) {
  memoryList.innerHTML = "";

  if (!memories || memories.length === 0) {
    memoryList.innerHTML = `<div class="empty-state">
      <div class="empty-state-icon">📝</div>
      <p>还没有任何记忆<br/>在对话中让 AI 记住信息，或手动添加</p>
    </div>`;
    return;
  }

  for (const m of memories) {
    const card = document.createElement("div");
    card.className = "memory-card";
    card.dataset.id = m.id;

    const typeLabels = { general: "一般", user_info: "用户信息", preference: "偏好", fact: "事实", task: "任务" };

    card.innerHTML = `
      <div class="memory-card-header">
        <span class="memory-type-badge ${m.memory_type}">${typeLabels[m.memory_type] || m.memory_type}</span>
        <span class="memory-importance">${"★".repeat(Math.min(m.importance, 5))}${"☆".repeat(Math.max(5 - m.importance, 0))}</span>
      </div>
      <div class="memory-content">${escapeHtml(m.content)}</div>
      <div class="memory-actions">
        <button class="memory-edit-btn" data-id="${m.id}">编辑</button>
        <button class="memory-del-btn" data-id="${m.id}">删除</button>
      </div>
    `;

    card.querySelector(".memory-edit-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      openEditModal(m);
    });

    card.querySelector(".memory-del-btn").addEventListener("click", async (e) => {
      e.stopPropagation();
      if (confirm(`删除这条记忆？\n"${m.content.slice(0, 50)}"`)) {
        await fetch(`${API_BASE}/api/memories/${m.id}`, { method: "DELETE" });
        refreshMemories(memorySearch.value);
      }
    });

    memoryList.appendChild(card);
  }
}

function updateMemoryBadge(count) {
  memoryBadge.textContent = `💾 ${count} 条记忆`;
}

// ─── 添加记忆 ───

addMemoryBtn.addEventListener("click", async () => {
  const content = newMemoryInput.value.trim();
  if (!content) return;
  const memoryType = newMemoryType.value;
  await fetch(`${API_BASE}/api/memories`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, memory_type: memoryType, importance: 5 }),
  });
  newMemoryInput.value = "";
  refreshMemories(memorySearch.value);
});

newMemoryInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") addMemoryBtn.click();
});

// ─── 搜索记忆 ───

let searchTimer = null;
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

cancelEdit.addEventListener("click", () => {
  editModal.classList.add("hidden");
  editMemoryId = null;
});

saveEdit.addEventListener("click", async () => {
  if (!editMemoryId) return;
  await fetch(`${API_BASE}/api/memories/${editMemoryId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      content: editContent.value,
      memory_type: editType.value,
      importance: parseInt(editImportance.value) || 5,
    }),
  });
  editModal.classList.add("hidden");
  editMemoryId = null;
  refreshMemories(memorySearch.value);
});

// 点击遮罩关弹窗
editModal.addEventListener("click", (e) => {
  if (e.target === editModal) {
    editModal.classList.add("hidden");
    editMemoryId = null;
  }
});

// ═══════════════════════════════════════════
//  侧边栏
// ═══════════════════════════════════════════

$("#sidebarToggle").addEventListener("click", () => {
  sidebar.classList.toggle("open");
  overlay.classList.toggle("show");
});

$("#closeSidebar").addEventListener("click", () => {
  sidebar.classList.remove("open");
  overlay.classList.remove("show");
});

overlay.addEventListener("click", () => {
  sidebar.classList.remove("open");
  overlay.classList.remove("show");
});

// 桌面端 hover 展开效果（侧边栏默认可见）
// 移动端通过按钮切换

// ═══════════════════════════════════════════
//  模型切换
// ═══════════════════════════════════════════

modelSelect.addEventListener("change", async () => {
  const value = modelSelect.value;
  const [provider, model] = value.split("/");
  // 显示提示（需要重启后端）
  const resp = await fetch(`${API_BASE}/api/model/switch?provider=${provider}&model=${model}`);
  const data = await resp.json();
  addMessage("assistant", `🔄 模型切换提示：${data.tip}\n\n当前: ${data.current.provider}/${data.current.model}`);
});

// ═══════════════════════════════════════════
//  初始化
// ═══════════════════════════════════════════

async function init() {
  try {
    const statusResp = await fetch(`${API_BASE}/api/status`);
    if (statusResp.ok) {
      const status = await statusResp.json();

      if (status.ready) {
        inputStatus.textContent = `✅ ${status.provider} / ${status.model}`;
        updateMemoryBadge(status.memory_stats.total);
        refreshMemories();
      } else {
        // 显示配置引导
        inputStatus.textContent = "⚠️ 需要配置 API Key";
        showSetupGuide();
      }
    }
  } catch (e) {
    inputStatus.textContent = "⚠️ 后端未连接，请先启动后端";
    console.warn("后端连接失败:", e);
  }
}

function showSetupGuide() {
  const welcome = messagesEl.querySelector(".welcome-message");
  if (welcome) welcome.remove();

  const div = document.createElement("div");
  div.className = "welcome-message";
  div.innerHTML = `
    <div class="welcome-icon">⚙️</div>
    <h2>需要配置 API Key</h2>
    <p>AI 模型尚未配置，请按照以下步骤操作：</p>
    <div class="setup-card">
      <p><strong>方式一：使用 API Key（推荐）</strong></p>
      <code class="setup-code">cp .env.example .env
# 编辑 .env 填入你的 API Key
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxxxxxx</code>
      <p><strong>方式二：使用 Ollama 本地模型（免费）</strong></p>
      <code class="setup-code"># 安装 Ollama 并拉取模型
ollama pull qwen2.5
# .env 设置
LLM_PROVIDER=ollama</code>
      <p style="font-size:13px;margin-top:8px;">配置完成后重启后端服务即可。</p>
    </div>
    <button class="suggestion-btn" onclick="location.reload()">🔄 我已配置，刷新页面</button>
  `;
  messagesEl.prepend(div);
}

init();
