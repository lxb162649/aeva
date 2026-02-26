# time_engine.py — AEVA 时间引擎
# 最核心模块：让 AEVA 随时间独自存活、成长
# 使用 asyncio 后台定时任务驱动生命周期

import asyncio
from datetime import datetime
from typing import Union

from models import DataStore

# Echo 字典值的联合类型（避免使用 any）
EchoValue = Union[str, int, float, dict[str, float]]
EchoDict = dict[str, EchoValue]


class TimeEngine:
    """时间引擎：每隔固定间隔执行一次 tick，驱动 AEVA 的生命节律"""

    def __init__(self, store: DataStore) -> None:
        self.store = store
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
        last = datetime.fromisoformat(last_active_str)
        delta_seconds = (now - last).total_seconds()

        # 更新存活总时间
        prev_total: float = float(str(echo.get("total_life_seconds", 0)))
        echo["total_life_seconds"] = prev_total + delta_seconds

        # 更新最后活跃时间
        echo["last_active"] = now.isoformat()

        # 更新心情（基于精力和离线时间）
        self._update_mood(echo, delta_seconds)

        # 更新精力（随时间缓慢恢复）
        self._update_energy(echo, delta_seconds)

        # 经验增长
        self._grow_exp(echo)

        self.store.save_echo(echo)

    def _update_mood(self, echo: dict[str, object], delta: float) -> None:
        """
        根据离线时间和精力更新心情：
        - 离线超过1小时 → lonely（孤独）
        - 精力低于30 → thinking（沉思）
        - 精力高于70且离线不超过10分钟 → happy（开心）
        - 其他 → calm（平静）
        """
        energy: float = float(str(echo.get("energy", 50)))

        if delta > 3600:
            echo["mood"] = "lonely"
        elif energy < 30:
            echo["mood"] = "thinking"
        elif energy > 70 and delta <= 600:
            echo["mood"] = "happy"
        else:
            echo["mood"] = "calm"

    def _update_energy(self, echo: dict[str, object], delta: float) -> None:
        """精力随时间缓慢恢复，每分钟恢复1点，单次最多恢复5点，上限100"""
        current: float = float(str(echo.get("energy", 50)))
        recovery = min(delta / 60, 5)  # 每分钟恢复1点，最多5点
        echo["energy"] = min(100.0, current + recovery)

    def _grow_exp(self, echo: dict[str, object]) -> None:
        """每次 tick 增加1点经验，达到升级阈值时升级"""
        exp: int = int(str(echo.get("exp", 0)))
        level: int = int(str(echo.get("level", 1)))

        exp += 1
        # 升级条件：经验 >= 当前等级 * 100
        if exp >= level * 100:
            exp = 0
            level += 1

        echo["exp"] = exp
        echo["level"] = level
