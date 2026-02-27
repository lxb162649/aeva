# emotion_system.py — AEVA 情感系统
# 精细化的情感模型：多维情感、亲密度、情感记忆
# 让 AEVA 拥有更真实、更丰富的情感体验

import random
import math
from datetime import datetime
from uuid import uuid4
from typing import Optional

from models import DataStore
from logger import get_logger

log = get_logger("Emotion")


# ---- 心情类型定义 ----
# 7 种基础心情，比 MVP 版增加了 excited / sleepy / curious
MOODS = ["calm", "happy", "lonely", "thinking", "excited", "sleepy", "curious"]

# 心情的中文名和 emoji 映射
MOOD_DISPLAY: dict[str, dict[str, str]] = {
    "calm": {"zh": "平静", "emoji": "😌"},
    "happy": {"zh": "愉快", "emoji": "😊"},
    "lonely": {"zh": "想念", "emoji": "🥺"},
    "thinking": {"zh": "沉思", "emoji": "🤔"},
    "excited": {"zh": "兴奋", "emoji": "🤩"},
    "sleepy": {"zh": "困倦", "emoji": "😴"},
    "curious": {"zh": "好奇", "emoji": "🧐"},
}

# ---- 心情转移概率矩阵 ----
# 格式: {当前心情: {目标心情: 概率权重}}
# 权重越高越容易转移到该心情
MOOD_TRANSITIONS: dict[str, dict[str, float]] = {
    "calm": {
        "calm": 40,
        "thinking": 25,
        "curious": 15,
        "lonely": 10,
        "happy": 8,
        "sleepy": 2,
    },
    "happy": {
        "happy": 35,
        "excited": 20,
        "calm": 20,
        "curious": 15,
        "thinking": 8,
        "lonely": 2,
    },
    "lonely": {
        "lonely": 30,
        "thinking": 25,
        "calm": 20,
        "sleepy": 10,
        "happy": 10,
        "curious": 5,
    },
    "thinking": {
        "thinking": 30,
        "calm": 25,
        "curious": 20,
        "excited": 10,
        "lonely": 10,
        "happy": 5,
    },
    "excited": {
        "excited": 25,
        "happy": 30,
        "curious": 20,
        "calm": 15,
        "thinking": 8,
        "sleepy": 2,
    },
    "sleepy": {
        "sleepy": 40,
        "calm": 30,
        "thinking": 15,
        "lonely": 10,
        "happy": 3,
        "curious": 2,
    },
    "curious": {
        "curious": 30,
        "thinking": 25,
        "excited": 15,
        "happy": 15,
        "calm": 10,
        "lonely": 5,
    },
}

# ---- 亲密度等级定义 ----
INTIMACY_LEVELS: list[dict[str, object]] = [
    {"min": 0, "max": 50, "title": "初识", "description": "刚刚认识的陌生人"},
    {"min": 50, "max": 150, "title": "认识", "description": "有过几次交流"},
    {"min": 150, "max": 400, "title": "熟悉", "description": "聊天变得自然了"},
    {"min": 400, "max": 800, "title": "朋友", "description": "可以分享心事了"},
    {"min": 800, "max": 1500, "title": "好友", "description": "互相信赖的存在"},
    {"min": 1500, "max": 3000, "title": "知己", "description": "心灵相通的伙伴"},
    {"min": 3000, "max": 6000, "title": "挚友", "description": "无话不谈的灵魂伴侣"},
    {
        "min": 6000,
        "max": 99999,
        "title": "命运之人",
        "description": "超越一切定义的羁绊",
    },
]


class EmotionSystem:
    """情感系统：管理 AEVA 的心情、亲密度和情感记忆"""

    def __init__(self, store: DataStore) -> None:
        self.store = store

    # ============================================================
    # 心情显示
    # ============================================================

    def get_mood_display(self, echo: dict[str, object]) -> dict[str, str]:
        """获取当前心情的中文名和 emoji，用于前端展示"""
        mood = str(echo.get("mood", "calm"))
        display = MOOD_DISPLAY.get(mood, MOOD_DISPLAY["calm"])
        return {"mood": mood, "zh": display["zh"], "emoji": display["emoji"]}

    # ============================================================
    # 情感记忆（预留）
    # ============================================================

    def record_emotion_event(
        self, echo: dict[str, object], event_type: str, detail: str
    ) -> dict[str, object]:
        """
        记录一次情感事件到 echo 的情感记忆中。
        用于未来回忆和情感叙事。
        """
        memory = {
            "id": str(uuid4()),
            "type": event_type,
            "detail": detail,
            "mood": str(echo.get("mood", "calm")),
            "intimacy": self.get_intimacy(echo),
            "timestamp": datetime.utcnow().isoformat(),
        }
        emotion_memories: list = echo.setdefault("emotion_memories", [])  # type: ignore
        emotion_memories.append(memory)
        # 只保留最近 100 条情感记忆
        if len(emotion_memories) > 100:
            echo["emotion_memories"] = emotion_memories[-100:]
        return memory

    # ============================================================
    # 心情管理
    # ============================================================

    def drift_mood(self, echo: dict[str, object], delta_seconds: float) -> str:
        """
        心情自然漂移：基于概率矩阵决定心情变化。
        考虑精力、离线时间、互动频率等因素调整概率。

        参数:
            echo: Echo 实体状态
            delta_seconds: 距上次更新的秒数

        返回:
            新的心情字符串
        """
        current_mood = str(echo.get("mood", "calm"))
        energy = float(str(echo.get("energy", 50)))

        # 获取当前心情的转移概率
        transitions = dict(MOOD_TRANSITIONS.get(current_mood, MOOD_TRANSITIONS["calm"]))

        # 根据精力调整概率
        if energy < 20:
            # 精力极低 → 大幅增加 sleepy 概率
            transitions["sleepy"] = transitions.get("sleepy", 0) + 40
            transitions["excited"] = max(0, transitions.get("excited", 0) - 10)
            transitions["happy"] = max(0, transitions.get("happy", 0) - 5)
        elif energy < 40:
            # 精力偏低 → 增加 sleepy 和 thinking
            transitions["sleepy"] = transitions.get("sleepy", 0) + 15
            transitions["thinking"] = transitions.get("thinking", 0) + 10
        elif energy > 80:
            # 精力充沛 → 增加 happy / excited / curious
            transitions["happy"] = transitions.get("happy", 0) + 10
            transitions["excited"] = transitions.get("excited", 0) + 8
            transitions["curious"] = transitions.get("curious", 0) + 8
            transitions["sleepy"] = max(0, transitions.get("sleepy", 0) - 10)

        # 长时间无人互动 → 增加 lonely
        if delta_seconds > 3600:  # 超过 1 小时
            transitions["lonely"] = transitions.get("lonely", 0) + 40
        elif delta_seconds > 1800:  # 超过 30 分钟
            transitions["lonely"] = transitions.get("lonely", 0) + 20

        # 按权重随机选择
        return self._weighted_choice(transitions)

    def on_user_interaction(self, echo: dict[str, object]) -> str:
        """
        用户互动时触发情感反应。
        根据当前心情决定互动后的心情变化。
        """
        current_mood = str(echo.get("mood", "calm"))
        energy = float(str(echo.get("energy", 50)))

        # 互动会恢复一些精力
        echo["energy"] = min(100.0, energy + 3)

        # 根据当前心情，互动后的情感反应
        reaction_map: dict[str, dict[str, float]] = {
            "calm": {"happy": 40, "calm": 30, "curious": 20, "excited": 10},
            "happy": {"happy": 50, "excited": 30, "curious": 20},
            "lonely": {"happy": 50, "excited": 20, "calm": 20, "curious": 10},
            "thinking": {"curious": 35, "happy": 25, "calm": 25, "thinking": 15},
            "excited": {"excited": 40, "happy": 40, "curious": 20},
            "sleepy": {"calm": 40, "happy": 20, "sleepy": 30, "thinking": 10},
            "curious": {"curious": 40, "excited": 25, "happy": 25, "thinking": 10},
        }

        reactions = reaction_map.get(current_mood, {"happy": 50, "calm": 50})
        new_mood = self._weighted_choice(reactions)
        echo["mood"] = new_mood
        return new_mood

    # ============================================================
    # 亲密度系统
    # ============================================================

    def get_intimacy(self, echo: dict[str, object]) -> float:
        """获取当前亲密度值"""
        return float(str(echo.get("intimacy", 0)))

    def add_intimacy(self, echo: dict[str, object], amount: float) -> float:
        """
        增加亲密度。不同行为增加不同的亲密度：
        - 普通聊天: +2~5
        - 分享心事: +5~10
        - 长时间陪伴: +3~8
        - 每日首次互动: +10
        """
        current = self.get_intimacy(echo)
        new_value = max(0, current + amount)
        echo["intimacy"] = new_value
        return new_value

    def decay_intimacy(self, echo: dict[str, object], offline_hours: float) -> float:
        """
        亲密度随离线时间缓慢衰减。
        衰减速率很慢 —— 关系的建立需要时间，但不应该轻易被遗忘。
        超过 24 小时才开始衰减，且有最低保底值。
        """
        current = self.get_intimacy(echo)
        if offline_hours <= 24:
            return current

        # 超过 24 小时后，每额外 24 小时衰减 2%，最低保留 80% 的当前值
        excess_days = (offline_hours - 24) / 24
        decay_rate = min(0.2, excess_days * 0.02)  # 最多衰减 20%
        new_value = max(current * 0.8, current * (1 - decay_rate))
        echo["intimacy"] = new_value
        return new_value

    def get_intimacy_level(self, echo: dict[str, object]) -> dict[str, object]:
        """获取当前亲密度等级信息"""
        intimacy = self.get_intimacy(echo)
        for level in INTIMACY_LEVELS:
            min_val = float(str(level["min"]))
            max_val = float(str(level["max"]))
            if min_val <= intimacy < max_val:
                progress = (intimacy - min_val) / (max_val - min_val)
                return {
                    "title": level["title"],
                    "description": level["description"],
                    "value": intimacy,
                    "progress": round(progress, 3),
                    "next_level_at": max_val,
                }
        # 最高等级
        last = INTIMACY_LEVELS[-1]
        return {
            "title": last["title"],
            "description": last["description"],
            "value": intimacy,
            "progress": 1.0,
            "next_level_at": None,
        }

    # ============================================================
    # 情感记忆
    # ============================================================

    def record_emotion_event(
        self,
        echo: dict[str, object],
        event_type: str,
        description: str,
        intensity: float = 0.5,
    ) -> dict[str, object]:
        """
        记录一次情感事件（如开心的对话、被冷落的感受等）。
        情感记忆会影响后续的心情漂移倾向。
        """
        emotion_event: dict[str, object] = {
            "id": f"emo_{uuid4().hex[:8]}",
            "type": event_type,
            "description": description,
            "mood_at_time": str(echo.get("mood", "calm")),
            "intensity": intensity,
            "create_time": datetime.now().isoformat(),
        }

        # 存入情感记忆列表（存在 echo 状态中）
        emotion_memory: list[dict[str, object]] = echo.get("emotion_memory", [])  # type: ignore[assignment]
        if not isinstance(emotion_memory, list):
            emotion_memory = []
        emotion_memory.append(emotion_event)

        # 只保留最近 50 条情感记忆
        if len(emotion_memory) > 50:
            emotion_memory = emotion_memory[-50:]

        echo["emotion_memory"] = emotion_memory
        return emotion_event

    def get_recent_emotions(
        self, echo: dict[str, object], limit: int = 10
    ) -> list[dict[str, object]]:
        """获取最近的情感记忆"""
        emotion_memory: list[dict[str, object]] = echo.get("emotion_memory", [])  # type: ignore[assignment]
        if not isinstance(emotion_memory, list):
            return []
        return emotion_memory[-limit:]

    def get_emotion_tendency(self, echo: dict[str, object]) -> dict[str, float]:
        """
        分析最近情感记忆的倾向，返回各心情的权重。
        用于调整自然心情漂移的倾向。
        """
        recent = self.get_recent_emotions(echo, limit=20)
        if not recent:
            return {}

        tendency: dict[str, float] = {}
        now = datetime.now()

        for event in recent:
            mood = str(event.get("mood_at_time", "calm"))
            intensity = float(str(event.get("intensity", 0.5)))
            # 时间衰减：越近的情感记忆权重越高
            create_time_str = str(event.get("create_time", now.isoformat()))
            try:
                create_time = datetime.fromisoformat(create_time_str)
                hours_ago = (now - create_time).total_seconds() / 3600
            except (ValueError, TypeError):
                hours_ago = 24
            time_weight = math.exp(-hours_ago / 12)  # 12 小时半衰期
            weight = intensity * time_weight
            tendency[mood] = tendency.get(mood, 0) + weight

        return tendency

    # ============================================================
    # 工具方法
    # ============================================================

    @staticmethod
    def _weighted_choice(weights: dict[str, float]) -> str:
        """按权重随机选择"""
        items = list(weights.items())
        total = sum(w for _, w in items)
        if total <= 0:
            return "calm"
        r = random.uniform(0, total)
        cumulative = 0.0
        for item, weight in items:
            cumulative += weight
            if r <= cumulative:
                return item
        return items[-1][0]

    @staticmethod
    def get_mood_display(mood: str) -> dict[str, str]:
        """获取心情的显示信息"""
        return MOOD_DISPLAY.get(mood, {"zh": "未知", "emoji": "❓"})
