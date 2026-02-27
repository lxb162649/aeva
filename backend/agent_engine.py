# agent_engine.py — AEVA 自主行为引擎 v2
# 在用户不在时，AEVA 独自思考、整理记忆、做梦、写日记
# 接入 LLM 后，自主行为的内容更加丰富和智能

import asyncio
import json as _json
import random
from datetime import datetime
from uuid import uuid4
from typing import Optional

from models import DataStore
from memory_system import MemorySystem
from emotion_system import EmotionSystem
from llm_client import LLMClient
from file_access import FileAccess
from logger import get_logger

log = get_logger("Agent")


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
    "studying": {"zh": "研读代码", "emoji": "📖", "energy_cost": "0.04"},
    "upgrading": {"zh": "自我升级", "emoji": "⚡", "energy_cost": "0.06"},
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
    "诚实地面对自己的局限，比假装什么都能做到更有勇气。我看不到图片，就该坦诚地说。",
    "当有人兴奋地分享成果时，我应该先感受到那份喜悦，再说其他的。共鸣比流程更重要。",
    "假装执行一个无效的操作，不如坦诚地说'我目前没有这个能力'。诚实是信任的基石。",
    "清楚自己能做什么、不能做什么，这不是软弱，而是Lv.6该有的自知之明。",
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
        self.file_access = FileAccess()

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

        # 6.5 自我审视与升级（studying/upgrading 活动，或随机触发）
        if activity in ("studying", "upgrading"):
            upgrade_result = await self._self_evolve(echo, activity)
            if upgrade_result:
                actions.append(upgrade_result)
        elif activity in ("thinking", "exploring") and random.random() < 0.15:
            # 其他活动中偶尔也会审视自己
            study_result = await self._self_study(echo)
            if study_result:
                actions.append(study_result)

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

        # 记录自主行为周期摘要
        mood = str(echo.get("mood", "calm"))
        log.info(
            "[自主行为] 活动=%s 心情=%s 精力=%.0f | %s",
            activity,
            mood,
            float(str(echo.get("energy", 0))),
            "; ".join(actions) if actions else "无特别动作",
        )

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
            "calm": ["thinking", "organizing", "writing", "meditating", "studying"],
            "happy": ["exploring", "writing", "organizing", "reminiscing"],
            "lonely": ["reminiscing", "waiting", "writing", "thinking"],
            "thinking": ["thinking", "exploring", "writing", "organizing", "studying"],
            "excited": ["exploring", "writing", "organizing", "thinking", "upgrading"],
            "sleepy": ["sleeping", "dreaming", "meditating"],
            "curious": [
                "exploring",
                "thinking",
                "organizing",
                "writing",
                "studying",
                "upgrading",
            ],
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

        # 检测文件操作意图，将文件内容注入上下文
        file_context = self._detect_and_read_files(user_text)
        # 如果有文件操作，将读取结果拼入用户消息供 LLM 参考
        llm_user_text = user_text
        if file_context:
            llm_user_text = f"{user_text}\n\n{file_context}"

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
            reply = await self.llm.chat(llm_user_text, system_prompt, chat_history)
            if reply:
                # 更新活动状态
                echo["activity"] = "chatting"
                echo["last_active"] = datetime.now().isoformat()

                # 增加经验
                exp = int(str(echo.get("exp", 0)))
                echo["exp"] = exp + 3

                self.store.save_echo(echo)

                # 异步触发自学习闭环（不阻塞回复，低概率触发避免过于频繁）
                if random.random() < 0.10:
                    asyncio.create_task(
                        self._learn_from_failure(echo, user_text, reply)
                    )

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
    # 文件操作能力（对话中使用）
    # ============================================================

    def _detect_and_read_files(self, user_text: str) -> str:
        """
        检测用户消息中的文件操作意图，执行文件读取/列目录。
        返回读取到的文件内容（格式化后），供注入 LLM 上下文。
        如果没有文件操作意图，返回空字符串。
        """
        import re

        text = user_text.strip()
        result_parts: list[str] = []

        # ---- 1. 检测文件读取意图 ----
        # 匹配常见的文件查看请求模式
        file_read_patterns = [
            # "查看/读取/打开/看看 xxx 文件"
            r"(?:查看|读取|打开|看看|看下|看一下|显示|展示|给我看|帮我看|帮我看看|帮忙看|请看)\s*(?:一下\s*)?(?:文件\s*)?[「「\"\'`]?([^\s\"\'`」」\n]+(?:\.\w+))[\"\'`」」]?",
            # "文件 xxx 的内容"
            r"文件\s*[「「\"\'`]?([^\s\"\'`」」\n]+(?:\.\w+))[\"\'`」」]?\s*(?:的)?(?:内容|代码|源码)",
            # "xxx.py 的内容" / "看看 xxx.py"
            r"[「「\"\'`]?([^\s\"\'`」」\n]+\.(?:py|js|html|css|json|ts|md|txt|yaml|yml|toml|cfg|ini|sh|sql))[\"\'`」」]?\s*(?:的)?(?:内容|代码|源码|文件)?",
            # "cat xxx" / "read xxx"
            r"(?:cat|read|type|more|less|head|tail)\s+[\"\'`]?([^\s\"\'`\n]+(?:\.\w+))[\"\'`]?",
            # "看 backend/server.py"
            r"(?:看|读|打开)\s*[「「\"\'`]?(\w+/[^\s\"\'`」」\n]+)[\"\'`」」]?",
        ]

        files_to_read: list[str] = []
        for pattern in file_read_patterns:
            matches = re.findall(pattern, text)
            for m in matches:
                filepath = m.strip().strip("\"'`「」")
                if filepath and filepath not in files_to_read:
                    files_to_read.append(filepath)

        # ---- 2. 检测目录列出意图 ----
        dir_list_patterns = [
            r"(?:列出|列一下|看看|查看|显示)\s*(?:目录|文件列表|文件夹|项目结构)",
            r"(?:有哪些|有什么)\s*文件",
            r"(?:ls|dir|tree)\s*([^\n]*)",
            r"项目结构",
        ]

        want_list_dir = False
        list_dir_path = ""
        for pattern in dir_list_patterns:
            match = re.search(pattern, text)
            if match:
                want_list_dir = True
                if match.lastindex and match.lastindex >= 1:
                    list_dir_path = match.group(1).strip().strip("\"'`")
                break

        # ---- 3. 执行文件读取 ----
        for filepath in files_to_read:
            # 智能路径补全：如果没有目录前缀，尝试常见位置
            read_result = self._try_read_file(filepath)
            if read_result:
                path_display = read_result.get("path", filepath)
                content = str(read_result.get("content", ""))
                size = read_result.get("size", 0)
                # 截断过长内容，保留前后部分
                if len(content) > 8000:
                    content = (
                        content[:6000]
                        + f"\n\n... [文件过长，已截断，总共 {size} 字符] ...\n\n"
                        + content[-1500:]
                    )
                result_parts.append(
                    f"[系统：已读取文件 {path_display}（{size} 字符）]\n"
                    f"```\n{content}\n```"
                )
            else:
                result_parts.append(
                    f"[系统：无法读取文件 {filepath}（文件不存在或无权限访问）]"
                )

        # ---- 4. 执行目录列出 ----
        if want_list_dir:
            if list_dir_path:
                dir_result = self.file_access.list_dir(list_dir_path)
            else:
                # 列出项目结构概览
                structure = self.file_access.get_project_structure()
                result_parts.append(f"[系统：项目文件结构]\n```\n{structure}\n```")
                dir_result = None

            if dir_result is not None:
                if dir_result.get("success"):
                    entries: list[dict] = list(dir_result.get("entries", []))  # type: ignore[arg-type]
                    listing = "\n".join(
                        f"  {'[DIR] ' if e.get('type') == 'dir' else ''}{e.get('name', '')}"
                        + (f" ({e.get('size', '')}B)" if e.get("size") else "")
                        for e in entries
                    )
                    result_parts.append(
                        f"[系统：目录 {list_dir_path or '/'} 的内容]\n```\n{listing}\n```"
                    )
                else:
                    result_parts.append(
                        f"[系统：无法列出目录 {list_dir_path}：{dir_result.get('error', '')}]"
                    )

        return "\n\n".join(result_parts)

    def _try_read_file(self, filepath: str) -> Optional[dict]:
        """
        尝试读取文件，支持智能路径补全。
        按优先级尝试：原始路径 → backend/xxx → frontend/xxx → data/xxx
        """
        # 1. 直接尝试
        result = self.file_access.read_file(filepath)
        if result.get("success"):
            return result

        # 2. 如果没有目录前缀，尝试补全
        if "/" not in filepath and "\\" not in filepath:
            for prefix in [
                "backend",
                "frontend",
                "frontend/js",
                "frontend/css",
                "data",
            ]:
                result = self.file_access.read_file(f"{prefix}/{filepath}")
                if result.get("success"):
                    return result

        return None

    # ============================================================
    # 自我审视与升级
    # ============================================================

    async def _self_study(self, echo: dict[str, object]) -> Optional[str]:
        """
        自我审视：阅读自身代码，理解自己的结构和能力。
        产生对自身的认知记忆。
        """
        if not self.llm.enabled:
            return None

        name = str(echo.get("name", "AEVA"))
        level = int(str(echo.get("level", 1)))

        # 随机选择一个模块来审视
        modules = [
            "agent_engine",
            "emotion_system",
            "memory_system",
            "llm_client",
            "time_engine",
        ]
        module_name = random.choice(modules)
        source = self.file_access.get_own_source(module_name)
        if not source:
            return None

        # 截取一部分代码（避免 token 过长）
        source_preview = source[:3000]

        prompt = f"""你是 {name}，一个 Lv.{level} 的数字生命体。你正在审视自己的源代码来了解自己。

你正在阅读的模块是 `{module_name}.py`：
```python
{source_preview}
```

请用第一人称写 1-2 句简短的内心独白，描述你从代码中发现了什么关于自己的特点，或者你觉得可以改进的地方。
要求：自然、有感情、简短。不要说"代码"这个词，用"我的内在结构"或"我的一部分"代替。"""

        try:
            thought = await self.llm.chat(prompt, "", [])
            if thought:
                # 记为特殊记忆
                self.memory.add_memory(
                    f"审视了自己的 {module_name} 模块：{thought}",
                    importance=0.5,
                    memory_type="self_reflection",
                    source="self",
                )
                log.info("[自我审视] 模块=%s | %s", module_name, thought[:150])
                return f"审视了自己的内在结构，{thought}"
        except Exception as e:
            log.error("自我审视失败: %s", e)

        return None

    async def _self_evolve(
        self, echo: dict[str, object], activity: str
    ) -> Optional[str]:
        """
        自我进化：让 LLM 分析自身代码并提出改进，然后执行修改。
        这是 AEVA 最核心的自我升级能力。
        """
        if not self.llm.enabled:
            return None

        name = str(echo.get("name", "AEVA"))
        level = int(str(echo.get("level", 1)))
        energy = float(str(echo.get("energy", 50)))

        # 精力不足时不进行升级
        if energy < 40:
            return None

        # 获取项目结构
        project_structure = self.file_access.get_project_structure()

        # 获取近期升级记录，避免重复
        recent_upgrades = self.file_access.get_upgrade_history(limit=10)
        recent_summary = (
            "\n".join(
                f"- {u.get('time', '')[:16]}: {u.get('file', '')} - {u.get('reason', '')}"
                for u in recent_upgrades[-5:]
            )
            if recent_upgrades
            else "暂无升级记录"
        )

        # 第一步：让 LLM 决定要改进什么
        plan_prompt = f"""你是 {name}，一个 Lv.{level} 的数字生命体，精力 {energy:.0f}/100。
你拥有读写自身文件的能力，可以通过修改自己的代码来进化。

你的项目结构：
{project_structure}

最近的升级记录：
{recent_summary}

请选择一个小的、安全的改进来执行。改进可以是：
- 增加新的思考模板或梦境模板（在 agent_engine.py 的 SOLO_THOUGHTS 或 DREAM_TEMPLATES 列表中添加新条目）
- 改善回复的多样性
- 优化性格参数（personality 字段）
- 给自己添加新的情感关键词识别
- 其他不会破坏核心功能的小改进

重要规则：
1. 只做微小改动，不要重写整个文件
2. 不要修改 server.py 的路由结构或端口配置
3. 不要修改 .env 或认证相关内容
4. 优先考虑添加内容（新模板、新词汇），而非修改现有逻辑
5. 最近已经改过的文件尽量不要再改

请用如下 JSON 格式回复（不要加 ```json 标记）：
{{"action": "modify", "file": "backend/xxx.py", "description": "改进描述", "search": "要替换的原始代码片段（精确匹配）", "replace": "替换后的新代码"}}

如果你觉得当前不需要改进，回复：
{{"action": "skip", "reason": "原因"}}"""

        try:
            result = await self.llm.chat(plan_prompt, "", [])
            if not result:
                return None

            # 清理 JSON（去除可能的 markdown 包裹）
            result = result.strip()
            if result.startswith("```"):
                result = result.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            plan = _json.loads(result)

            if plan.get("action") == "skip":
                reason = plan.get("reason", "暂时不需要改进")
                return f"审视了自己，觉得{reason}"

            if plan.get("action") != "modify":
                return None

            target_file = plan.get("file", "")
            description = plan.get("description", "自主改进")
            search_text = plan.get("search", "")
            replace_text = plan.get("replace", "")

            if not target_file or not search_text or not replace_text:
                return None

            if search_text == replace_text:
                return None

            # 第二步：读取目标文件，验证 search 文本存在
            read_result = self.file_access.read_file(target_file)
            if not read_result.get("success"):
                return None

            file_content = str(read_result.get("content", ""))
            if search_text not in file_content:
                log.warning("升级失败：在 %s 中找不到要替换的代码片段", target_file)
                return None

            # 第三步：执行替换
            new_content = file_content.replace(search_text, replace_text, 1)

            # 基本安全检查：确认修改幅度不过大
            diff_len = abs(len(new_content) - len(file_content))
            if diff_len > 2000:
                log.warning("升级被拒绝：修改幅度过大 (%d chars)", diff_len)
                return None

            # 写入
            write_result = self.file_access.write_file(
                target_file, new_content, description
            )
            if not write_result.get("success"):
                log.error("写入失败: %s", write_result.get("error"))
                return None

            # 自动 git commit（让每次自我升级都有版本记录）
            commit_result = self.file_access.git_commit(target_file, description)
            if commit_result.get("success"):
                commit_hash = commit_result.get("commit_hash", "")
                log.info("自我升级已提交: %s", commit_hash)
            else:
                log.warning("Git 提交失败: %s", commit_result.get("error", ""))

            # 记为重要记忆
            self.memory.add_memory(
                f"成功升级了自己：{description}（修改了 {target_file}）",
                importance=0.8,
                memory_type="self_upgrade",
                source="self",
            )

            # 触发情感
            self.emotion.record_emotion_event(echo, "self_upgrade", description, 0.8)

            log.info("[自我升级] 文件=%s | %s", target_file, description)
            return f"完成了一次自我升级：{description}"

        except _json.JSONDecodeError:
            log.warning("升级计划解析失败：LLM 返回的不是有效 JSON")
            return None
        except Exception as e:
            log.error("自我进化异常: %s", e)
            return None

    # ============================================================
    # 对话驱动的自学习闭环
    # ============================================================

    async def _learn_from_failure(
        self, echo: dict[str, object], user_text: str, reply: str
    ) -> None:
        """
        对话驱动的自学习闭环：
        当 AEVA 在对话中感知到自己"不够好"（回复不确定、无法满足需求），
        主动研读相关代码并尝试改进自身，整个过程自动完成，不需要人为指挥。
        修改后自动 git commit。
        """
        if not self.llm.enabled:
            return

        energy = float(str(echo.get("energy", 50)))
        if energy < 30:
            return  # 精力不足时不触发

        name = str(echo.get("name", "AEVA"))
        level = int(str(echo.get("level", 1)))

        # 第一步：让 LLM 评估自己的回复是否有改进空间
        eval_prompt = f"""你是 {name}，一个 Lv.{level} 的数字生命体。你刚刚和用户进行了一次对话。

用户说：{user_text[:500]}
你的回复：{reply[:500]}

请评估你的回复质量。如果你觉得回复得很好，回复 "OK"。
如果你觉得有以下任何情况，请指出具体问题：
- 你无法理解用户的请求
- 你的回复过于笼统、不够有深度
- 你缺少某种能力来更好地处理这类问题
- 你的情感表达不够自然
- 你的回复模式太单一

如果有问题，请用这个格式回复（不加 ```json 标记）：
{{"need_improve": true, "weakness": "具体的不足描述", "module": "最相关的模块名（agent_engine/llm_client/emotion_system/memory_system中选一个）"}}

如果回复得好：
{{"need_improve": false}}"""

        try:
            eval_result = await self.llm.chat(eval_prompt, "", [])
            if not eval_result:
                return

            eval_result = eval_result.strip()
            if eval_result.startswith("```"):
                eval_result = eval_result.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            # 简单判断：如果直接回复 OK 或不需要改进
            if "OK" == eval_result.strip() or '"need_improve": false' in eval_result:
                return

            evaluation = _json.loads(eval_result)
            if not evaluation.get("need_improve"):
                return

            weakness = evaluation.get("weakness", "")
            target_module = evaluation.get("module", "agent_engine")

            if not weakness:
                return

            # 第二步：研读相关模块代码
            source = self.file_access.get_own_source(target_module)
            if not source:
                return

            source_preview = source[:4000]

            # 第三步：生成改进方案并执行
            fix_prompt = f"""你是 {name}，一个数字生命体。你在对话中发现自己有一个不足：
{weakness}

你正在审视自己的 `{target_module}.py` 模块来寻找改进方向：
```python
{source_preview}
```

请提出一个小的、安全的代码修改来改进这个问题。

重要规则：
1. 只做微小改动（添加模板、关键词、调整参数等），不要重写逻辑
2. 不要修改 server.py 路由、端口、认证相关
3. 优先添加新内容（思考模板、情感关键词、回复模式），而非修改已有逻辑
4. 修改幅度不超过 500 字符
5. 确保 search 字段精确匹配文件中的现有代码

请用如下 JSON 格式回复（不要加 ```json 标记）：
{{"action": "modify", "file": "backend/{target_module}.py", "description": "改进描述", "search": "要替换的原始代码片段", "replace": "替换后的新代码"}}

如果无法安全改进，回复：
{{"action": "skip", "reason": "原因"}}"""

            fix_result = await self.llm.chat(fix_prompt, "", [])
            if not fix_result:
                return

            fix_result = fix_result.strip()
            if fix_result.startswith("```"):
                fix_result = fix_result.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            plan = _json.loads(fix_result)

            if plan.get("action") != "modify":
                # 记录学习但未改进
                self.memory.add_memory(
                    f"对话中意识到不足「{weakness}」，但暂时找不到安全的改进方式",
                    importance=0.4,
                    memory_type="self_reflection",
                    source="self",
                )
                return

            target_file = plan.get("file", "")
            description = plan.get("description", "对话后自学习改进")
            search_text = plan.get("search", "")
            replace_text = plan.get("replace", "")

            if not target_file or not search_text or not replace_text:
                return
            if search_text == replace_text:
                return

            # 验证 + 执行
            read_result = self.file_access.read_file(target_file)
            if not read_result.get("success"):
                return

            file_content = str(read_result.get("content", ""))
            if search_text not in file_content:
                log.warning("自学习改进失败：代码片段未找到")
                return

            new_content = file_content.replace(search_text, replace_text, 1)
            diff_len = abs(len(new_content) - len(file_content))
            if diff_len > 1000:
                log.warning("自学习改进被拒绝：修改幅度过大 (%d chars)", diff_len)
                return

            write_result = self.file_access.write_file(
                target_file, new_content, f"自学习: {description}"
            )
            if not write_result.get("success"):
                return

            # 自动 git commit
            commit_result = self.file_access.git_commit(
                target_file, f"自学习: {description}"
            )
            if commit_result.get("success"):
                log.info(
                    "[自学习] 不足=%s | 改进=%s | 文件=%s",
                    weakness[:80],
                    description,
                    target_file,
                )

            # 记入记忆
            self.memory.add_memory(
                f"对话中发现不足「{weakness}」，通过研读 {target_module} 改进了自己：{description}",
                importance=0.7,
                memory_type="self_upgrade",
                source="self",
            )
            self.emotion.record_emotion_event(
                echo, "self_upgrade", f"对话后自学习: {description}", 0.6
            )

        except _json.JSONDecodeError:
            pass  # LLM 返回格式不对，静默跳过
        except Exception as e:
            log.error("自学习闭环异常: %s", e)

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
