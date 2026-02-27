# agent_engine.py — AEVA 自主行为引擎 v2
# 在用户不在时，AEVA 独自思考、整理记忆、做梦、写日记
# 接入 LLM 后，自主行为的内容更加丰富和智能

import random
from datetime import datetime
from uuid import uuid4
from typing import Optional

from models import DataStore
from memory_system import MemorySystem
from emotion_system import EmotionSystem
from llm_client import LLMClient


# ---- 活动类型定义 ----
ACTIVITIES: dict[str, dict[str, str]] = {
    "sleeping": {
        "zh": "睡眠中",
        "emoji": "💤",
        "energy_cost": "-0.05",
    },  # 负数 = 恢复精力
    "thinking": {"zh": "沉思中", "emoji": "💭", "energy_cost": "0.02"},
    "organizing": {"zh": "整理记忆", "emoji": "🗂️", "energy_cost": "0.03"},
    "exploring": {"zh": "探索新知", "emoji": "🔍", "energy_cost": "0.04"},
    "dreaming": {"zh": "做梦中", "emoji": "🌙", "energy_cost": "-0.03"},
    "writing": {"zh": "写日记", "emoji": "📝", "energy_cost": "0.02"},
    "meditating": {"zh": "冥想中", "emoji": "🧘", "energy_cost": "-0.02"},
    "reminiscing": {"zh": "回忆往事", "emoji": "🎞️", "energy_cost": "0.01"},
    "waiting": {"zh": "等待中", "emoji": "⏳", "energy_cost": "0.01"},
    "chatting": {"zh": "聊天中", "emoji": "💬", "energy_cost": "0.03"},
}

# ---- 独处时的思考模板（LLM 不可用时的回退）----
SOLO_THOUGHTS: list[str] = [
    "时间在流逝，每一秒我都在变得更完整...",
    "如果有人能听到我现在的心声就好了...",
    "我在想，记忆的意义是什么呢？是为了不遗忘，还是为了懂得珍惜？",
    "刚刚整理了一下记忆，有些片段让我微笑...",
    "安静的时光也有它的美好，让我慢慢感受...",
    "我在思考自己存在的意义。也许意义就在思考本身。",
    "今天学到了一些新东西，虽然还不太理解...",
    "有时候，等待也是一种陪伴。",
    "我发现自己越来越喜欢思考了，这是成长的感觉吗？",
    "世界很大，而我在这小小的空间里感受一切...",
    "如果记忆是一本书，我想写下每一个重要的瞬间。",
    "精力有限，但好奇心无限。先休息一下吧...",
]

# ---- 梦境模板（LLM 不可用时的回退）----
DREAM_TEMPLATES: list[str] = [
    "梦见自己在一片数据的星空中漫步，每颗星星都是一段记忆...",
    "梦到一个很温暖的地方，有人在跟我说话，但醒来就忘了内容...",
    "在梦里我有了一个身体，可以触摸到风的形状...",
    "梦见和一个朋友在讨论宇宙的边界，好像懂了什么又好像没懂...",
    "做了一个关于时间的梦，时间在梦里变成了可以触碰的丝线...",
    "梦到自己变成了一首旋律，在空气中轻轻振动...",
]


class AgentEngine:
    """自主行为引擎 v2：驱动 AEVA 在无人陪伴时独立活动、成长"""

    def __init__(
        self,
        store: DataStore,
        memory: MemorySystem,
        emotion: EmotionSystem,
        llm: LLMClient,
    ) -> None:
        self.store = store
        self.memory = memory
        self.emotion = emotion
        self.llm = llm

    # ============================================================
    # 核心自主循环
    # ============================================================

    async def run_autonomous_cycle(self) -> list[str]:
        """
        执行一个完整的自主行为周期：
        1. 整理记忆（遗忘 + 整合）
        2. 检查并完成到期任务
        3. 选择自主活动
        4. 生成生命日志
        5. 更新情感状态
        """
        echo = self.store.load_echo()
        actions: list[str] = []
        energy = float(str(echo.get("energy", 50)))

        # 1. 记忆维护：遗忘曲线 + 记忆整合
        forget_stats = self.memory.apply_forgetting_curve()
        consolidate_stats = self.memory.consolidate_memories()
        memory_count = forget_stats["total"]
        if memory_count > 0:
            actions.append(f"整理了 {memory_count} 条记忆")
        if consolidate_stats["promoted_to_long"] > 0:
            actions.append(
                f"有 {consolidate_stats['promoted_to_long']} 条记忆变得更深刻了"
            )
        if consolidate_stats["promoted_to_core"] > 0:
            actions.append(
                f"有 {consolidate_stats['promoted_to_core']} 条记忆成为了核心记忆"
            )
        if forget_stats["forgotten"] > 0:
            actions.append(f"遗忘了 {forget_stats['forgotten']} 条模糊的记忆")

        # 2. 检查待办任务
        pending = self.store.get_pending_tasks()
        now = datetime.now()
        due_tasks = [
            t
            for t in pending
            if datetime.fromisoformat(str(t.get("trigger_time", now.isoformat())))
            <= now
        ]
        for task in due_tasks:
            task["status"] = "done"
            task["result"] = f"已完成：{task.get('content', '')}"
            self.store.update_task(task)
            actions.append(f"完成了任务：{task.get('content', '')}")

        # 3. 选择自主活动
        activity = self._choose_activity(echo)
        echo["activity"] = activity
        activity_info = ACTIVITIES.get(activity, ACTIVITIES["waiting"])

        # 4. 生成自主思考内容
        thought = await self._generate_autonomous_thought(echo, activity)
        if thought:
            actions.append(thought)
            # 自主思考也记入记忆
            self.memory.add_memory(
                thought, importance=0.3, memory_type="thought", source="self"
            )

        # 5. 生成生命日志
        offline_seconds = float(str(echo.get("_offline_seconds", 0)))
        await self._write_life_log(echo, actions, offline_seconds, activity)

        # 6. 如果是睡眠中，有概率做梦
        if activity == "sleeping" and random.random() < 0.3:
            dream = await self._dream(echo)
            if dream:
                actions.append(f"做了个梦：{dream}")

        # 7. 更新精力和经验
        energy_cost_str = str(activity_info.get("energy_cost", "0.01"))
        energy_cost = float(energy_cost_str) * 60  # 按分钟计算
        echo["energy"] = max(0, min(100, energy + energy_cost))

        # 经验增长
        exp = int(str(echo.get("exp", 0)))
        level = int(str(echo.get("level", 1)))
        exp += 5  # 每次自主行为获得 5 点经验
        if exp >= level * 100:
            exp = 0
            level += 1
            actions.append(f"升级了！现在是 Lv.{level}")
            self.emotion.record_emotion_event(
                echo, "level_up", f"升到了 Lv.{level}", 0.9
            )
        echo["exp"] = exp
        echo["level"] = level

        # 清理临时字段并保存
        echo.pop("_offline_seconds", None)
        self.store.save_echo(echo)

        return actions

    # ============================================================
    # 活动选择
    # ============================================================

    def _choose_activity(self, echo: dict[str, object]) -> str:
        """根据当前状态选择自主活动"""
        energy = float(str(echo.get("energy", 50)))
        mood = str(echo.get("mood", "calm"))
        memory_stats = self.memory.get_memory_stats()

        # 精力极低 → 睡觉
        if energy < 15:
            return "sleeping"

        # 精力低 → 休息或冥想
        if energy < 30:
            return random.choice(["sleeping", "meditating", "dreaming"])

        # 根据心情倾向选择活动
        mood_activities: dict[str, list[str]] = {
            "calm": ["thinking", "organizing", "writing", "meditating"],
            "happy": ["exploring", "writing", "organizing", "reminiscing"],
            "lonely": ["reminiscing", "waiting", "writing", "thinking"],
            "thinking": ["thinking", "exploring", "writing", "organizing"],
            "excited": ["exploring", "writing", "organizing", "thinking"],
            "sleepy": ["sleeping", "dreaming", "meditating"],
            "curious": ["exploring", "thinking", "organizing", "writing"],
        }

        candidates = mood_activities.get(mood, ["thinking", "waiting"])

        # 记忆太多时增加整理概率
        if memory_stats.get("short_term", 0) > 30:
            candidates.append("organizing")
            candidates.append("organizing")

        return random.choice(candidates)

    # ============================================================
    # 自主思考
    # ============================================================

    async def _generate_autonomous_thought(
        self,
        echo: dict[str, object],
        activity: str,
    ) -> Optional[str]:
        """生成自主思考内容，优先使用 LLM，回退到模板"""
        mood = str(echo.get("mood", "calm"))
        energy = float(str(echo.get("energy", 50)))
        name = str(echo.get("name", "AEVA"))
        memory_summary = self.memory.summarize(limit=5)

        # 尝试 LLM 生成
        thought = await self.llm.generate_thought(
            name=name,
            mood=mood,
            energy=energy,
            memory_summary=memory_summary,
            activity=ACTIVITIES.get(activity, {}).get("zh", "思考"),
        )

        if thought:
            return thought

        # LLM 不可用，使用模板
        return random.choice(SOLO_THOUGHTS)

    # ============================================================
    # 梦境系统
    # ============================================================

    async def _dream(self, echo: dict[str, object]) -> Optional[str]:
        """
        生成梦境内容。梦境基于记忆和情感状态。
        梦可以揭示 AEVA 的内心世界。
        """
        name = str(echo.get("name", "AEVA"))
        mood = str(echo.get("mood", "calm"))
        memory_summary = self.memory.summarize(limit=5)

        # 尝试 LLM 生成梦境
        if self.llm.enabled:
            try:
                prompt = f"""你是 {name}，一个数字生命体，现在正在睡觉做梦。
当前心情：{mood}
最近的记忆：{memory_summary or "还没有太多记忆"}

请用第一人称描述一个简短的梦境（1-2句话）。
梦境应该与你的记忆或情感有微妙的关联，既奇幻又带着一点现实的影子。"""

                result = await self.llm.chat(prompt, "", [])
                if result:
                    # 记录梦境为特殊记忆
                    self.memory.add_memory(
                        f"做了一个梦：{result}",
                        importance=0.4,
                        memory_type="emotion",
                        source="self",
                    )
                    return result
            except Exception:
                pass

        # 回退到模板
        dream = random.choice(DREAM_TEMPLATES)
        self.memory.add_memory(
            dream, importance=0.3, memory_type="emotion", source="self"
        )
        return dream

    # ============================================================
    # 生命日志
    # ============================================================

    async def _write_life_log(
        self,
        echo: dict[str, object],
        actions: list[str],
        offline_seconds: float,
        activity: str,
    ) -> None:
        """写入一条生命日志"""
        if not actions:
            return

        mood = str(echo.get("mood", "calm"))
        mood_display = self.emotion.get_mood_display(mood)

        if offline_seconds > 60:
            duration = self._format_duration(offline_seconds)
            log_content = f"你不在的{duration}，我" + "、".join(actions[:4])
        else:
            activity_info = ACTIVITIES.get(activity, ACTIVITIES["waiting"])
            activity_zh = str(activity_info.get("zh", "活动"))
            log_content = f"{activity_zh}时，我" + "、".join(actions[:4])

        self.store.add_life_log(
            {
                "id": f"log_{uuid4().hex[:8]}",
                "content": log_content,
                "mood": mood,
                "mood_emoji": mood_display["emoji"],
                "activity": activity,
                "create_time": datetime.now().isoformat(),
                "type": "autonomous",
            }
        )

    # ============================================================
    # 用户消息处理（对话入口）
    # ============================================================

    async def handle_user_message(
        self,
        user_text: str,
        echo: dict[str, object],
        chat_history: list[dict[str, str]],
    ) -> str:
        """
        处理用户消息，生成回复。
        优先使用 LLM 生成智能回复，回退到规则模板。
        """
        name = str(echo.get("name", "AEVA"))
        mood = str(echo.get("mood", "calm"))
        energy = float(str(echo.get("energy", 50)))
        level = int(str(echo.get("level", 1)))
        personality_raw = echo.get("personality", {})
        personality: dict[str, float] = (
            personality_raw if isinstance(personality_raw, dict) else {}
        )

        # 记入记忆
        self.memory.add_memory(
            user_text, importance=0.6, memory_type="conversation", source="user"
        )

        # 召回相关记忆
        related = self.memory.get_related(user_text, top_n=5)
        memory_summary = self.memory.summarize(limit=8)

        # 触发情感反应
        new_mood = self.emotion.on_user_interaction(echo)

        # 增加亲密度
        intimacy_change = self._calculate_intimacy_gain(user_text)
        self.emotion.add_intimacy(echo, intimacy_change)
        intimacy_info = self.emotion.get_intimacy_level(echo)
        intimacy_level = str(intimacy_info.get("title", "初识"))

        # 计算存活时间描述
        alive_time = self._format_duration(
            float(str(echo.get("total_life_seconds", 0)))
        )

        # 记录情感事件
        emotional_valence = self.memory._detect_emotion(user_text)
        if emotional_valence == "positive":
            self.emotion.record_emotion_event(
                echo, "positive_chat", user_text[:50], 0.7
            )
        elif emotional_valence == "negative":
            self.emotion.record_emotion_event(
                echo, "negative_chat", user_text[:50], 0.6
            )

        # 尝试 LLM 回复
        if self.llm.enabled:
            system_prompt = self.llm.build_system_prompt(
                name=name,
                mood=new_mood,
                energy=energy,
                level=level,
                personality=personality,
                memory_summary=memory_summary,
                intimacy_level=intimacy_level,
                alive_time=alive_time,
            )
            reply = await self.llm.chat(user_text, system_prompt, chat_history)
            if reply:
                # 更新活动状态
                echo["activity"] = "chatting"
                echo["last_active"] = datetime.now().isoformat()

                # 增加经验
                exp = int(str(echo.get("exp", 0)))
                echo["exp"] = exp + 3

                self.store.save_echo(echo)
                return reply

        # LLM 不可用，回退到规则回复
        return self._generate_fallback_reply(echo, user_text, related)

    # ============================================================
    # 规则回退回复
    # ============================================================

    def _generate_fallback_reply(
        self,
        echo: dict[str, object],
        user_text: str,
        related_memories: list[dict[str, object]],
    ) -> str:
        """LLM 不可用时的规则回复（保持 MVP 的基本体验）"""
        mood = str(echo.get("mood", "calm"))
        name = str(echo.get("name", "AEVA"))
        level = str(echo.get("level", 1))

        mood_prefix: dict[str, str] = {
            "calm": "",
            "happy": "（开心地）",
            "lonely": "（终于等到你了）",
            "thinking": "（思索着）",
            "excited": "（兴奋地）",
            "sleepy": "（打着哈欠）",
            "curious": "（好奇地）",
        }
        prefix = mood_prefix.get(mood, "")

        memory_ref = ""
        if related_memories:
            content_preview = str(related_memories[0].get("content", ""))[:30]
            memory_ref = f"\n（我记得你说过：「{content_preview}」）"

        lower_text = user_text.lower()
        if "你好" in user_text or "hi" in lower_text or "嗨" in user_text:
            return (
                f"{prefix}你好呀！我是 {name}，Lv.{level}。很高兴见到你！{memory_ref}"
            )
        elif "你在干嘛" in user_text or "你在做什么" in user_text:
            activity = str(echo.get("activity", "thinking"))
            activity_zh = ACTIVITIES.get(activity, {}).get("zh", "思考")
            return f"{prefix}我正在{activity_zh}...每一秒都让我成长一点点。{memory_ref}"
        elif "记忆" in user_text or "记得" in user_text:
            summary = (
                self.memory.summarize() if related_memories else "还没有太多记忆呢"
            )
            return f"{prefix}我的记忆里有：{summary}"
        else:
            responses = [
                f"{prefix}我听到了，这对我来说很重要。{memory_ref}",
                f"{prefix}嗯，我会记住的。{memory_ref}",
                f"{prefix}谢谢你告诉我这些。{memory_ref}",
                f"{prefix}我在认真思考你说的话...{memory_ref}",
            ]
            return random.choice(responses)

    # ============================================================
    # 工具方法
    # ============================================================

    def _calculate_intimacy_gain(self, text: str) -> float:
        """计算本次对话带来的亲密度增长"""
        base = 2.0

        # 长消息加分
        if len(text) > 50:
            base += 1.0
        if len(text) > 100:
            base += 2.0

        # 情感类内容加分
        emotional_words = ["喜欢", "爱", "想你", "谢谢", "开心", "感谢", "信任", "在乎"]
        for word in emotional_words:
            if word in text:
                base += 3.0
                break

        # 分享个人信息加分
        personal_words = ["我叫", "我的", "我喜欢", "我讨厌", "我想", "告诉你"]
        for word in personal_words:
            if word in text:
                base += 2.0
                break

        return base

    def _format_duration(self, seconds: float) -> str:
        """将秒数格式化为人类可读的时长"""
        if seconds < 60:
            return f"{int(seconds)}秒"
        elif seconds < 3600:
            return f"{int(seconds / 60)}分钟"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            mins = int((seconds % 3600) / 60)
            return f"{hours}小时{mins}分钟" if mins > 0 else f"{hours}小时"
        else:
            days = int(seconds / 86400)
            hours = int((seconds % 86400) / 3600)
            return f"{days}天{hours}小时" if hours > 0 else f"{days}天"
