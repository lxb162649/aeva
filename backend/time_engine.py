# time_engine.py — AEVA 时间引擎 v2
# 最核心模块：让 AEVA 随时间独自存活、成长
# 整合情感系统：心情漂移由概率矩阵驱动

import asyncio
from datetime import datetime

from models import DataStore
from emotion_system import EmotionSystem


class TimeEngine:
    """时间引擎 v2：每隔固定间隔执行一次 tick，驱动 AEVA 的生命节律"""

    def __init__(self, store: DataStore, emotion: EmotionSystem) -> None:
        self.store = store
        self.emotion = emotion
        self.running: bool = False
        self.tick_interval: int = 30  # 每30秒一个 tick

    async def start(self) -> None:
        """启动时间引擎主循环"""
        self.running = True
        while self.running:
            await self.tick()
            await asyncio.sleep(self.tick_interval)

    def stop(self) -> None:
        """停止时间引擎"""
        self.running = False

    async def tick(self) -> None:
        """一次心跳：更新存活时间、心情、精力、经验"""
        echo = self.store.load_echo()
        now = datetime.now()

        # 计算自上次活跃以来的时间差（秒）
        last_active_str = str(echo.get("last_active", now.isoformat()))
        try:
            last = datetime.fromisoformat(last_active_str)
        except (ValueError, TypeError):
            last = now
        delta_seconds = (now - last).total_seconds()

        # 更新存活总时间
        prev_total = float(str(echo.get("total_life_seconds", 0)))
        echo["total_life_seconds"] = prev_total + delta_seconds

        # 更新最后活跃时间
        echo["last_active"] = now.isoformat()

        # 使用情感系统更新心情（概率矩阵驱动）
        new_mood = self.emotion.drift_mood(echo, delta_seconds)
        echo["mood"] = new_mood

        # 更新精力（随时间缓慢恢复）
        self._update_energy(echo, delta_seconds)

        # 亲密度衰减检查（长时间离线）
        offline_hours = delta_seconds / 3600
        if offline_hours > 24:
            self.emotion.decay_intimacy(echo, offline_hours)

        # 经验增长
        self._grow_exp(echo)

        self.store.save_echo(echo)

    def _update_energy(self, echo: dict[str, object], delta: float) -> None:
        """
        精力随时间变化：
        - 基础恢复：每分钟恢复 0.5 点，单次最多 5 点
        - 睡眠加速恢复：每分钟恢复 2 点
        - 上限 100
        """
        current = float(str(echo.get("energy", 50)))
        activity = str(echo.get("activity", "waiting"))

        if activity in ("sleeping", "dreaming", "meditating"):
            # 休息类活动恢复更快
            recovery = min(delta / 60 * 2, 10)
        else:
            recovery = min(delta / 60 * 0.5, 5)

        echo["energy"] = min(100.0, current + recovery)

    def _grow_exp(self, echo: dict[str, object]) -> None:
        """每次 tick 增加1点经验，达到升级阈值时升级"""
        exp = int(str(echo.get("exp", 0)))
        level = int(str(echo.get("level", 1)))

        exp += 1
        # 升级条件：经验 >= 当前等级 * 100
        if exp >= level * 100:
            exp = 0
            level += 1
            # 升级时触发情感事件
            self.emotion.record_emotion_event(
                echo,
                "level_up",
                f"升到了 Lv.{level}！",
                intensity=0.8,
            )

        echo["exp"] = exp
        echo["level"] = level
