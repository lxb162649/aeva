# memory_system.py — AEVA 记忆系统 v2
# 记忆分层：短期记忆 / 长期记忆 / 核心记忆
# 遗忘曲线：记忆随时间衰减，被回忆时强化
# 记忆整合：定期将短期记忆整合为长期记忆

import math

from datetime import datetime
from uuid import uuid4


from models import DataStore
from logger import get_logger

log = get_logger("Memory")


# ---- 记忆层级定义 ----
MEMORY_LAYERS = {
    "short_term": {
        "label": "短期记忆",
        "max_count": 50,  # 短期记忆最多保留 50 条
        "base_decay": 0.15,  # 每小时衰减 15% 的强度
    },
    "long_term": {
        "label": "长期记忆",
        "max_count": 200,  # 长期记忆最多保留 200 条
        "base_decay": 0.005,  # 每小时衰减 0.5%
    },
    "core": {
        "label": "核心记忆",
        "max_count": 30,  # 核心记忆最多 30 条（最珍贵的记忆）
        "base_decay": 0.0,  # 核心记忆永不遗忘
    },
}


class MemorySystem:
    """
    记忆系统 v2：管理 AEVA 的分层记忆
    - 短期记忆：最近的对话和事件，容量有限，会自然遗忘
    - 长期记忆：被反复回忆或特别重要的记忆，长期保留
    - 核心记忆：与用户关系最关键的记忆，永久保存
    """

    def __init__(self, store: DataStore) -> None:
        self.store = store
        self._migrate_old_memories()

    # ============================================================
    # 添加记忆
    # ============================================================

    def add_memory(
        self,
        content: str,
        importance: float = 0.5,
        memory_type: str = "conversation",
        source: str = "user",
    ) -> dict[str, object]:
        """
        添加一条新记忆到短期记忆层。
        如果重要性 >= 0.8，直接标记为长期记忆。

        参数:
            content: 记忆内容
            importance: 重要性 (0~1)
            memory_type: 记忆类型 (conversation/emotion/event/knowledge/preference/thought)
            source: 来源 (user/self/system)
        """
        # 自动计算重要性（如果没有指定高重要性）
        if importance < 0.6:
            importance = self._calculate_importance(content)

        tags = self._extract_tags(content)

        # 判断初始记忆层
        layer = "long_term" if importance >= 0.8 else "short_term"

        memory: dict[str, object] = {
            "id": f"mem_{uuid4().hex[:8]}",
            "content": content,
            "type": memory_type,
            "layer": layer,
            "importance": round(importance, 3),
            "strength": 1.0,  # 记忆强度，初始为 1.0
            "recall_count": 0,  # 被回忆次数
            "last_recall_time": None,
            "create_time": datetime.now().isoformat(),
            "tags": tags,
            "source": source,
            "emotional_valence": self._detect_emotion(content),  # 情感色彩
        }
        self.store.add_memory(memory)
        return memory

    # ============================================================
    # 记忆召回
    # ============================================================

    def get_related(self, query: str, top_n: int = 5) -> list[dict[str, object]]:
        """
        基于关键词匹配召回相关记忆。
        综合考虑：关键词重叠 × 重要性 × 记忆强度 × 时间衰减。
        召回时会强化记忆（回忆使记忆更持久）。
        """
        memories = self.store.get_memories()
        query_words = set(self._extract_tags(query) + query.lower().split())
        scored: list[tuple[float, dict[str, object]]] = []
        now = datetime.now()

        for m in memories:
            # 收集记忆的标签和内容词
            raw_tags = m.get("tags", [])
            tags_list: list[str] = raw_tags if isinstance(raw_tags, list) else []
            tags = set(t.lower() for t in tags_list)
            content_words = set(str(m.get("content", "")).lower().split())

            # 计算关键词重叠
            overlap = len(query_words & (tags | content_words))
            if overlap == 0:
                continue

            # 计算综合分数
            importance = float(str(m.get("importance", 0.5)))
            strength = float(str(m.get("strength", 1.0)))

            # 时间衰减因子
            create_time_str = str(m.get("create_time", now.isoformat()))
            try:
                create_time = datetime.fromisoformat(create_time_str)
                hours_ago = max(0, (now - create_time).total_seconds() / 3600)
            except (ValueError, TypeError):
                hours_ago = 24
            time_factor = math.exp(-hours_ago / 168)  # 一周半衰期

            # 层级加分
            layer = str(m.get("layer", "short_term"))
            layer_bonus = {"core": 2.0, "long_term": 1.5, "short_term": 1.0}.get(
                layer, 1.0
            )

            score = overlap * importance * strength * time_factor * layer_bonus
            scored.append((score, m))

        # 排序取 top_n
        scored.sort(key=lambda x: x[0], reverse=True)
        results = [m for _, m in scored[:top_n]]

        # 召回强化：被回忆的记忆变得更持久
        self._reinforce_memories(results)

        return results

    def recall_by_type(
        self, memory_type: str, limit: int = 10
    ) -> list[dict[str, object]]:
        """按类型召回记忆"""
        memories = self.store.get_memories()
        typed = [m for m in memories if m.get("type") == memory_type]
        # 按强度 × 重要性排序
        typed.sort(
            key=lambda m: (
                float(str(m.get("strength", 0))) * float(str(m.get("importance", 0)))
            ),
            reverse=True,
        )
        return typed[:limit]

    def get_recent(self, limit: int = 10) -> list[dict[str, object]]:
        """获取最近的记忆"""
        memories = self.store.get_memories()
        return memories[-limit:]

    # ============================================================
    # 遗忘与强化
    # ============================================================

    def apply_forgetting_curve(self) -> dict[str, int]:
        """
        应用遗忘曲线：降低记忆强度。
        强度降到 0.1 以下的短期记忆会被遗忘（删除）。
        长期记忆强度不会低于 0.3。
        核心记忆永不遗忘。
        """
        memories = self.store.get_memories()
        now = datetime.now()
        stats = {"forgotten": 0, "weakened": 0, "total": len(memories)}
        surviving: list[dict[str, object]] = []

        for m in memories:
            layer = str(m.get("layer", "short_term"))
            strength = float(str(m.get("strength", 1.0)))

            # 核心记忆不衰减
            if layer == "core":
                surviving.append(m)
                continue

            # 计算衰减量
            last_time_str = str(
                m.get("last_recall_time") or m.get("create_time", now.isoformat())
            )
            try:
                last_time = datetime.fromisoformat(last_time_str)
                hours_since = max(0, (now - last_time).total_seconds() / 3600)
            except (ValueError, TypeError):
                hours_since = 1

            layer_config = MEMORY_LAYERS.get(layer, MEMORY_LAYERS["short_term"])
            decay_rate = float(str(layer_config["base_decay"]))

            # 回忆次数越多，衰减越慢
            recall_count = int(str(m.get("recall_count", 0)))
            recall_resistance = 1.0 / (1.0 + recall_count * 0.3)

            new_strength = strength * math.exp(
                -decay_rate * hours_since * recall_resistance
            )

            # 应用层级最低强度
            if layer == "long_term":
                new_strength = max(0.3, new_strength)

            m["strength"] = round(new_strength, 4)

            # 短期记忆强度过低则遗忘
            if layer == "short_term" and new_strength < 0.1:
                stats["forgotten"] += 1
                continue

            stats["weakened"] += 1 if new_strength < strength else 0
            surviving.append(m)

        # 写回存储
        self.store._write_json(self.store.memories_path, surviving)
        if stats["forgotten"] > 0:
            log.debug(
                "遗忘曲线: 遗忘 %d 条, 弱化 %d 条, 总计 %d 条",
                stats["forgotten"],
                stats["weakened"],
                stats["total"],
            )
        return stats

    def _reinforce_memories(self, memories: list[dict[str, object]]) -> None:
        """强化被回忆的记忆"""
        if not memories:
            return

        all_memories = self.store.get_memories()
        recalled_ids = {str(m.get("id")) for m in memories}
        now_str = datetime.now().isoformat()

        for m in all_memories:
            if str(m.get("id")) in recalled_ids:
                m["recall_count"] = int(str(m.get("recall_count", 0))) + 1
                m["last_recall_time"] = now_str
                # 回忆使强度恢复一部分
                old_strength = float(str(m.get("strength", 1.0)))
                m["strength"] = round(min(1.0, old_strength + 0.1), 4)

        self.store._write_json(self.store.memories_path, all_memories)

    # ============================================================
    # 记忆整合（短期 → 长期 → 核心）
    # ============================================================

    def consolidate_memories(self) -> dict[str, int]:
        """
        记忆整合：将满足条件的短期记忆晋升为长期记忆，
        将特别重要的长期记忆晋升为核心记忆。
        同时清理超出容量的旧记忆。

        晋升条件：
        - 短期 → 长期：回忆次数 >= 3 或 重要性 >= 0.7
        - 长期 → 核心：回忆次数 >= 10 且 重要性 >= 0.85 且 强度 >= 0.8
        """
        memories = self.store.get_memories()
        stats = {"promoted_to_long": 0, "promoted_to_core": 0, "pruned": 0}

        for m in memories:
            layer = str(m.get("layer", "short_term"))
            recall_count = int(str(m.get("recall_count", 0)))
            importance = float(str(m.get("importance", 0.5)))
            strength = float(str(m.get("strength", 0.5)))

            if layer == "short_term":
                # 短期 → 长期
                if recall_count >= 3 or importance >= 0.7:
                    m["layer"] = "long_term"
                    stats["promoted_to_long"] += 1

            elif layer == "long_term":
                # 长期 → 核心
                if recall_count >= 10 and importance >= 0.85 and strength >= 0.8:
                    m["layer"] = "core"
                    stats["promoted_to_core"] += 1

        # 容量控制：每层超出上限时，删除强度最低的记忆
        for layer_name, config in MEMORY_LAYERS.items():
            max_count = int(str(config["max_count"]))
            layer_memories = [m for m in memories if m.get("layer") == layer_name]
            if len(layer_memories) > max_count:
                # 按强度排序，保留最强的
                layer_memories.sort(
                    key=lambda m: float(str(m.get("strength", 0))), reverse=True
                )
                to_remove = {str(m.get("id")) for m in layer_memories[max_count:]}
                before_len = len(memories)
                memories = [m for m in memories if str(m.get("id")) not in to_remove]
                stats["pruned"] += before_len - len(memories)

        self.store._write_json(self.store.memories_path, memories)
        if stats["promoted_to_long"] or stats["promoted_to_core"] or stats["pruned"]:
            log.debug(
                "记忆整合: 晋升长期 %d, 晋升核心 %d, 裁剪 %d",
                stats["promoted_to_long"],
                stats["promoted_to_core"],
                stats["pruned"],
            )
        return stats

    # ============================================================
    # 记忆摘要
    # ============================================================

    def summarize(self, limit: int = 10) -> str:
        """生成记忆摘要，优先展示核心记忆和重要长期记忆"""
        memories = self.store.get_memories()
        if not memories:
            return "还没有任何记忆"

        # 按层级和重要性排序
        layer_order = {"core": 0, "long_term": 1, "short_term": 2}
        sorted_memories = sorted(
            memories,
            key=lambda m: (
                layer_order.get(str(m.get("layer", "short_term")), 2),
                -float(str(m.get("importance", 0))),
            ),
        )

        parts: list[str] = []
        for m in sorted_memories[:limit]:
            content = str(m.get("content", ""))[:50]
            layer = str(m.get("layer", "short_term"))
            layer_label = MEMORY_LAYERS.get(layer, {}).get("label", "记忆")
            parts.append(f"[{layer_label}] {content}")

        return "；".join(parts)

    def get_memory_stats(self) -> dict[str, int]:
        """获取各层记忆的数量统计"""
        memories = self.store.get_memories()
        stats: dict[str, int] = {"total": len(memories)}
        for layer_name in MEMORY_LAYERS:
            stats[layer_name] = sum(1 for m in memories if m.get("layer") == layer_name)
        return stats

    # ============================================================
    # 工具方法
    # ============================================================

    def _calculate_importance(self, text: str) -> float:
        """自动计算记忆的重要性"""
        base = 0.3

        # 长度加分
        if len(text) > 50:
            base += 0.1
        if len(text) > 100:
            base += 0.1

        # 情感词加分
        emotion_words = [
            "喜欢",
            "爱",
            "讨厌",
            "害怕",
            "希望",
            "想",
            "梦想",
            "感谢",
            "对不起",
            "难过",
            "开心",
            "生气",
            "担心",
            "相信",
            "信任",
            "在乎",
            "重要",
            "特别",
            "永远",
        ]
        for word in emotion_words:
            if word in text:
                base += 0.05

        # 个人信息加分（包含"我"相关的内容通常更重要）
        personal_patterns = ["我叫", "我的名字", "我喜欢", "我讨厌", "我的", "我想"]
        for pattern in personal_patterns:
            if pattern in text:
                base += 0.1
                break

        return min(1.0, base)

    def _extract_tags(self, text: str) -> list[str]:
        """
        简单分词提取标签：
        将中文标点替换为空格，按空格分词，过滤短词。
        """
        cleaned = text
        for punct in [
            "，",
            "。",
            ",",
            ".",
            "！",
            "？",
            "!",
            "?",
            "；",
            "：",
            ":",
            "、",
            '"',
            "'",
            "（",
            "）",
            "(",
            ")",
            "…",
            "~",
            "——",
        ]:
            cleaned = cleaned.replace(punct, " ")
        words = cleaned.split()
        return [w for w in words if len(w) >= 2][:8]

    def _detect_emotion(self, text: str) -> str:
        """检测文本的情感色彩"""
        positive_words = [
            "开心",
            "喜欢",
            "爱",
            "感谢",
            "棒",
            "好",
            "快乐",
            "幸福",
            "哈哈",
            "嘿",
        ]
        negative_words = [
            "难过",
            "讨厌",
            "害怕",
            "生气",
            "烦",
            "累",
            "痛",
            "伤心",
            "孤独",
        ]

        pos_count = sum(1 for w in positive_words if w in text)
        neg_count = sum(1 for w in negative_words if w in text)

        if pos_count > neg_count:
            return "positive"
        elif neg_count > pos_count:
            return "negative"
        return "neutral"

    def _migrate_old_memories(self) -> None:
        """迁移旧版记忆数据，补充 v2 新字段"""
        memories = self.store.get_memories()
        changed = False

        for m in memories:
            if "layer" not in m:
                m["layer"] = "short_term"
                m["strength"] = 0.8
                m["recall_count"] = 0
                m["last_recall_time"] = None
                m["source"] = "user"
                m["emotional_valence"] = "neutral"
                if "type" not in m:
                    m["type"] = "conversation"
                changed = True

        if changed:
            self.store._write_json(self.store.memories_path, memories)
