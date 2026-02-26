/* ============================================================
   AEVA Digital Life - 前端逻辑
   ============================================================ */

const API = "http://127.0.0.1:19260";
let ws = null;

// ============================================================
// 初始化
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
  loadStatus();
  loadLogs();
  loadMemories();
  connectChat();
  initParticles();

  // 每 10 秒刷新状态
  setInterval(loadStatus, 10000);
  // 每秒更新存活时间
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

  // 心情（中文 + emoji）
  const moodMap = {
    calm: "\u{1F60C} 平静",
    happy: "\u{1F60A} 愉快",
    lonely: "\u{1F97A} 想念你",
    thinking: "\u{1F914} 思考中",
  };
  document.getElementById("echoMood").textContent =
    moodMap[echo.mood] || echo.mood || "--";

  // 精力条
  const energy = Math.max(0, Math.min(100, echo.energy || 0));
  document.getElementById("energyFill").style.width = energy + "%";
  document.getElementById("energyText").textContent =
    Math.round(energy) + "/100";

  // 经验条
  const expMax = (echo.level || 1) * 100;
  const expPct = Math.max(0, Math.min(100, ((echo.exp || 0) / expMax) * 100));
  document.getElementById("expFill").style.width = expPct + "%";

  // 保存总存活秒数，供计时器使用
  window._totalLifeSeconds = echo.total_life_seconds || 0;
  window._lastStatusTime = Date.now();
}

// ============================================================
// 更新生命光球颜色
// ============================================================
function updateLifeOrb(mood) {
  const orb = document.getElementById("lifeOrb");
  // 清除所有 mood- 类名，保留 life-orb
  orb.className = "life-orb mood-" + (mood || "calm");
}

// ============================================================
// 更新状态文字（从最新日志或回退文案）
// ============================================================
function updateStatusText(data) {
  const el = document.getElementById("statusText");
  // 优先取 status_text 字段，否则从日志里取最新一条
  if (data.status_text) {
    el.textContent = data.status_text;
    return;
  }
  // 回退：显示存活相关文案
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
    String(hours).padStart(2, "0") +
    ":" +
    String(mins).padStart(2, "0") +
    ":" +
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
    // 清除初始提示消息
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
      if (data.type === "reply") {
        addMessage("aeva", data.text);
        // 更新心情与精力
        if (data.mood) {
          updateLifeOrb(data.mood);
        }
        if (data.energy !== undefined) {
          document.getElementById("energyFill").style.width =
            data.energy + "%";
          document.getElementById("energyText").textContent =
            Math.round(data.energy) + "/100";
        }
        // 聊天后刷新记忆
        loadMemories();
      }
    } catch (err) {
      console.error("[WS] 消息解析失败:", err);
    }
  };

  ws.onerror = (err) => {
    console.error("[WS] 连接错误:", err);
    setConnectionStatus("error");
  };

  ws.onclose = () => {
    console.log("[WS] 连接关闭，3秒后重连...");
    setConnectionStatus("error");
    ws = null;
    scheduleReconnect();
  };
}

/** 延迟重连 */
function scheduleReconnect() {
  setTimeout(() => {
    connectChat();
  }, 3000);
}

/** 更新底部连接状态指示器 */
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
// 发送消息
// ============================================================
function sendMessage() {
  const input = document.getElementById("chatInput");
  const text = input.value.trim();
  if (!text) return;

  if (!ws || ws.readyState !== WebSocket.OPEN) {
    addMessage("aeva", "[连接已断开，正在重连...]");
    return;
  }

  addMessage("user", text);

  try {
    ws.send(JSON.stringify({ text: text }));
  } catch (err) {
    console.error("[sendMessage] 发送失败:", err);
    addMessage("aeva", "[消息发送失败，请稍后重试]");
  }

  input.value = "";
  input.focus();
}

// ============================================================
// 添加聊天气泡
// ============================================================
function addMessage(role, text) {
  const container = document.getElementById("chatMessages");
  const div = document.createElement("div");
  div.className = "message message-" + role;

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  bubble.textContent = text;
  div.appendChild(bubble);

  container.appendChild(div);
  // 滚动到底部
  container.scrollTop = container.scrollHeight;
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

    if (!data.logs || data.logs.length === 0) {
      container.innerHTML =
        '<div class="log-empty">AEVA 刚刚诞生，还没有生命日志...</div>';
      return;
    }

    // 最新的在最上面
    const logs = data.logs.slice().reverse();
    let html = "";
    logs.forEach((log) => {
      const time = formatTime(log.create_time);
      html +=
        '<div class="log-item">' +
        '<div class="log-time">' +
        escapeHtml(time) +
        "</div>" +
        '<div class="log-content">' +
        escapeHtml(log.content) +
        "</div>" +
        "</div>";
    });
    container.innerHTML = html;

    // 缓存最新日志用于状态文字
    if (logs.length > 0) {
      window._latestLogContent = logs[0].content;
      // 如果状态文字还是初始化文案就更新
      const statusEl = document.getElementById("statusText");
      if (
        statusEl.textContent === "正在唤醒 AEVA..." ||
        statusEl.textContent === ""
      ) {
        statusEl.textContent = logs[0].content;
      }
    }
  } catch (err) {
    console.error("[loadLogs] 请求失败:", err);
  }
}

// ============================================================
// 加载记忆
// ============================================================
async function loadMemories() {
  try {
    const resp = await fetch(`${API}/api/memories`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    const container = document.getElementById("memoryList");

    if (!data.memories || data.memories.length === 0) {
      container.innerHTML =
        '<div class="memory-empty">还没有任何记忆...</div>';
      return;
    }

    // 显示最近 10 条，最新的在上面
    const recent = data.memories.slice(-10).reverse();
    let html = "";
    recent.forEach((m) => {
      const importance = Math.round((m.importance || 0) * 100);
      html +=
        '<div class="memory-item">' +
        '<div class="memory-content">' +
        escapeHtml(m.content) +
        "</div>" +
        '<div class="memory-meta">重要度: ' +
        importance +
        "%</div>" +
        "</div>";
    });
    container.innerHTML = html;
  } catch (err) {
    console.error("[loadMemories] 请求失败:", err);
  }
}

// ============================================================
// 回车发送
// ============================================================
document.addEventListener("keydown", (e) => {
  if (
    e.key === "Enter" &&
    !e.shiftKey &&
    document.activeElement &&
    document.activeElement.id === "chatInput"
  ) {
    e.preventDefault();
    sendMessage();
  }
});

// ============================================================
// 光球粒子效果
// ============================================================
function initParticles() {
  const container = document.getElementById("orbParticles");
  if (!container) return;
  const count = 20;
  for (let i = 0; i < count; i++) {
    const p = document.createElement("div");
    p.className = "particle";
    // 随机位置 & 延迟
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

/** 格式化时间 */
function formatTime(raw) {
  try {
    const d = new Date(raw);
    if (isNaN(d.getTime())) return raw || "--";
    return d.toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch (_) {
    return raw || "--";
  }
}

/** HTML 转义，防止 XSS */
function escapeHtml(str) {
  if (!str) return "";
  const map = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  };
  return String(str).replace(/[&<>"']/g, (c) => map[c]);
}
