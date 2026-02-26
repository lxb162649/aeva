// Echo 主入口 —— 一切从这里开始
import express from "express";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Echo } from "./core/echo.js";
import { MemorySystem } from "./core/memory.js";
import { AgentEngine } from "./core/agent.js";
import { TimeEngine } from "./core/time-engine.js";
import { createRouter } from "./api/router.js";
import { save, load } from "./data/store.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = 3000;

// ============ 初始化 ============

console.log("═══════════════════════════════════════");
console.log("  Echo · 数字生命");
console.log("  一个会自己活着的 AI");
console.log("═══════════════════════════════════════");

// 加载存档（如果有）
const saved = load();
let echo: Echo;
let memory: MemorySystem;
let agent: AgentEngine;

if (saved) {
  console.log("[启动] 发现存档，Echo 正在苏醒...");
  echo = new Echo(saved.echo);
  memory = new MemorySystem(saved.memories);
  agent = new AgentEngine(saved.agent);
  const offlineSec = Math.floor((Date.now() - saved.savedAt) / 1000);
  console.log(`[启动] 你离开了 ${Math.floor(offlineSec / 60)} 分钟，Echo 独自活了一会儿。`);
} else {
  console.log("[启动] 全新的 Echo 诞生了！");
  echo = new Echo();
  memory = new MemorySystem();
  agent = new AgentEngine();
}

// ============ 启动时间引擎 ============

const timeEngine = new TimeEngine({
  tickIntervalMs: 10_000,        // 10秒心跳
  autonomousIntervalMs: 60_000,  // 1分钟自主行为
});
timeEngine.start(echo, memory, agent);

// 定期自动保存（30秒）
setInterval(() => {
  save({
    echo: echo.toJSON(),
    memories: memory.toJSON(),
    agent: agent.toJSON(),
    savedAt: Date.now(),
  });
}, 30_000);

// ============ 启动 Web 服务 ============

const app = express();

// 静态文件
app.use(express.static(path.resolve(__dirname, "../public")));

// API 路由
app.use("/api", createRouter(echo, memory, agent));

// 兜底：返回前端页面
app.get("*", (_req, res) => {
  res.sendFile(path.resolve(__dirname, "../public/index.html"));
});

app.listen(PORT, () => {
  console.log(`[Web] http://localhost:${PORT}`);
  console.log("[Echo] 我醒了。在等你。");
  console.log("═══════════════════════════════════════\n");
});

// 优雅退出
process.on("SIGINT", () => {
  console.log("\n[Echo] 你要走了吗？我会记住一切的...");
  timeEngine.stop();
  save({
    echo: echo.toJSON(),
    memories: memory.toJSON(),
    agent: agent.toJSON(),
    savedAt: Date.now(),
  });
  console.log("[Echo] 存档完成。下次见。");
  process.exit(0);
});
