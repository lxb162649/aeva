# memory_system.py — AEVA 记忆系统
# 负责记忆的存储、召回和摘要

from datetime import datetime
from uuid import uuid4

from models import DataStore


class MemorySystem:
    """记忆系统：管理 AEVA 的记忆存取与关联召回"""

    def __init__(self, store: DataStore) -> None:
        self.store = store

    def add_memory(self, content: str, importance: float = 0.5) -> dict[str, object]:
        """添加一条新记忆，自动提取标签"""
        tags = self._extract_tags(content)
        memory: dict[str, object] = {
            "id": f"mem_{uuid4().hex[:8]}",
            "type": "memory",
            "content": content,
            "importance": importance,
            "create_time": datetime.now().isoformat(),
            "tags": tags,
        }
        self.store.add_memory(memory)
        return memory

    def get_related(self, query: str, top_n: int = 5) -> list[dict[str, object]]:
        """
        基于关键词匹配召回相关记忆。
        计算查询词与记忆标签/内容的重叠度，乘以重要性排序。
        """
        memories = self.store.get_memories()
        query_words = set(query.lower().split())
        scored: list[tuple[float, dict[str, object]]] = []

        for m in memories:
            # 收集记忆的标签和内容词
            raw_tags = m.get("tags", [])
            tags_list: list[str] = raw_tags if isinstance(raw_tags, list) else []
            tags = set(t.lower() for t in tags_list)
            content_words = set(str(m.get("content", "")).lower().split())

            # 计算重叠词数
            overlap = len(query_words & (tags | content_words))
            if overlap > 0:
                importance: float = float(str(m.get("importance", 0.5)))
                scored.append((overlap * importance, m))

        # 按得分降序排列
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:top_n]]

    def summarize(self) -> str:
        """返回最近5条记忆的摘要"""
        memories = self.store.get_memories()
        if not memories:
            return "还没有任何记忆"
        recent = memories[-5:]
        return "；".join(str(m.get("content", ""))[:30] for m in recent)

    def _extract_tags(self, text: str) -> list[str]:
        """
        简单分词提取标签：
        将中文标点替换为空格，按空格分词，过滤掉长度小于2的词，
        最多取前5个作为标签。
        """
        # 替换常见标点为空格
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
        ]:
            cleaned = cleaned.replace(punct, " ")
        words = cleaned.split()
        return [w for w in words if len(w) >= 2][:5]
