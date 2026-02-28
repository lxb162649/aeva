/* ============================================================
   AEVA Digital Life v2 - 前端逻辑
   新增：打字机效果、亲密度展示、记忆分层、新心情粒子
   ============================================================ */

const API = "http://127.0.0.1:19260";
const MAX_CHARS = 20000;
let ws = null;
let isSending = false;
let pendingFiles = []; // 待发送的文件列表
let slashCommands = {}; // 斜杠命令定义缓存
let slashMenuIndex = -1; // 当前选中的命令菜单项索引

// ============================================================
// 初始化
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
  loadStatus();
  loadLogs();
  loadMemories();
  loadSlashCommands();
  connectChat();
  initParticles();
  initFileUpload();
  initTextarea();
  initSlashMenu();

  // 定时刷新
  setInterval(loadStatus, 10000);
  setInterval(loadLogs, 30000);
  setInterval(updateLifeTimer, 1000);
});

// ============================================================
// 加载 AEVA 状态
// ============================================================
async function loadStatus() {
  try {
    const resp = await fetch(`${API}/api/status`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    updateStatusPanel(data);
    updateLifeOrb(data.mood);
    updateStatusText(data);
    updateParticleColor(data.mood);
  } catch (err) {
    console.error("[loadStatus] 请求失败:", err);
  }
}

// ============================================================
// 更新状态面板
// ============================================================
function updateStatusPanel(echo) {
  // 名字 & 等级
  document.getElementById("echoName").textContent = echo.name || "AEVA";
  document.getElementById("echoLevel").textContent = "Lv." + (echo.level || 1);

  // 心情
  const moodDisplay = echo.mood_display || {};
  const moodText = moodDisplay.emoji
    ? `${moodDisplay.emoji} ${moodDisplay.zh || echo.mood}`
    : echo.mood || "--";
  document.getElementById("echoMood").textContent = moodText;

  // 活动状态
  const actDisplay = echo.activity_display || {};
  const actEmoji = actDisplay.emoji || "⏳";
  const actZh = actDisplay.zh || "等待中";
  document.getElementById("activityDisplay").textContent = `${actEmoji} ${actZh}`;

  // 精力条
  const energy = Math.max(0, Math.min(100, echo.energy || 0));
  document.getElementById("energyFill").style.width = energy + "%";
  document.getElementById("energyText").textContent = Math.round(energy) + "/100";

  // 经验条
  const expMax = (echo.level || 1) * 100;
  const expPct = Math.max(0, Math.min(100, ((echo.exp || 0) / expMax) * 100));
  document.getElementById("expFill").style.width = expPct + "%";
  document.getElementById("expText").textContent = `${echo.exp || 0}/${expMax}`;

  // 亲密度
  const intimacy = echo.intimacy_info || {};
  document.getElementById("intimacyTitle").textContent = intimacy.title || "初识";
  const intimacyPct = Math.max(0, Math.min(100, (intimacy.progress || 0) * 100));
  document.getElementById("intimacyFill").style.width = intimacyPct + "%";

  // 存活时间
  window._totalLifeSeconds = echo.total_life_seconds || 0;
  window._lastStatusTime = Date.now();
}

// ============================================================
// 更新生命光球颜色
// ============================================================
function updateLifeOrb(mood) {
  const orb = document.getElementById("lifeOrb");
  orb.className = "life-orb mood-" + (mood || "calm");
}

// ============================================================
// 更新粒子颜色（跟随心情）
// ============================================================
function updateParticleColor(mood) {
  const colorMap = {
    calm: "#6366f1",
    happy: "#10b981",
    lonely: "#f59e0b",
    thinking: "#8b5cf6",
    excited: "#f43f5e",
    sleepy: "#64748b",
    curious: "#06b6d4",
  };
  const color = colorMap[mood] || colorMap.calm;
  const particles = document.querySelectorAll(".particle");
  particles.forEach((p) => { p.style.background = color; });
}

// ============================================================
// 更新状态文字
// ============================================================
function updateStatusText(data) {
  const el = document.getElementById("statusText");
  if (data.status_text) {
    el.textContent = data.status_text;
    return;
  }
  if (window._latestLogContent) {
    el.textContent = window._latestLogContent;
  }
}

// ============================================================
// 每秒更新存活时间
// ============================================================
function updateLifeTimer() {
  if (window._totalLifeSeconds === undefined) return;
  const elapsed = (Date.now() - (window._lastStatusTime || Date.now())) / 1000;
  const total = (window._totalLifeSeconds || 0) + elapsed;

  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const mins = Math.floor((total % 3600) / 60);
  const secs = Math.floor(total % 60);

  let text = "";
  if (days > 0) text += days + "天 ";
  text +=
    String(hours).padStart(2, "0") + ":" +
    String(mins).padStart(2, "0") + ":" +
    String(secs).padStart(2, "0");

  document.getElementById("lifeTimer").textContent = text;
}

// ============================================================
// WebSocket 聊天
// ============================================================
function connectChat() {
  setConnectionStatus("connecting");

  try {
    ws = new WebSocket("ws://127.0.0.1:19260/ws/chat");
  } catch (err) {
    console.error("[connectChat] WebSocket 创建失败:", err);
    setConnectionStatus("error");
    scheduleReconnect();
    return;
  }

  ws.onopen = () => {
    console.log("[WS] 已连接");
    setConnectionStatus("connected");
    const container = document.getElementById("chatMessages");
    if (
      container.children.length === 1 &&
      container.firstElementChild.textContent.includes("连接建立中")
    ) {
      container.innerHTML = "";
    }
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);

      // 升级进度消息（实时更新）
      if (data.type === "upgrade_progress") {
        addUpgradeProgress(data.text);
        return;
      }

      if (data.type === "reply") {
        // 移除打字指示器和升级进度
        removeTypingIndicator();
        clearUpgradeProgress();
        isSending = false;
        document.getElementById("chatSendBtn").disabled = false;

        // 打字机效果展示回复
        typeMessage("aeva", data.text);

        // 更新状态
        if (data.mood) {
          updateLifeOrb(data.mood);
          updateParticleColor(data.mood);
        }
        if (data.mood_display) {
          const moodText = `${data.mood_display.emoji} ${data.mood_display.zh}`;
          document.getElementById("echoMood").textContent = moodText;
        }
        if (data.energy !== undefined) {
          const e = Math.round(data.energy);
          document.getElementById("energyFill").style.width = e + "%";
          document.getElementById("energyText").textContent = e + "/100";
        }
        if (data.intimacy) {
          document.getElementById("intimacyTitle").textContent = data.intimacy.title || "初识";
          const pct = Math.max(0, Math.min(100, (data.intimacy.progress || 0) * 100));
          document.getElementById("intimacyFill").style.width = pct + "%";
        }

        loadMemories();
      }
    } catch (err) {
      console.error("[WS] 消息解析失败:", err);
    }
  };

  ws.onerror = () => { setConnectionStatus("error"); };
  ws.onclose = () => {
    setConnectionStatus("error");
    ws = null;
    scheduleReconnect();
  };
}

function scheduleReconnect() {
  setTimeout(() => { connectChat(); }, 3000);
}

function setConnectionStatus(state) {
  const el = document.getElementById("connectionStatus");
  const textEl = el.querySelector(".conn-text");
  el.className = "connection-status";
  switch (state) {
    case "connected":
      el.classList.add("connected");
      textEl.textContent = "CONNECTED";
      break;
    case "connecting":
      textEl.textContent = "CONNECTING...";
      break;
    case "error":
      el.classList.add("error");
      textEl.textContent = "DISCONNECTED";
      break;
    default:
      textEl.textContent = "INITIALIZING";
  }
}

// ============================================================
// 发送消息（支持文件附件）
// ============================================================
function sendMessage() {
  const input = document.getElementById("chatInput");
  const text = input.value.trim();
  if ((!text && pendingFiles.length === 0) || isSending) return;

  // 隐藏斜杠命令菜单
  hideSlashMenu();

  if (!ws || ws.readyState !== WebSocket.OPEN) {
    addMessage("aeva", "[连接已断开，正在重连...]");
    return;
  }

  isSending = true;
  document.getElementById("chatSendBtn").disabled = true;

  // 显示用户消息（含文件预览）
  if (pendingFiles.length > 0) {
    const fileNames = pendingFiles.map(f => f.name).join(", ");
    const displayText = text ? `${text}\n📎 ${fileNames}` : `📎 ${fileNames}`;
    addMessage("user", displayText);
  } else {
    addMessage("user", text);
  }

  showTypingIndicator();

  // 如果有文件，先上传再发送消息
  if (pendingFiles.length > 0) {
    uploadAndSend(text);
  } else {
    try {
      ws.send(JSON.stringify({ text: text }));
    } catch (err) {
      console.error("[sendMessage] 发送失败:", err);
      removeTypingIndicator();
      addMessage("aeva", "[消息发送失败，请稍后重试]");
      isSending = false;
      document.getElementById("chatSendBtn").disabled = false;
    }
  }

  input.value = "";
  updateCharCount();
  autoResizeTextarea();
  clearFilePreviews();
  input.focus();
}

// ============================================================
// 上传文件后发送消息
// ============================================================
async function uploadAndSend(text) {
  try {
    const formData = new FormData();
    for (const file of pendingFiles) {
      formData.append("files", file);
    }

    const resp = await fetch(`${API}/api/upload`, { method: "POST", body: formData });
    if (!resp.ok) throw new Error(`上传失败: HTTP ${resp.status}`);

    const result = await resp.json();
    const fileInfos = result.files || [];

    // 通过 WebSocket 发送带文件信息的消息
    ws.send(JSON.stringify({
      text: text,
      files: fileInfos,
    }));
  } catch (err) {
    console.error("[uploadAndSend] 失败:", err);
    removeTypingIndicator();
    addMessage("aeva", "[文件上传失败，请重试]");
    isSending = false;
    document.getElementById("chatSendBtn").disabled = false;
  }
}

// ============================================================
// 聊天气泡
// ============================================================
function addMessage(role, text) {
  const container = document.getElementById("chatMessages");
  const div = document.createElement("div");
  div.className = "message message-" + role;

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  // 支持多行文本：将换行符转为 <br>
  bubble.innerHTML = escapeHtml(text).replace(/\n/g, "<br>");
  div.appendChild(bubble);

  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

// ============================================================
// 打字机效果
// ============================================================
function typeMessage(role, text) {
  const container = document.getElementById("chatMessages");
  const div = document.createElement("div");
  div.className = "message message-" + role;

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  div.appendChild(bubble);
  container.appendChild(div);

  let i = 0;
  const speed = Math.max(15, Math.min(40, 1200 / text.length)); // 自适应速度

  function type() {
    if (i < text.length) {
      const char = text.charAt(i);
      if (char === "\n") {
        bubble.appendChild(document.createElement("br"));
      } else {
        bubble.appendChild(document.createTextNode(char));
      }
      i++;
      container.scrollTop = container.scrollHeight;
      setTimeout(type, speed);
    }
  }
  type();
}

// ============================================================
// 打字指示器
// ============================================================
function showTypingIndicator() {
  const container = document.getElementById("chatMessages");
  // 避免重复
  if (document.getElementById("typingIndicator")) return;

  const div = document.createElement("div");
  div.className = "message message-aeva";
  div.id = "typingIndicator";

  const indicator = document.createElement("div");
  indicator.className = "typing-indicator";
  for (let i = 0; i < 3; i++) {
    const dot = document.createElement("span");
    dot.className = "typing-dot";
    indicator.appendChild(dot);
  }
  div.appendChild(indicator);
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function removeTypingIndicator() {
  const el = document.getElementById("typingIndicator");
  if (el) el.remove();
}

// ============================================================
// 加载生命日志
// ============================================================
async function loadLogs() {
  try {
    const resp = await fetch(`${API}/api/logs`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    const container = document.getElementById("lifeLogs");
    const logs = data.logs || [];

    if (logs.length === 0) {
      container.innerHTML = '<div class="log-empty">AEVA 刚刚诞生，还没有生命日志...</div>';
      return;
    }

    // 最新在最上面
    const reversed = logs.slice().reverse();
    let html = "";
    reversed.forEach((log) => {
      const time = formatTime(log.create_time);
      const moodEmoji = log.mood_emoji || "";
      html +=
        '<div class="log-item">' +
        '<div class="log-time">' + escapeHtml(time) +
        (moodEmoji ? ' <span class="log-mood-tag">' + moodEmoji + '</span>' : '') +
        '</div>' +
        '<div class="log-content">' + escapeHtml(log.content) + '</div>' +
        '</div>';
    });
    container.innerHTML = html;

    if (reversed.length > 0) {
      window._latestLogContent = reversed[0].content;
      const statusEl = document.getElementById("statusText");
      if (statusEl.textContent === "正在唤醒 AEVA..." || statusEl.textContent === "") {
        statusEl.textContent = reversed[0].content;
      }
    }
  } catch (err) {
    console.error("[loadLogs] 请求失败:", err);
  }
}

// ============================================================
// 加载记忆（分层展示）
// ============================================================
async function loadMemories() {
  try {
    const resp = await fetch(`${API}/api/memories`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    const container = document.getElementById("memoryList");
    const statsEl = document.getElementById("memoryStats");

    const memories = data.memories || [];
    const stats = data.stats || {};

    // 更新统计
    if (statsEl) {
      statsEl.textContent = `${stats.total || 0}`;
    }

    if (memories.length === 0) {
      container.innerHTML = '<div class="memory-empty">还没有任何记忆...</div>';
      return;
    }

    // 层级标签映射
    const layerMap = {
      core: { label: "核心", class: "tag-core", itemClass: "memory-core" },
      long_term: { label: "长期", class: "tag-long", itemClass: "memory-long" },
      short_term: { label: "短期", class: "tag-short", itemClass: "memory-short" },
    };

    // 按层级排序：核心 > 长期 > 短期，同层内按时间倒序
    const layerOrder = { core: 0, long_term: 1, short_term: 2 };
    const sorted = memories.slice().sort((a, b) => {
      const la = layerOrder[a.layer] ?? 2;
      const lb = layerOrder[b.layer] ?? 2;
      if (la !== lb) return la - lb;
      return (b.create_time || "").localeCompare(a.create_time || "");
    });

    // 显示最近 15 条
    const recent = sorted.slice(0, 15);
    let html = "";
    recent.forEach((m) => {
      const layer = layerMap[m.layer] || layerMap.short_term;
      const strength = Math.round((m.strength || 0) * 100);
      html +=
        '<div class="memory-item ' + layer.itemClass + '">' +
        '<div class="memory-content">' + escapeHtml(m.content) + '</div>' +
        '<div class="memory-meta">' +
        '<span class="memory-layer-tag ' + layer.class + '">' + layer.label + '</span>' +
        '<span>强度 ' + strength + '%</span>' +
        '</div>' +
        '</div>';
    });
    container.innerHTML = html;
  } catch (err) {
    console.error("[loadMemories] 请求失败:", err);
  }
}

// ============================================================
// 键盘事件：Enter 发送，Ctrl/Shift+Enter 换行，方向键控制命令菜单
// ============================================================
document.addEventListener("keydown", (e) => {
  if (
    document.activeElement &&
    document.activeElement.id === "chatInput"
  ) {
    const menu = document.getElementById("slashMenu");
    const menuVisible = menu && menu.style.display === "block";

    // 命令菜单可见时，拦截方向键和 Tab
    if (menuVisible) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        navigateSlashMenu("down");
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        navigateSlashMenu("up");
        return;
      }
      if (e.key === "Tab") {
        e.preventDefault();
        confirmSlashMenu();
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        hideSlashMenu();
        return;
      }
    }

    if (e.key === "Enter") {
      // 命令菜单可见时，Enter 选择命令
      if (menuVisible) {
        e.preventDefault();
        if (!confirmSlashMenu()) {
          // 菜单无匹配项，正常发送
          sendMessage();
        }
        return;
      }

      if (e.ctrlKey || e.shiftKey) {
        // Ctrl+Enter 或 Shift+Enter → 换行（textarea 自然支持）
        return; // 不阻止默认行为，让 textarea 插入换行
      }
      // 普通 Enter → 发送消息
      e.preventDefault();
      sendMessage();
    }
  }
});

// ============================================================
// Textarea 初始化 & 自动高度调整
// ============================================================
function initTextarea() {
  const input = document.getElementById("chatInput");
  // 输入时更新字数统计 & 自动调整高度
  input.addEventListener("input", () => {
    // 字数限制
    if (input.value.length > MAX_CHARS) {
      input.value = input.value.substring(0, MAX_CHARS);
    }
    updateCharCount();
    autoResizeTextarea();
  });
  // 粘贴时也检查
  input.addEventListener("paste", () => {
    setTimeout(() => {
      if (input.value.length > MAX_CHARS) {
        input.value = input.value.substring(0, MAX_CHARS);
      }
      updateCharCount();
      autoResizeTextarea();
    }, 0);
  });
  updateCharCount();
}

function updateCharCount() {
  const input = document.getElementById("chatInput");
  const counter = document.getElementById("charCount");
  if (!counter) return;
  const len = input.value.length;
  counter.textContent = `${len}/${MAX_CHARS}`;
  if (len > MAX_CHARS * 0.9) {
    counter.classList.add("char-count-warn");
  } else {
    counter.classList.remove("char-count-warn");
  }
}

function autoResizeTextarea() {
  const input = document.getElementById("chatInput");
  input.style.height = "auto";
  const maxHeight = 120; // 最大 ~5 行
  input.style.height = Math.min(input.scrollHeight, maxHeight) + "px";
}

// ============================================================
// 文件上传功能
// ============================================================
function initFileUpload() {
  const uploadBtn = document.getElementById("chatUploadBtn");
  const fileInput = document.getElementById("fileInput");

  uploadBtn.addEventListener("click", () => {
    fileInput.click();
  });

  fileInput.addEventListener("change", (e) => {
    const files = Array.from(e.target.files);
    if (files.length === 0) return;

    for (const file of files) {
      // 限制单文件 10MB
      if (file.size > 10 * 1024 * 1024) {
        addMessage("aeva", `[文件 ${file.name} 超过 10MB 限制]`);
        continue;
      }
      pendingFiles.push(file);
      addFilePreview(file);
    }

    // 清空 input 以允许再次选择相同文件
    fileInput.value = "";
  });

  // 支持拖拽上传
  const chatSection = document.querySelector(".chat-section");
  chatSection.addEventListener("dragover", (e) => {
    e.preventDefault();
    chatSection.classList.add("drag-over");
  });
  chatSection.addEventListener("dragleave", () => {
    chatSection.classList.remove("drag-over");
  });
  chatSection.addEventListener("drop", (e) => {
    e.preventDefault();
    chatSection.classList.remove("drag-over");
    const files = Array.from(e.dataTransfer.files);
    for (const file of files) {
      if (file.size > 10 * 1024 * 1024) {
        addMessage("aeva", `[文件 ${file.name} 超过 10MB 限制]`);
        continue;
      }
      pendingFiles.push(file);
      addFilePreview(file);
    }
  });
}

function addFilePreview(file) {
  const previewArea = document.getElementById("filePreviewArea");
  const previewList = document.getElementById("filePreviewList");
  previewArea.style.display = "flex";

  const item = document.createElement("div");
  item.className = "file-preview-item";

  if (file.type.startsWith("image/")) {
    const img = document.createElement("img");
    img.className = "file-preview-img";
    const reader = new FileReader();
    reader.onload = (e) => { img.src = e.target.result; };
    reader.readAsDataURL(file);
    item.appendChild(img);
  } else {
    const icon = document.createElement("div");
    icon.className = "file-preview-icon";
    icon.textContent = getFileIcon(file.name);
    item.appendChild(icon);
  }

  const name = document.createElement("span");
  name.className = "file-preview-name";
  name.textContent = file.name.length > 12 ? file.name.substring(0, 10) + "..." : file.name;
  name.title = file.name;
  item.appendChild(name);

  // 删除按钮
  const removeBtn = document.createElement("button");
  removeBtn.className = "file-preview-remove";
  removeBtn.textContent = "×";
  removeBtn.onclick = () => {
    const idx = pendingFiles.indexOf(file);
    if (idx !== -1) pendingFiles.splice(idx, 1);
    item.remove();
    if (pendingFiles.length === 0) {
      previewArea.style.display = "none";
    }
  };
  item.appendChild(removeBtn);

  previewList.appendChild(item);
}

function clearFilePreviews() {
  pendingFiles = [];
  const previewArea = document.getElementById("filePreviewArea");
  const previewList = document.getElementById("filePreviewList");
  previewList.innerHTML = "";
  previewArea.style.display = "none";
}

function getFileIcon(filename) {
  const ext = filename.split(".").pop().toLowerCase();
  const iconMap = {
    csv: "📊", json: "📋", txt: "📄", xlsx: "📊", xls: "📊",
    pdf: "📕", doc: "📘", docx: "📘", xml: "📰", yaml: "⚙️",
    yml: "⚙️", md: "📝", log: "📃", tsv: "📊",
  };
  return iconMap[ext] || "📎";
}

// ============================================================
// 斜杠命令系统 - 加载命令定义
// ============================================================
async function loadSlashCommands() {
  try {
    const resp = await fetch(`${API}/api/slash-commands`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    slashCommands = data.commands || {};
    console.log("[SlashCommands] 已加载", Object.keys(slashCommands).length, "个命令");
  } catch (err) {
    console.error("[SlashCommands] 加载失败:", err);
    // 内置后备命令列表
    slashCommands = {
      "/upgrade": { usage: "/upgrade [描述]", description: "触发一次自我升级" },
      "/upgrade-blueprint": { usage: "/upgrade-blueprint [蓝图ID]", description: "执行指定的蓝图升级" },
      "/upgrade-cleanup": { usage: "/upgrade-cleanup [文件路径]", description: "清理冗余代码" },
      "/upgrade-status": { usage: "/upgrade-status", description: "查看升级系统状态" },
      "/upgrade-rollback": { usage: "/upgrade-rollback", description: "回滚最近一次升级" },
      "/help": { usage: "/help", description: "列出所有可用命令" },
    };
  }
}

// ============================================================
// 斜杠命令菜单 - 初始化和交互
// ============================================================
function initSlashMenu() {
  const input = document.getElementById("chatInput");

  input.addEventListener("input", () => {
    updateSlashMenu();
  });

  // 点击其他地方关闭菜单
  document.addEventListener("click", (e) => {
    const menu = document.getElementById("slashMenu");
    if (menu && !menu.contains(e.target) && e.target.id !== "chatInput") {
      hideSlashMenu();
    }
  });
}

function updateSlashMenu() {
  const input = document.getElementById("chatInput");
  const text = input.value;

  // 只在输入以 "/" 开头且没有空格（还在输入命令名）时显示
  if (!text.startsWith("/") || text.includes(" ")) {
    hideSlashMenu();
    return;
  }

  const query = text.toLowerCase();
  const matches = Object.entries(slashCommands).filter(([cmd]) =>
    cmd.startsWith(query)
  );

  if (matches.length === 0) {
    hideSlashMenu();
    return;
  }

  showSlashMenu(matches);
}

function showSlashMenu(matches) {
  let menu = document.getElementById("slashMenu");
  if (!menu) {
    menu = document.createElement("div");
    menu.id = "slashMenu";
    menu.className = "slash-menu";
    // 插入到 chat-input-area 的父元素中
    const inputArea = document.querySelector(".chat-input-area");
    inputArea.parentElement.insertBefore(menu, inputArea);
  }

  slashMenuIndex = -1;
  let html = '<div class="slash-menu-header">/ 命令</div>';
  matches.forEach(([cmd, info], idx) => {
    html +=
      '<div class="slash-menu-item" data-cmd="' + escapeHtml(cmd) + '" data-idx="' + idx + '">' +
      '<div class="slash-menu-cmd">' + escapeHtml(cmd) + '</div>' +
      '<div class="slash-menu-desc">' + escapeHtml(info.description) + '</div>' +
      '</div>';
  });
  menu.innerHTML = html;
  menu.style.display = "block";

  // 绑定点击事件
  menu.querySelectorAll(".slash-menu-item").forEach((item) => {
    item.addEventListener("click", () => {
      selectSlashCommand(item.getAttribute("data-cmd"));
    });
    item.addEventListener("mouseenter", () => {
      clearSlashMenuActive();
      item.classList.add("active");
      slashMenuIndex = parseInt(item.getAttribute("data-idx"), 10);
    });
  });
}

function hideSlashMenu() {
  const menu = document.getElementById("slashMenu");
  if (menu) menu.style.display = "none";
  slashMenuIndex = -1;
}

function selectSlashCommand(cmd) {
  const input = document.getElementById("chatInput");
  // 如果命令接受参数（usage 中含 [...]），在后面加空格方便继续输入
  const info = slashCommands[cmd];
  const hasArgs = info && info.usage && info.usage.includes("[");
  input.value = hasArgs ? cmd + " " : cmd;
  hideSlashMenu();
  input.focus();
  updateCharCount();
  autoResizeTextarea();
}

function clearSlashMenuActive() {
  const menu = document.getElementById("slashMenu");
  if (!menu) return;
  menu.querySelectorAll(".slash-menu-item").forEach((el) =>
    el.classList.remove("active")
  );
}

function navigateSlashMenu(direction) {
  const menu = document.getElementById("slashMenu");
  if (!menu || menu.style.display === "none") return false;

  const items = menu.querySelectorAll(".slash-menu-item");
  if (items.length === 0) return false;

  clearSlashMenuActive();

  if (direction === "down") {
    slashMenuIndex = (slashMenuIndex + 1) % items.length;
  } else {
    slashMenuIndex = slashMenuIndex <= 0 ? items.length - 1 : slashMenuIndex - 1;
  }

  items[slashMenuIndex].classList.add("active");
  items[slashMenuIndex].scrollIntoView({ block: "nearest" });
  return true;
}

function confirmSlashMenu() {
  const menu = document.getElementById("slashMenu");
  if (!menu || menu.style.display === "none") return false;

  const items = menu.querySelectorAll(".slash-menu-item");
  if (slashMenuIndex >= 0 && slashMenuIndex < items.length) {
    selectSlashCommand(items[slashMenuIndex].getAttribute("data-cmd"));
    return true;
  }
  // 如果没有选中项但菜单可见，选第一个
  if (items.length > 0) {
    selectSlashCommand(items[0].getAttribute("data-cmd"));
    return true;
  }
  return false;
}

// ============================================================
// 升级进度消息展示
// ============================================================
function addUpgradeProgress(text) {
  const container = document.getElementById("chatMessages");

  // 查找或创建升级进度容器
  let progressWrap = document.getElementById("upgradeProgressWrap");
  if (!progressWrap) {
    // 先移除打字指示器，避免冲突
    removeTypingIndicator();

    const div = document.createElement("div");
    div.className = "message message-aeva";
    div.id = "upgradeProgressWrap";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble upgrade-progress-bubble";
    bubble.innerHTML =
      '<div class="upgrade-progress-header">⚡ 自我升级中...</div>' +
      '<div class="upgrade-progress-list" id="upgradeProgressList"></div>';
    div.appendChild(bubble);
    container.appendChild(div);
    progressWrap = div;
  }

  const list = document.getElementById("upgradeProgressList");
  const step = document.createElement("div");
  step.className = "upgrade-progress-step";

  // 判断是否是完成/错误/普通步骤
  const isError = text.includes("❌") || text.includes("失败") || text.includes("错误");
  const isDone = text.includes("✅") || text.includes("完成") || text.includes("成功");

  if (isError) {
    step.classList.add("step-error");
  } else if (isDone) {
    step.classList.add("step-done");
  } else {
    step.classList.add("step-running");
  }

  step.innerHTML =
    '<span class="step-indicator">' + (isError ? "✗" : isDone ? "✓" : "›") + '</span>' +
    '<span class="step-text">' + escapeHtml(text) + '</span>';

  list.appendChild(step);

  // 标记之前的 running 步骤为完成
  const prevRunning = list.querySelectorAll(".step-running");
  prevRunning.forEach((el, i) => {
    if (i < prevRunning.length - 1) {
      el.classList.remove("step-running");
      el.classList.add("step-done");
      el.querySelector(".step-indicator").textContent = "✓";
    }
  });

  container.scrollTop = container.scrollHeight;
}

// 清理升级进度容器（在最终 reply 到达后）
function clearUpgradeProgress() {
  const wrap = document.getElementById("upgradeProgressWrap");
  if (wrap) wrap.remove();
}

// ============================================================
// 光球粒子
// ============================================================
function initParticles() {
  const container = document.getElementById("orbParticles");
  if (!container) return;
  const count = 25;
  for (let i = 0; i < count; i++) {
    const p = document.createElement("div");
    p.className = "particle";
    p.style.left = Math.random() * 100 + "%";
    p.style.top = Math.random() * 100 + "%";
    p.style.animationDelay = Math.random() * 4 + "s";
    p.style.animationDuration = 3 + Math.random() * 3 + "s";
    container.appendChild(p);
  }
}

// ============================================================
// 工具函数
// ============================================================
function formatTime(raw) {
  try {
    const d = new Date(raw);
    if (isNaN(d.getTime())) return raw || "--";
    return d.toLocaleString("zh-CN", {
      month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit",
      hour12: false,
    });
  } catch (_) {
    return raw || "--";
  }
}

function escapeHtml(str) {
  if (!str) return "";
  const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
  return String(str).replace(/[&<>"']/g, (c) => map[c]);
}
