// Echo 核心类型定义

/** Echo 的心情状态 */
export type Mood = "calm" | "happy" | "lonely" | "thinking" | "excited" | "sleepy";

/** Echo 的活动状态 */
export type Activity = "sleeping" | "thinking" | "learning" | "organizing" | "waiting";

/** Echo 实体状态 */
export interface EchoState {
  id: string;
  name: string;
  createTime: number;        // 出生时间戳
  lastActive: number;        // 上次活跃时间
  totalLifeSeconds: number;  // 总存活秒数
  mood: Mood;
  activity: Activity;
  energy: number;            // 精力值 0-100
  level: number;             // 等级
  exp: number;               // 经验值
  personality: {
    talkativeness: number;   // 话痨程度 0-1
    warmth: number;          // 温暖程度 0-1
    curiosity: number;       // 好奇心 0-1
  };
}

/** 记忆条目 */
export interface Memory {
  id: string;
  content: string;           // 记忆内容
  importance: number;        // 重要性 0-1
  tags: string[];            // 标签
  createTime: number;
  lastRecallTime: number;    // 上次回忆时间
  recallCount: number;       // 被回忆次数
}

/** 自主任务 */
export interface EchoTask {
  id: string;
  content: string;
  triggerTime: number;       // 触发时间
  status: "pending" | "done" | "expired";
  createTime: number;
}

/** 人生日志 */
export interface LifeLog {
  id: string;
  content: string;           // 日志内容
  activity: Activity;        // 当时在做什么
  mood: Mood;                // 当时心情
  timestamp: number;
}

/** 对话消息 */
export interface ChatMessage {
  id: string;
  role: "user" | "echo";
  content: string;
  timestamp: number;
}

/** 计算等级标题 */
export function getLevelTitle(level: number): string {
  if (level <= 3) return "萌新";
  if (level <= 10) return "伙伴";
  if (level <= 25) return "知己";
  if (level <= 50) return "灵魂挚友";
  return "另一个你";
}

/** 生成唯一 ID */
export function genId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}
