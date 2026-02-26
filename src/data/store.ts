// 持久化存储 —— Echo 的"记忆硬盘"
// 用 JSON 文件存储，零依赖
import fs from "node:fs";
import path from "node:path";
import { EchoState } from "../core/types.js";
import { Memory, LifeLog, EchoTask, ChatMessage } from "../core/types.js";

/** 完整的存档结构 */
export interface SaveData {
  echo: EchoState;
  memories: Memory[];
  agent: {
    logs: LifeLog[];
    tasks: EchoTask[];
    chatHistory: ChatMessage[];
  };
  savedAt: number;
}

const DATA_DIR = path.resolve("data");
const SAVE_FILE = path.join(DATA_DIR, "echo-save.json");

/** 确保数据目录存在 */
function ensureDir(): void {
  if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
  }
}

/** 保存数据 */
export function save(data: SaveData): void {
  ensureDir();
  data.savedAt = Date.now();
  fs.writeFileSync(SAVE_FILE, JSON.stringify(data, null, 2), "utf-8");
}

/** 加载数据 */
export function load(): SaveData | null {
  if (!fs.existsSync(SAVE_FILE)) return null;
  try {
    const raw = fs.readFileSync(SAVE_FILE, "utf-8");
    return JSON.parse(raw) as SaveData;
  } catch {
    console.error("[Store] 存档文件损坏，将重新开始");
    return null;
  }
}
