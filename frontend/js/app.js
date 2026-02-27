/* ============================================================
   AEVA Digital Life v2 - 前端逻辑
   新增：打字机效果、亲密度展示、记忆分层、新心情粒子
   ============================================================ */

const API = "http://127.0.0.1:19260";
let ws = null;
let isSending = false;

// ============================================================
// 初始化
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
  loadStatus();
  loadLogs();
  loadMemories();
  connectChat();
  initParticles();

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
      if (data.type === "reply") {
        // 移除打字指示器
        removeTypingIndicator();
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
// 发送消息
// ============================================================
function sendMessage() {
  const input = document.getElementById("chatInput");
  const text = input.value.trim();
  if (!text || isSending) return;

  if (!ws || ws.readyState !== WebSocket.OPEN) {
    addMessage("aeva", "[连接已断开，正在重连...]");
    return;
  }

  isSending = true;
  document.getElementById("chatSendBtn").disabled = true;
  addMessage("user", text);
  showTypingIndicator();

  try {
    ws.send(JSON.stringify({ text: text }));
  } catch (err) {
    console.error("[sendMessage] 发送失败:", err);
    removeTypingIndicator();
    addMessage("aeva", "[消息发送失败，请稍后重试]");
    isSending = false;
    document.getElementById("chatSendBtn").disabled = false;
  }

  input.value = "";
  input.focus();
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
  bubble.textContent = text;
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
      bubble.textContent += text.charAt(i);
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
// 回车发送
// ============================================================
document.addEventListener("keydown", (e) => {
  if (
    e.key === "Enter" && !e.shiftKey &&
    document.activeElement && document.activeElement.id === "chatInput"
  ) {
    e.preventDefault();
    sendMessage();
  }
});

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
