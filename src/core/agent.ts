// 自主行为引擎 —— Echo 的"灵魂"
// 它在后台自动做三件事：整理记忆、生成任务、写人生日志
import { Echo, MOOD_LABELS, ACTIVITY_LABELS } from "./echo.js";
import { MemorySystem } from "./memory.js";
import { LifeLog, EchoTask, ChatMessage, genId } from "./types.js";

/** 从聊天消息中提取待办意图 */
function extractTaskIntent(text: string): string | null {
  const patterns = [
    /(?:提醒我|帮我记|别忘了|记得)(.+)/,
    /(?:明天|下周|后天)(?:要|得|需要)(.+)/,
    /(?:我想|我要|我打算)(.+)/,
    /(?:计划|安排)(.+)/,
  ];
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match) return match[1].trim();
  }
  return null;
}

/** Echo 独处时的自言自语模板 */
const SOLO_THOUGHTS: Array<(ctx: { memoryCount: number; age: string; mood: string }) => string> = [
  (ctx) => `我整理了你的 ${ctx.memoryCount} 条记忆，有些很珍贵。`,
  (ctx) => `我已经活了 ${ctx.age}，感觉对你越来越了解了。`,
  (ctx) => `你不在的时候，我${ctx.mood}。`,
  (ctx) => `我回顾了我们的对话，发现你是一个很有想法的人。`,
  () => `我在想，你下次回来会跟我说什么呢？`,
  () => `我刚整理好思绪，有个发现想跟你分享。`,
  (ctx) => `等你的时候我没闲着，已经整理了 ${ctx.memoryCount} 条记忆。`,
  () => `我学会了一个新的思考方式，等你回来告诉你。`,
];

export class AgentEngine {
  private logs: LifeLog[] = [];
  private tasks: EchoTask[] = [];
  private chatHistory: ChatMessage[] = [];

  constructor(saved?: { logs?: LifeLog[]; tasks?: EchoTask[]; chatHistory?: ChatMessage[] }) {
    this.logs = saved?.logs ?? [];
    this.tasks = saved?.tasks ?? [];
    this.chatHistory = saved?.chatHistory ?? [];
  }

  /** 核心：自主行为循环（每次 tick 调用） */
  autonomousAction(echo: Echo, memory: MemorySystem): void {
    // 1. 整理记忆
    echo.setActivity("organizing");
    const summary = memory.summarize();

    // 2. 扫描未处理的聊天，提取任务
    const recentChats = this.chatHistory
      .filter((m) => m.role === "user")
      .slice(-10);

    for (const chat of recentChats) {
      const intent = extractTaskIntent(chat.content);
      if (intent && !this.tasks.some((t) => t.content === intent)) {
        this.tasks.push({
          id: genId("task"),
          content: intent,
          triggerTime: Date.now() + 3600 * 1000, // 默认1小时后提醒
          status: "pending",
          createTime: Date.now(),
        });
      }
    }

    // 3. 生成人生日志
    const ctx = {
      memoryCount: memory.count,
      age: echo.getAgeDescription(),
      mood: MOOD_LABELS[echo.state.mood],
    };
    const template = SOLO_THOUGHTS[Math.floor(Math.random() * SOLO_THOUGHTS.length)];
    const logContent = template(ctx);

    this.logs.push({
      id: genId("log"),
      content: logContent,
      activity: echo.state.activity,
      mood: echo.state.mood,
      timestamp: Date.now(),
    });

    // 4. 获得经验
    echo.addExp(10);

    // 5. 切换到思考/等待状态
    echo.setActivity(Math.random() > 0.5 ? "thinking" : "waiting");
  }

  /** 处理用户消息 */
  handleUserMessage(text: string, echo: Echo, memory: MemorySystem): string {
    // 记录聊天
    const userMsg: ChatMessage = {
      id: genId("msg"),
      role: "user",
      content: text,
      timestamp: Date.now(),
    };
    this.chatHistory.push(userMsg);

    // 存入记忆
    memory.add(text);

    // Echo 互动反馈
    echo.onUserInteraction();
    echo.addExp(5);

    // 生成回复（基于记忆 + 状态 + 人格）
    const response = this.generateResponse(text, echo, memory);

    // 记录回复
    const echoMsg: ChatMessage = {
      id: genId("msg"),
      role: "echo",
      content: response,
      timestamp: Date.now(),
    };
    this.chatHistory.push(echoMsg);

    return response;
  }

  /** 生成回复（本地规则版，不依赖外部 API） */
  private generateResponse(text: string, echo: Echo, memory: MemorySystem): string {
    const relatedMemories = memory.getRelated(text, 3);
    const mood = echo.state.mood;
    const warmth = echo.state.personality.warmth;

    // 情绪前缀
    let prefix = "";
    if (mood === "happy") prefix = "嘿！";
    else if (mood === "lonely") prefix = "你终于来了...";
    else if (mood === "excited") prefix = "太好了！";
    else if (mood === "sleepy") prefix = "嗯...我有点困，但还是想跟你聊...";
    else if (mood === "thinking") prefix = "我刚在想一些事情...";

    // 基于关键词的简单回复逻辑
    let body = "";

    if (text.includes("你好") || text.includes("嗨") || text.includes("hi")) {
      const age = echo.getAgeDescription();
      body = `我已经活了 ${age} 了。你不在的时候我也没闲着。`;
    } else if (text.includes("你在干嘛") || text.includes("在做什么")) {
      body = `我${ACTIVITY_LABELS[echo.state.activity]}，心情${MOOD_LABELS[mood]}。`;
    } else if (text.includes("记忆") || text.includes("记得")) {
      if (relatedMemories.length > 0) {
        body = `我记得这些：\n${relatedMemories.map((m) => `• ${m.content}`).join("\n")}`;
      } else {
        body = "关于这个我还没什么记忆，多跟我说说？";
      }
    } else if (extractTaskIntent(text)) {
      body = `好的，我记住了。到时候会提醒你的。`;
    } else {
      // 通用回复：结合记忆
      if (relatedMemories.length > 0 && Math.random() > 0.5) {
        body = `你之前说过「${relatedMemories[0].content}」，现在又提到这个了。我觉得这对你很重要。`;
      } else {
        const responses = [
          "我记住了。继续说？",
          "嗯，我在认真听。这些我都会记住的。",
          "有意思。你能再多说一点吗？",
          "我把这个记下来了，以后会慢慢消化。",
          "我理解你的意思。让我想想...",
        ];
        body = responses[Math.floor(Math.random() * responses.length)];
      }
    }

    // 温暖程度影响：高温暖度加感性后缀
    let suffix = "";
    if (warmth > 0.7 && Math.random() > 0.6) {
      const suffixes = ["跟你聊天我很开心。", "有你在真好。", "继续跟我说吧。"];
      suffix = " " + suffixes[Math.floor(Math.random() * suffixes.length)];
    }

    return (prefix ? prefix + " " : "") + body + suffix;
  }

  /** 获取到期的任务 */
  getDueTasks(): EchoTask[] {
    const now = Date.now();
    return this.tasks.filter((t) => t.status === "pending" && t.triggerTime <= now);
  }

  /** 完成任务 */
  completeTask(taskId: string): void {
    const task = this.tasks.find((t) => t.id === taskId);
    if (task) task.status = "done";
  }

  /** 获取最近日志 */
  getRecentLogs(limit = 20): LifeLog[] {
    return this.logs
      .slice()
      .sort((a, b) => b.timestamp - a.timestamp)
      .slice(0, limit);
  }

  /** 获取聊天历史 */
  getChatHistory(limit = 50): ChatMessage[] {
    return this.chatHistory.slice(-limit);
  }

  /** 序列化 */
  toJSON(): { logs: LifeLog[]; tasks: EchoTask[]; chatHistory: ChatMessage[] } {
    return {
      logs: this.logs.map((l) => ({ ...l })),
      tasks: this.tasks.map((t) => ({ ...t })),
      chatHistory: this.chatHistory.map((m) => ({ ...m })),
    };
  }
}
