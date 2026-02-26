// API 路由 —— Echo 的"嘴巴和耳朵"
import { Router, json } from "express";
import { Echo, MOOD_LABELS, ACTIVITY_LABELS } from "../core/echo.js";
import { MemorySystem } from "../core/memory.js";
import { AgentEngine } from "../core/agent.js";
import { getLevelTitle } from "../core/types.js";
import { save } from "../data/store.js";

/** 创建 API 路由 */
export function createRouter(echo: Echo, memory: MemorySystem, agent: AgentEngine): Router {
  const router = Router();
  router.use(json());

  // 获取 Echo 完整状态
  router.get("/status", (_req, res) => {
    const s = echo.state;
    res.json({
      name: s.name,
      age: echo.getAgeDescription(),
      mood: { key: s.mood, label: MOOD_LABELS[s.mood] },
      activity: { key: s.activity, label: ACTIVITY_LABELS[s.activity] },
      energy: Math.round(s.energy),
      level: s.level,
      levelTitle: getLevelTitle(s.level),
      exp: s.exp,
      expToNext: s.level * 100,
      memoryCount: memory.count,
      totalLifeSeconds: Math.round(s.totalLifeSeconds),
    });
  });

  // 获取人生日志（时间线）
  router.get("/logs", (req, res) => {
    const limit = parseInt(req.query.limit as string) || 20;
    const logs = agent.getRecentLogs(limit);
    res.json({ logs });
  });

  // 发送消息（对话）
  router.post("/chat", (req, res) => {
    const { message } = req.body as { message?: string };
    if (!message || typeof message !== "string" || !message.trim()) {
      res.status(400).json({ error: "消息不能为空" });
      return;
    }

    const reply = agent.handleUserMessage(message.trim(), echo, memory);

    // 每次对话后自动保存
    save({
      echo: echo.toJSON(),
      memories: memory.toJSON(),
      agent: agent.toJSON(),
      savedAt: Date.now(),
    });

    res.json({
      reply,
      mood: { key: echo.state.mood, label: MOOD_LABELS[echo.state.mood] },
      activity: { key: echo.state.activity, label: ACTIVITY_LABELS[echo.state.activity] },
    });
  });

  // 获取聊天历史
  router.get("/history", (req, res) => {
    const limit = parseInt(req.query.limit as string) || 50;
    const history = agent.getChatHistory(limit);
    res.json({ history });
  });

  // 获取待办任务
  router.get("/tasks", (_req, res) => {
    const dueTasks = agent.getDueTasks();
    res.json({ tasks: dueTasks });
  });

  return router;
}
