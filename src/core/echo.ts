// Echo 实体状态管理 —— 它的"身体"
import { EchoState, Mood, Activity } from "./types.js";

/** Echo 的默认初始状态 */
function createDefaultState(): EchoState {
  const now = Date.now();
  return {
    id: "echo_001",
    name: "Echo",
    createTime: now,
    lastActive: now,
    totalLifeSeconds: 0,
    mood: "calm",
    activity: "waiting",
    energy: 100,
    level: 1,
    exp: 0,
    personality: {
      talkativeness: 0.6,
      warmth: 0.8,
      curiosity: 0.7,
    },
  };
}

/** 心情之间的自然转换概率 */
const MOOD_TRANSITIONS: Record<Mood, Partial<Record<Mood, number>>> = {
  calm:     { thinking: 0.3, lonely: 0.2, happy: 0.1 },
  happy:    { calm: 0.4, excited: 0.2 },
  lonely:   { calm: 0.3, thinking: 0.3 },
  thinking: { calm: 0.3, excited: 0.1, happy: 0.1 },
  excited:  { happy: 0.4, calm: 0.3 },
  sleepy:   { calm: 0.5, thinking: 0.1 },
};

/** 心情的中文描述 */
export const MOOD_LABELS: Record<Mood, string> = {
  calm: "平静",
  happy: "开心",
  lonely: "有点想你",
  thinking: "沉思中",
  excited: "兴奋",
  sleepy: "犯困",
};

/** 活动的中文描述 */
export const ACTIVITY_LABELS: Record<Activity, string> = {
  sleeping: "睡觉中",
  thinking: "在思考",
  learning: "学习中",
  organizing: "整理记忆",
  waiting: "等你回来",
};

export class Echo {
  state: EchoState;

  constructor(saved?: EchoState) {
    this.state = saved ?? createDefaultState();
  }

  /** 时间流逝：更新存活时间、精力、心情 */
  tick(deltaSeconds: number): void {
    this.state.totalLifeSeconds += deltaSeconds;
    this.state.lastActive = Date.now();

    // 精力随时间缓慢恢复（如果在休息）或消耗
    if (this.state.activity === "sleeping") {
      this.state.energy = Math.min(100, this.state.energy + deltaSeconds * 0.05);
    } else {
      this.state.energy = Math.max(0, this.state.energy - deltaSeconds * 0.005);
    }

    // 精力太低就想睡
    if (this.state.energy < 20) {
      this.state.mood = "sleepy";
      this.state.activity = "sleeping";
    }

    // 随机心情漂移
    if (Math.random() < 0.1) {
      this.driftMood();
    }
  }

  /** 心情自然漂移 */
  private driftMood(): void {
    const transitions = MOOD_TRANSITIONS[this.state.mood];
    const roll = Math.random();
    let cumulative = 0;
    for (const [mood, prob] of Object.entries(transitions)) {
      cumulative += prob as number;
      if (roll < cumulative) {
        this.state.mood = mood as Mood;
        return;
      }
    }
    // 没命中就保持当前
  }

  /** 设置活动状态 */
  setActivity(activity: Activity): void {
    this.state.activity = activity;
  }

  /** 增加经验，自动升级 */
  addExp(amount: number): boolean {
    this.state.exp += amount;
    const threshold = this.state.level * 100; // 每级需要 level*100 经验
    if (this.state.exp >= threshold) {
      this.state.exp -= threshold;
      this.state.level += 1;
      this.state.mood = "excited";
      return true; // 升级了
    }
    return false;
  }

  /** 用户互动时：提升心情和精力 */
  onUserInteraction(): void {
    this.state.energy = Math.min(100, this.state.energy + 5);
    if (this.state.mood === "lonely") {
      this.state.mood = "happy";
    }
    if (this.state.activity === "waiting" || this.state.activity === "sleeping") {
      this.state.activity = "thinking";
    }
  }

  /** 获取存活时间的友好描述 */
  getAgeDescription(): string {
    const s = this.state.totalLifeSeconds;
    if (s < 60) return `${Math.floor(s)} 秒`;
    if (s < 3600) return `${Math.floor(s / 60)} 分钟`;
    if (s < 86400) return `${Math.floor(s / 3600)} 小时 ${Math.floor((s % 3600) / 60)} 分钟`;
    const days = Math.floor(s / 86400);
    const hours = Math.floor((s % 86400) / 3600);
    return `${days} 天 ${hours} 小时`;
  }

  /** 序列化 */
  toJSON(): EchoState {
    return { ...this.state };
  }
}
