// 记忆系统 —— Echo 的"大脑"
import { Memory, genId } from "./types.js";

/** 从文本中提取关键词（简易版） */
function extractTags(text: string): string[] {
  // 移除标点，按空格/逗号分词，取长度>1的词
  const words = text
    .replace(/[，。！？、；：""''（）\[\]{},.!?;:'"()\s]+/g, " ")
    .split(" ")
    .filter((w) => w.length > 1);
  // 去重，最多5个
  return [...new Set(words)].slice(0, 5);
}

/** 计算文本重要性（简易版：越长、越有情绪词越重要） */
function calculateImportance(text: string): number {
  let score = 0.3; // 基础分
  // 长度加分
  if (text.length > 20) score += 0.1;
  if (text.length > 50) score += 0.1;
  if (text.length > 100) score += 0.1;
  // 情绪词加分
  const emotionalWords = ["想", "要", "希望", "梦想", "目标", "计划", "喜欢", "讨厌", "害怕", "开心", "难过", "重要"];
  for (const word of emotionalWords) {
    if (text.includes(word)) score += 0.05;
  }
  return Math.min(1, score);
}

export class MemorySystem {
  private memories: Memory[] = [];

  constructor(saved?: Memory[]) {
    this.memories = saved ?? [];
  }

  /** 添加新记忆 */
  add(content: string): Memory {
    const memory: Memory = {
      id: genId("mem"),
      content,
      importance: calculateImportance(content),
      tags: extractTags(content),
      createTime: Date.now(),
      lastRecallTime: Date.now(),
      recallCount: 0,
    };
    this.memories.push(memory);
    return memory;
  }

  /** 搜索相关记忆（简单关键词匹配） */
  getRelated(query: string, limit = 5): Memory[] {
    const queryWords = extractTags(query);

    const scored = this.memories.map((m) => {
      let score = 0;
      // 关键词匹配
      for (const word of queryWords) {
        if (m.content.includes(word)) score += 1;
        if (m.tags.includes(word)) score += 0.5;
      }
      // 重要性加权
      score *= m.importance;
      // 最近的记忆稍微优先
      const age = (Date.now() - m.createTime) / (1000 * 3600);
      score *= Math.max(0.5, 1 - age * 0.01);
      return { memory: m, score };
    });

    return scored
      .filter((s) => s.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, limit)
      .map((s) => {
        // 标记被回忆
        s.memory.lastRecallTime = Date.now();
        s.memory.recallCount += 1;
        return s.memory;
      });
  }

  /** 获取最近的记忆 */
  getRecent(limit = 10): Memory[] {
    return this.memories
      .slice()
      .sort((a, b) => b.createTime - a.createTime)
      .slice(0, limit);
  }

  /** 获取最重要的记忆 */
  getImportant(limit = 5): Memory[] {
    return this.memories
      .slice()
      .sort((a, b) => b.importance - a.importance)
      .slice(0, limit);
  }

  /** 记忆总数 */
  get count(): number {
    return this.memories.length;
  }

  /** 整理记忆：生成摘要文本 */
  summarize(): string {
    if (this.memories.length === 0) return "还没有任何记忆。";
    const important = this.getImportant(3);
    const recent = this.getRecent(3);
    const parts: string[] = [];
    if (important.length > 0) {
      parts.push("重要记忆：" + important.map((m) => m.content).join("；"));
    }
    if (recent.length > 0) {
      parts.push("最近记忆：" + recent.map((m) => m.content).join("；"));
    }
    return parts.join("\n");
  }

  /** 序列化 */
  toJSON(): Memory[] {
    return this.memories.map((m) => ({ ...m }));
  }
}
