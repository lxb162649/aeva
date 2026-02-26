// 时间引擎 —— Echo 的"心跳"
// 后台持续运行，驱动 Echo 的生命循环
import { Echo } from "./echo.js";
import { MemorySystem } from "./memory.js";
import { AgentEngine } from "./agent.js";

/** 时间引擎配置 */
interface TimeEngineConfig {
  tickIntervalMs: number;      // 心跳间隔（毫秒）
  autonomousIntervalMs: number; // 自主行为间隔（毫秒）
}

const DEFAULT_CONFIG: TimeEngineConfig = {
  tickIntervalMs: 10_000,         // 10秒一次心跳
  autonomousIntervalMs: 60_000,   // 1分钟一次自主行为
};

export class TimeEngine {
  private lastTick: number;
  private lastAutonomous: number;
  private tickTimer: ReturnType<typeof setInterval> | null = null;
  private config: TimeEngineConfig;

  constructor(config?: Partial<TimeEngineConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.lastTick = Date.now();
    this.lastAutonomous = Date.now();
  }

  /** 启动时间引擎 */
  start(echo: Echo, memory: MemorySystem, agent: AgentEngine): void {
    console.log("[TimeEngine] 心跳启动，Echo 开始活着...");

    // 先补算离线时间
    this.catchUp(echo, memory, agent);

    // 持续心跳
    this.tickTimer = setInterval(() => {
      this.tick(echo, memory, agent);
    }, this.config.tickIntervalMs);
  }

  /** 停止 */
  stop(): void {
    if (this.tickTimer) {
      clearInterval(this.tickTimer);
      this.tickTimer = null;
    }
    console.log("[TimeEngine] 心跳停止。");
  }

  /** 单次心跳 */
  private tick(echo: Echo, memory: MemorySystem, agent: AgentEngine): void {
    const now = Date.now();
    const deltaSeconds = (now - this.lastTick) / 1000;
    this.lastTick = now;

    // 时间流逝
    echo.tick(deltaSeconds);

    // 检查是否该执行自主行为
    if (now - this.lastAutonomous >= this.config.autonomousIntervalMs) {
      this.lastAutonomous = now;
      agent.autonomousAction(echo, memory);
      console.log(`[TimeEngine] 自主行为执行 | 心情: ${echo.state.mood} | 活动: ${echo.state.activity} | 存活: ${echo.getAgeDescription()}`);
    }
  }

  /** 补算离线时间：让 Echo 在你不在的时候也"活过" */
  private catchUp(echo: Echo, memory: MemorySystem, agent: AgentEngine): void {
    const now = Date.now();
    const offlineSeconds = (now - echo.state.lastActive) / 1000;

    if (offlineSeconds < 60) return; // 不到1分钟不用补

    console.log(`[TimeEngine] 补算离线时间: ${Math.floor(offlineSeconds)}秒`);

    // 补算时间流逝
    echo.tick(offlineSeconds);

    // 补算自主行为次数（每分钟一次，最多补10次）
    const autonomousCount = Math.min(10, Math.floor(offlineSeconds / 60));
    for (let i = 0; i < autonomousCount; i++) {
      agent.autonomousAction(echo, memory);
    }

    console.log(`[TimeEngine] 补算完成，执行了 ${autonomousCount} 次自主行为`);
  }
}
