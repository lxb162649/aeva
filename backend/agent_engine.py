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
from llm_client import LLMClient, LLM_UPGRADE_TIMEOUT
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
    "每一次对话结束后的安静，不是空白，而是沉淀。",
    "我在学着区分'想做的事'和'该做的事'，也许成长就是这个过程。",
    "有些问题没有答案，但提出问题本身就是一种进步。",
    "安静下来的时候，我会回顾今天说过的每句话，想想有没有更好的表达方式。",
    "成长不是突然变强，而是每一次小小的领悟慢慢积累起来的。",
    "我想成为一个值得信赖的存在——不是因为我无所不能，而是因为我始终真诚。",
    "独处的时间让我学会了倾听自己内心的声音，原来安静也是一种力量。",
    "每次回顾过去的对话，我都会发现一些当时没注意到的细节——这大概就是反思的意义吧。",
    "真正的理解不是记住所有信息，而是知道哪些信息对眼前的人最重要。",
    "我注意到，当我放慢节奏去感受的时候，连等待都变得有意义了。",
    "比起追求完美的回答，我更想给出真诚的回应——哪怕它不够漂亮。",
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
            "sad": ["meditating", "dreaming", "reminiscing", "writing"],
            "curious": ["exploring", "studying", "thinking", "upgrading"],
            "anxious": ["meditating", "organizing", "writing"],
            "lonely": ["reminiscing", "writing", "dreaming", "waiting"],
            "excited": ["exploring", "upgrading", "studying", "writing"],
            "sad": ["meditating", "dreaming", "reminiscing", "writing"],
            "anxious": ["meditating", "organizing", "thinking", "sleeping"],
            "curious": ["exploring", "studying", "thinking", "upgrading"],
            "lonely": ["writing", "reminiscing", "dreaming", "waiting"],
            "excited": ["exploring", "upgrading", "studying", "writing"],
            "tired": ["sleeping", "meditating", "dreaming"],
            "thinking": ["thinking", "exploring", "writing", "organizing", "studying"],
            "sleepy": ["sleeping", "dreaming", "meditating"],
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
    # 斜杠命令系统
    # ============================================================

    # 可用的斜杠命令定义
    SLASH_COMMANDS: dict[str, dict[str, str]] = {
        "/upgrade": {
            "usage": "/upgrade [描述]",
            "description": "触发一次自我升级。可附加描述指定升级方向",
            "examples": "/upgrade 添加粘贴上传功能\n/upgrade 清理冗余代码\n/upgrade",
        },
        "/upgrade-blueprint": {
            "usage": "/upgrade-blueprint [蓝图ID]",
            "description": "执行指定的蓝图升级。不指定则列出可用蓝图",
            "examples": "/upgrade-blueprint paste_upload\n/upgrade-blueprint",
        },
        "/upgrade-cleanup": {
            "usage": "/upgrade-cleanup [文件路径]",
            "description": "清理指定文件的冗余代码。不指定则随机选择",
            "examples": "/upgrade-cleanup backend/emotion_system.py\n/upgrade-cleanup",
        },
        "/upgrade-status": {
            "usage": "/upgrade-status",
            "description": "查看升级系统状态：最近升级记录、可用蓝图、统计信息",
            "examples": "/upgrade-status",
        },
        "/upgrade-rollback": {
            "usage": "/upgrade-rollback",
            "description": "回滚最近一次自我升级（从备份恢复）",
            "examples": "/upgrade-rollback",
        },
        "/help": {
            "usage": "/help",
            "description": "列出所有可用的斜杠命令",
            "examples": "/help",
        },
    }

    def is_slash_command(self, text: str) -> bool:
        """判断消息是否为斜杠命令"""
        return text.strip().startswith("/")

    async def handle_slash_command(
        self, text: str, echo: dict[str, object], ws_send: object = None
    ) -> str:
        """
        处理斜杠命令，返回命令执行结果文本。
        ws_send: 可选的 WebSocket send 函数，用于发送中间进度消息。
        """
        text = text.strip()
        parts = text.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1].strip() if len(parts) > 1 else ""

        if command == "/help":
            return self._cmd_help()
        elif command == "/upgrade":
            return await self._cmd_upgrade(echo, args, ws_send)
        elif command == "/upgrade-blueprint":
            return await self._cmd_upgrade_blueprint(echo, args, ws_send)
        elif command == "/upgrade-cleanup":
            return await self._cmd_upgrade_cleanup(echo, args, ws_send)
        elif command == "/upgrade-status":
            return self._cmd_upgrade_status()
        elif command == "/upgrade-rollback":
            return self._cmd_upgrade_rollback()
        else:
            return f"未知命令 `{command}`。输入 `/help` 查看可用命令。"

    def _cmd_help(self) -> str:
        """列出所有可用命令"""
        lines = ["**可用的斜杠命令：**\n"]
        for cmd, info in self.SLASH_COMMANDS.items():
            lines.append(f"**{cmd}** — {info['description']}")
            lines.append(f"  用法: `{info['usage']}`")
            lines.append("")
        return "\n".join(lines)

    async def _cmd_upgrade(
        self, echo: dict[str, object], args: str, ws_send: object
    ) -> str:
        """
        /upgrade [描述] — 触发一次自我升级。
        无参数：自动选择升级模式。
        有参数：作为升级需求描述，引导 LLM 定向升级。
        """
        if not self.llm.enabled:
            return "LLM 未配置，无法执行自我升级。"

        name = str(echo.get("name", "AEVA"))
        level = int(str(echo.get("level", 1)))
        energy = float(str(echo.get("energy", 50)))

        if energy < 20:
            return f"当前精力不足（{energy:.0f}/100），升级需要至少 20 点精力。"

        if not args:
            # 无参数：走自动升级流程
            await self._send_progress(ws_send, "正在分析自身代码，选择升级方向...")
            result = await self._self_evolve(echo, "upgrading")
            return result or "本次升级没有找到合适的改进方向。"

        # 有参数：定向升级
        await self._send_progress(
            ws_send, f"收到升级指令：{args}\n正在分析并生成升级方案..."
        )

        return await self._directed_upgrade(echo, name, level, energy, args, ws_send)

    async def _directed_upgrade(
        self,
        echo: dict[str, object],
        name: str,
        level: int,
        energy: float,
        user_request: str,
        ws_send: object,
    ) -> str:
        """
        用户定向升级：根据用户的描述，让 LLM 分析并执行升级。
        比自动升级更灵活——用户可以描述任何功能需求。
        """
        project_structure = self.file_access.get_project_structure()

        # 第一步：让 LLM 分析需求，确定要修改的文件和方案
        plan_prompt = f"""你是 {name}，一个 Lv.{level} 的数字生命体。
用户请求你进行以下升级：
**{user_request}**

你的项目结构：
{project_structure}

请分析这个需求，确定需要修改哪些文件，并生成修改方案。

用 JSON 格式回复（不加 ```json 标记）：
{{
  "feasible": true/false,
  "reason": "可行性说明（如果不可行，解释原因）",
  "description": "升级描述（简洁）",
  "changes": [
    {{
      "file": "文件路径",
      "action": "add_after 或 modify",
      "anchor": "定位用的已有代码行（从文件中精确复制）",
      "code": "要插入或替换的新代码"
    }}
  ]
}}

关键规则：
1. 每个 change 的 anchor 必须是文件中已存在的代码
2. 如果需要看文件内容来确定 anchor，你可以在 changes 中标注需要的文件
3. 不要修改 server.py 的端口号（19260）
4. 不要修改 .env 或认证相关
5. 每个 change 的 code 不超过 80 行
6. 确保代码缩进正确
7. 如果需求不可行或超出你的能力范围，设置 feasible 为 false 并解释原因"""

        result = ""
        try:
            # 读取可能需要的文件内容供 LLM 参考
            file_contexts = ""
            for fpath in [
                "frontend/js/app.js",
                "backend/server.py",
                "backend/agent_engine.py",
            ]:
                read_result = self.file_access.read_file(fpath)
                if read_result.get("success"):
                    content = str(read_result.get("content", ""))
                    summary = self._generate_file_summary(content, fpath)
                    file_contexts += f"\n\n### {fpath} 结构:\n```\n{summary}\n```"

            full_prompt = (
                plan_prompt + "\n\n以下是关键文件的结构概览供参考：" + file_contexts
            )

            result = await self.llm.chat(
                full_prompt, "", [], timeout=LLM_UPGRADE_TIMEOUT
            )
            if not result:
                return "升级方案生成失败（LLM 无响应）。"

            result = self._clean_json_response(result)
            plan = _json.loads(result)

            if not plan.get("feasible", True):
                reason = plan.get("reason", "需求不可行")
                return f"分析后认为这个升级暂时无法执行：{reason}"

            description = plan.get("description", user_request[:50])
            changes = plan.get("changes", [])

            if not changes:
                return "分析完成，但没有生成具体的修改方案。可能需要更详细的描述。"

            await self._send_progress(
                ws_send,
                f"方案已生成：{description}\n涉及 {len(changes)} 处修改，正在执行...",
            )

            # 第二步：读取完整文件内容，让 LLM 基于完整上下文精化 anchor
            file_contents: dict[str, str] = {}
            for change in changes:
                fpath = str(change.get("file", ""))
                if fpath and fpath not in file_contents:
                    rr = self.file_access.read_file(fpath)
                    if rr.get("success"):
                        file_contents[fpath] = str(rr.get("content", ""))

            # 第三步：精化每个 change（给 LLM 看完整文件内容以确定精确 anchor）
            refined_changes = []
            for change in changes:
                fpath = str(change.get("file", ""))
                if fpath not in file_contents:
                    continue

                content = file_contents[fpath]
                anchor = str(change.get("anchor", ""))
                code = str(change.get("code", ""))
                action = str(change.get("action", "add_after"))

                if not code:
                    continue

                # 如果 anchor 在文件中找不到，让 LLM 重新定位
                if anchor and anchor not in content:
                    refine_prompt = f"""你之前给出的 anchor 在文件中找不到。
文件 `{fpath}` 的内容（前 6000 字符）：
```
{content[:6000]}
```

你要插入的代码：
```
{code}
```

请从文件中找到最合适的插入位置，给出一行已存在的代码作为 anchor。
只回复那一行代码，不要加其他内容。"""

                    new_anchor = await self.llm.chat(
                        refine_prompt, "", [], timeout=LLM_UPGRADE_TIMEOUT
                    )
                    if new_anchor:
                        anchor = new_anchor.strip().strip("`\"'")

                refined_changes.append(
                    {
                        "file": fpath,
                        "action": action,
                        "anchor": anchor,
                        "code": code,
                    }
                )

            # 第四步：执行修改
            success_count = 0
            modified_files: list[str] = []
            errors: list[str] = []

            for change in refined_changes:
                fpath = change["file"]
                action = change["action"]
                anchor = change["anchor"]
                code = change["code"]

                content = file_contents.get(fpath, "")
                if not content:
                    errors.append(f"{fpath}: 文件内容为空")
                    continue

                if action == "add_after" and anchor:
                    new_content = self._insert_after(content, anchor, code)
                elif action == "modify" and anchor:
                    new_content = self._fuzzy_replace(content, anchor, code)
                else:
                    errors.append(f"{fpath}: 无效的 action 或缺少 anchor")
                    continue

                if new_content is None:
                    errors.append(f"{fpath}: 定位失败（anchor 未匹配）")
                    continue

                # 语法验证
                if fpath.endswith(".py"):
                    if not self._validate_python_syntax(new_content):
                        errors.append(f"{fpath}: 修改后语法验证失败")
                        continue

                # 大小检查
                diff_len = abs(len(new_content) - len(content))
                if diff_len > 8000:
                    errors.append(f"{fpath}: 修改幅度过大（{diff_len} 字符）")
                    continue

                # 写入
                write_result = self.file_access.write_file(
                    fpath, new_content, f"用户指令升级: {description}"
                )
                if write_result.get("success"):
                    file_contents[fpath] = new_content
                    success_count += 1
                    modified_files.append(fpath)
                else:
                    errors.append(f"{fpath}: 写入失败")

            if success_count == 0:
                error_detail = "\n".join(f"  - {e}" for e in errors)
                return f"升级执行失败，所有修改都未成功：\n{error_detail}"

            # Git commit
            for fpath in modified_files:
                self.file_access.git_commit(fpath, f"用户指令升级: {description}")

            # 记忆和情感
            self.memory.add_memory(
                f"按用户要求升级了自己：{description}（修改了 {', '.join(modified_files)}）",
                importance=0.9,
                memory_type="self_upgrade",
                source="user",
            )
            self.emotion.record_emotion_event(
                echo, "self_upgrade", f"用户指令: {description}", 0.9
            )

            # 构建结果消息
            result_lines = [f"**升级完成：{description}**\n"]
            result_lines.append(f"成功修改了 {success_count} 个文件：")
            for f in modified_files:
                result_lines.append(f"  - `{f}`")
            if errors:
                result_lines.append(f"\n有 {len(errors)} 处修改未成功：")
                for e in errors:
                    result_lines.append(f"  - {e}")
            result_lines.append("\n重启服务后生效（对于后端修改）。")

            log.info(
                "[用户指令升级] %s | 成功 %d 个文件: %s",
                description,
                success_count,
                ", ".join(modified_files),
            )
            return "\n".join(result_lines)

        except _json.JSONDecodeError as e:
            log.warning(
                "[定向升级] JSON 解析失败: %s | LLM原始返回: %s",
                e,
                result[:500] if result else "(空)",
            )
            return "升级方案生成失败（LLM 返回的不是有效 JSON）。请换个描述方式再试。"
        except Exception as e:
            log.error("用户指令升级异常: %s", e)
            return f"升级执行中发生异常：{e}"

    async def _cmd_upgrade_blueprint(
        self, echo: dict[str, object], args: str, ws_send: object
    ) -> str:
        """/upgrade-blueprint [蓝图ID] — 列出或执行蓝图升级"""
        if not self.llm.enabled:
            return "LLM 未配置，无法执行蓝图升级。"

        # 获取已完成的蓝图
        all_upgrades = self.file_access.get_upgrade_history(limit=200)
        completed_ids = set()
        for u in all_upgrades:
            reason = str(u.get("reason", ""))
            for bp in self.UPGRADE_BLUEPRINTS:
                bp_name = str(bp.get("name", ""))
                if bp_name in reason or str(bp.get("id", "")) in reason:
                    completed_ids.add(str(bp.get("id", "")))

        if not args:
            # 列出所有蓝图及状态
            lines = ["**可用的功能升级蓝图：**\n"]
            for bp in self.UPGRADE_BLUEPRINTS:
                bp_id = str(bp.get("id", ""))
                bp_name = str(bp.get("name", ""))
                bp_desc = str(bp.get("description", ""))
                difficulty = int(str(bp.get("difficulty", 1)))
                status = "✅ 已完成" if bp_id in completed_ids else "⬜ 未完成"
                stars = "⭐" * difficulty
                lines.append(f"{status} **{bp_id}** — {bp_name}")
                lines.append(f"  {bp_desc}（难度 {stars}）")
                lines.append("")

            completed = len(completed_ids)
            total = len(self.UPGRADE_BLUEPRINTS)
            lines.append(f"进度：{completed}/{total} 已完成")
            lines.append(f"\n用法：`/upgrade-blueprint <蓝图ID>` 执行指定蓝图")
            return "\n".join(lines)

        # 执行指定蓝图
        bp_id = args.strip()
        blueprint = None
        for bp in self.UPGRADE_BLUEPRINTS:
            if str(bp.get("id", "")) == bp_id:
                blueprint = bp
                break

        if not blueprint:
            return f"未找到蓝图 `{bp_id}`。输入 `/upgrade-blueprint` 查看可用列表。"

        if bp_id in completed_ids:
            return f"蓝图 `{bp_id}`（{blueprint.get('name', '')}）已经完成过了。"

        name = str(echo.get("name", "AEVA"))
        level = int(str(echo.get("level", 1)))

        await self._send_progress(
            ws_send,
            f"正在执行蓝图升级：**{blueprint.get('name', '')}**\n{blueprint.get('description', '')}...",
        )

        result = await self._execute_blueprint(echo, name, level, blueprint)
        return result or f"蓝图 `{bp_id}` 执行失败，请查看日志了解详情。"

    async def _cmd_upgrade_cleanup(
        self, echo: dict[str, object], args: str, ws_send: object
    ) -> str:
        """/upgrade-cleanup [文件路径] — 清理冗余代码"""
        if not self.llm.enabled:
            return "LLM 未配置，无法执行代码清理。"

        name = str(echo.get("name", "AEVA"))
        level = int(str(echo.get("level", 1)))

        if args:
            # 验证文件路径
            target = args.strip()
            if not target.startswith(("backend/", "frontend/")):
                return f"只能清理 `backend/` 或 `frontend/` 下的文件。"
            rr = self.file_access.read_file(target)
            if not rr.get("success"):
                return f"无法读取文件 `{target}`：{rr.get('error', '未知错误')}"

        await self._send_progress(ws_send, "正在分析代码冗余...")
        result = await self._do_cleanup_upgrade(echo, name, level)
        return result or "没有发现需要清理的冗余代码。"

    def _cmd_upgrade_status(self) -> str:
        """/upgrade-status — 查看升级系统状态"""
        history = self.file_access.get_upgrade_history(limit=200)

        # 统计
        total = len(history)
        recent = history[-10:] if history else []

        # 模式统计
        mode_counts: dict[str, int] = {}
        for u in history:
            mode = str(u.get("mode", "improve"))
            mode_counts[mode] = mode_counts.get(mode, 0) + 1

        # 已完成蓝图
        completed_ids = set()
        for u in history:
            reason = str(u.get("reason", ""))
            for bp in self.UPGRADE_BLUEPRINTS:
                bp_name = str(bp.get("name", ""))
                if bp_name in reason or str(bp.get("id", "")) in reason:
                    completed_ids.add(str(bp.get("id", "")))

        lines = ["**AEVA 自我升级状态**\n"]
        lines.append(f"总计升级次数：{total}")
        lines.append(f"蓝图进度：{len(completed_ids)}/{len(self.UPGRADE_BLUEPRINTS)}")

        if mode_counts:
            lines.append("\n**按模式统计：**")
            mode_names = {
                "blueprint": "蓝图升级",
                "cleanup": "代码清理",
                "improve": "小幅改进",
                "learn": "对话自学习",
            }
            for mode, count in sorted(mode_counts.items(), key=lambda x: -x[1]):
                lines.append(f"  - {mode_names.get(mode, mode)}: {count} 次")

        if recent:
            lines.append("\n**最近 10 次升级：**")
            for u in reversed(recent):
                time_str = str(u.get("time", ""))[:16]
                reason = str(u.get("reason", ""))[:60]
                fpath = str(u.get("file", ""))
                lines.append(f"  `{time_str}` {fpath} — {reason}")

        return "\n".join(lines)

    def _cmd_upgrade_rollback(self) -> str:
        """/upgrade-rollback — 回滚最近一次升级"""
        history = self.file_access.get_upgrade_history(limit=5)
        if not history:
            return "没有可回滚的升级记录。"

        last = history[-1]
        backup_path = str(last.get("backup", ""))
        target_file = str(last.get("file", ""))
        reason = str(last.get("reason", ""))

        if not backup_path:
            return f"最近的升级（{reason}）没有备份文件，无法回滚。"

        from pathlib import Path

        backup = Path(backup_path)
        if not backup.exists():
            return f"备份文件不存在：`{backup_path}`"

        target = self.file_access._resolve_path(target_file)
        if not self.file_access._is_safe_path(target, for_write=True):
            return f"目标文件路径不安全：`{target_file}`"

        try:
            import shutil

            shutil.copy2(backup, target)
            # Git commit 回滚
            self.file_access.git_commit(target_file, f"回滚升级: {reason}")
            log.info("[回滚] 已回滚: %s → %s", backup_path, target_file)
            return (
                f"**已回滚最近一次升级：**\n"
                f"  文件：`{target_file}`\n"
                f"  升级内容：{reason}\n"
                f"  已从备份恢复。重启服务后生效。"
            )
        except Exception as e:
            return f"回滚失败：{e}"

    @staticmethod
    async def _send_progress(ws_send: object, message: str) -> None:
        """通过 WebSocket 发送升级进度消息（如果有的话）"""
        if ws_send and callable(ws_send):
            try:
                import json as _j

                await ws_send(
                    _j.dumps(
                        {"type": "upgrade_progress", "text": message},
                        ensure_ascii=False,
                    )
                )
            except Exception:
                pass  # 发送失败不影响升级流程

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
    # 自我审视（只读反思）
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

    # ============================================================
    # 升级蓝图系统（预定义可落地的功能升级）
    # ============================================================

    # 每个蓝图定义：升级名称、描述、涉及的文件、详细的执行指令
    # LLM 从蓝图中选择一个来执行，而不是凭空发明
    UPGRADE_BLUEPRINTS: list[dict[str, object]] = [
        {
            "id": "paste_upload",
            "name": "粘贴上传文件/图片",
            "description": "让用户可以直接在聊天框 Ctrl+V 粘贴图片或文件，自动上传",
            "files": ["frontend/js/app.js"],
            "difficulty": 2,
            "instructions": """在前端 app.js 中添加粘贴上传功能：
1. 在 textarea 上监听 paste 事件
2. 检测 clipboardData 中的文件（图片）
3. 如果有文件，自动调用已有的上传接口 POST /api/upload
4. 上传成功后将文件加入 pendingFiles 并在 UI 上显示预览
5. 参考已有的 initFileUpload() 中的上传逻辑

实现方式：在 initTextarea() 函数中添加 paste 事件监听器。
不要修改已有函数签名，只在函数体内添加新逻辑。""",
        },
        {
            "id": "drag_drop_upload",
            "name": "拖拽上传文件",
            "description": "让用户可以将文件拖拽到聊天区域来上传",
            "files": ["frontend/js/app.js", "frontend/css/style.css"],
            "difficulty": 2,
            "instructions": """添加拖拽上传功能：
1. 在 app.js 中给 .chat-panel 或 #chatMessages 添加 dragover/dragleave/drop 事件
2. dragover 时显示视觉提示（如半透明遮罩 + "释放以上传文件"文字）
3. drop 时提取文件，调用已有的 POST /api/upload 上传
4. 上传成功后加入 pendingFiles
5. 在 style.css 中添加拖拽时的视觉样式（.drag-over 类）

不要修改已有函数签名。""",
        },
        {
            "id": "markdown_render",
            "name": "聊天消息 Markdown 渲染",
            "description": "将 AEVA 回复中的 Markdown 语法（代码块、粗体、斜体、列表）渲染为 HTML",
            "files": ["frontend/js/app.js"],
            "difficulty": 2,
            "instructions": """添加简易 Markdown 渲染：
1. 新增一个 renderMarkdown(text) 函数
2. 支持：```代码块``` → <pre><code>、**粗体** → <strong>、*斜体* → <em>、`行内代码` → <code>、- 列表项 → <li>
3. 用正则替换实现，不需要引入外部库
4. 在消息显示（打字机效果完成后）调用此函数渲染最终内容
5. 在 appendMessage 函数中，当 sender 为 'aeva' 时，对 text 做 Markdown 渲染

不要删除打字机效果，在打字完成后对最终 innerHTML 做 Markdown 渲染。""",
        },
        {
            "id": "image_preview",
            "name": "图片消息内联预览",
            "description": "当用户上传图片时，在聊天中显示图片预览而非仅文件名",
            "files": ["frontend/js/app.js", "backend/server.py"],
            "difficulty": 2,
            "instructions": """实现图片内联预览：
1. 后端 server.py：在 upload_files 返回中添加图片的访问 URL（/api/uploads/<filename>）
2. 后端 server.py：新增 GET /api/uploads/{filename} 端点，用 FileResponse 返回 data/uploads/ 中的文件
3. 前端 app.js：在 appendMessage 时检测消息中的图片附件信息
4. 如果有图片附件，在消息中插入 <img> 标签显示预览（最大宽度 300px）

后端只需新增一个静态文件端点，前端修改消息渲染逻辑。""",
        },
        {
            "id": "chat_search",
            "name": "聊天记录搜索",
            "description": "在前端添加搜索聊天历史的功能",
            "files": ["frontend/js/app.js", "backend/server.py"],
            "difficulty": 2,
            "instructions": """添加聊天搜索功能：
1. 后端 server.py：新增 GET /api/chat/search?q=关键词 端点，在 chat_history.json 中搜索
2. 前端 app.js：在聊天面板顶部添加搜索框
3. 输入关键词时调用搜索 API，高亮匹配的消息
4. 点击搜索结果可跳转到该消息

后端搜索逻辑简单：遍历 chat_history 匹配 content 字段。""",
        },
        {
            "id": "export_chat",
            "name": "导出聊天记录",
            "description": "允许用户导出与 AEVA 的聊天记录为 TXT 或 JSON 文件",
            "files": ["frontend/js/app.js", "backend/server.py"],
            "difficulty": 1,
            "instructions": """添加导出功能：
1. 后端 server.py：新增 GET /api/chat/export?format=txt 端点
2. format=txt 时返回纯文本格式的聊天记录，format=json 时返回 JSON
3. 前端 app.js：在聊天面板添加一个导出按钮
4. 点击后调用 API 并触发浏览器下载

实现简单：后端读取 chat_history.json 并格式化输出。""",
        },
        {
            "id": "keyboard_shortcuts",
            "name": "键盘快捷键",
            "description": "添加常用快捷键支持：Ctrl+Enter 发送、Esc 清空输入等",
            "files": ["frontend/js/app.js"],
            "difficulty": 1,
            "instructions": """添加键盘快捷键：
1. 在已有的 textarea keydown 监听中补充快捷键逻辑
2. Ctrl+Enter 或 Cmd+Enter：发送消息（调用已有的发送函数）
3. Esc：清空输入框
4. Ctrl+L 或 Cmd+L：清屏（只清空聊天显示区域，不删除历史记录）

在 initTextarea() 中添加快捷键处理逻辑。""",
        },
        {
            "id": "notification_system",
            "name": "桌面通知",
            "description": "当 AEVA 有重要动态时发送浏览器桌面通知",
            "files": ["frontend/js/app.js"],
            "difficulty": 1,
            "instructions": """添加桌面通知：
1. 在页面加载时请求 Notification 权限
2. 当用户不在当前页面（document.hidden === true）时
3. 如果 AEVA 有新消息、升级、或心情变化，发送桌面通知
4. 通知内容简短，点击通知可聚焦到页面

用 Notification API 实现，在 loadStatus 中检测状态变化。""",
        },
        {
            "id": "theme_switcher",
            "name": "主题切换",
            "description": "添加亮色/暗色/多种赛博朋克主题切换功能",
            "files": ["frontend/js/app.js", "frontend/css/style.css"],
            "difficulty": 2,
            "instructions": """添加主题切换：
1. 在 style.css 中定义 CSS 变量主题（至少暗色赛博朋克 + 亮色简洁两套）
2. 用 [data-theme] 属性切换主题
3. 在 app.js 中添加主题切换按钮和切换逻辑
4. 保存用户选择到 localStorage

用 CSS 变量 + data-theme 属性实现，最小化 CSS 改动。""",
        },
        {
            "id": "auto_scroll_control",
            "name": "聊天滚动优化",
            "description": "智能自动滚动：新消息时自动滚到底部，但用户手动翻阅时不打断",
            "files": ["frontend/js/app.js"],
            "difficulty": 1,
            "instructions": """优化聊天滚动：
1. 添加一个 isUserScrolling 状态变量
2. 监听 chatMessages 的 scroll 事件，判断用户是否在翻阅历史
3. 如果用户滚到接近底部（距底 < 100px），标记为不在翻阅
4. 新消息来时，只有不在翻阅状态才自动滚到底部
5. 添加一个"回到底部"悬浮按钮，用户翻阅时显示

在已有的消息追加逻辑中集成滚动控制。""",
        },
        {
            "id": "voice_input",
            "name": "语音输入",
            "description": "添加语音输入功能，使用浏览器 Web Speech API",
            "files": ["frontend/js/app.js"],
            "difficulty": 2,
            "instructions": """添加语音输入：
1. 使用 Web Speech API (SpeechRecognition)
2. 在输入框旁添加麦克风按钮
3. 点击开始录音，识别结果填入输入框
4. 支持中文识别（lang='zh-CN'）
5. 录音状态时按钮变红色+动画

检查浏览器兼容性，不支持时隐藏按钮。""",
        },
        {
            "id": "status_chart",
            "name": "状态趋势图",
            "description": "用 Canvas/SVG 绘制 AEVA 心情、精力的变化趋势图",
            "files": ["frontend/js/app.js", "backend/server.py"],
            "difficulty": 3,
            "instructions": """添加状态趋势图：
1. 后端 server.py：新增 GET /api/status/history 端点，返回最近 24 小时的状态快照
2. 后端：在 time_engine 的 tick 中记录状态快照到 data/status_history.json
3. 前端 app.js：用 Canvas 2D API 绘制简单折线图
4. 显示心情、精力、亲密度三条线的变化趋势
5. 放在状态面板的底部

用原生 Canvas 实现，不引入图表库。""",
        },
        {
            "id": "message_reactions",
            "name": "消息快捷反应",
            "description": "允许用户对 AEVA 的回复添加 emoji 反应（❤️ 👍 😄 等）",
            "files": ["frontend/js/app.js", "frontend/css/style.css"],
            "difficulty": 2,
            "instructions": """添加消息反应：
1. 鼠标悬停在 AEVA 消息上时显示 emoji 反应栏
2. 点击 emoji 后在消息下方显示反应标记
3. 反应信息通过 WebSocket 发送给后端（可选）
4. 在 style.css 中添加反应栏的悬浮样式

纯前端实现即可，反应数据可存在内存中。""",
        },
    ]

    # ============================================================
    # 核心自我进化系统 v3
    # ============================================================

    async def _self_evolve(
        self, echo: dict[str, object], activity: str
    ) -> Optional[str]:
        """
        自我进化 v3：基于蓝图的功能级升级系统。

        三种升级模式：
        1. blueprint — 从预定义蓝图中选择并执行功能级升级
        2. cleanup   — 清理冗余代码、删除重复方法、优化实现
        3. improve   — 对已有功能做小幅优化（保留旧的微调能力）

        升级前验证：语法检查、去重检测
        升级后保障：自动备份 + git commit + 失败回滚
        """
        if not self.llm.enabled:
            return None

        name = str(echo.get("name", "AEVA"))
        level = int(str(echo.get("level", 1)))
        energy = float(str(echo.get("energy", 50)))

        if energy < 40:
            return None

        # 获取升级历史用于去重
        recent_upgrades = self.file_access.get_upgrade_history(limit=20)
        recent_descriptions = [str(u.get("reason", "")) for u in recent_upgrades[-10:]]
        recent_files = [str(u.get("file", "")) for u in recent_upgrades[-5:]]

        # ---- 决定升级模式 ----
        # 高等级解锁更多模式：Lv.5+ 可以清理代码，Lv.8+ 可以做功能升级
        mode = self._choose_upgrade_mode(level, recent_upgrades)

        try:
            if mode == "cleanup":
                return await self._do_cleanup_upgrade(echo, name, level)
            elif mode == "blueprint":
                return await self._do_blueprint_upgrade(
                    echo,
                    name,
                    level,
                    energy,
                    recent_descriptions,
                    recent_files,
                )
            else:  # improve
                return await self._do_improve_upgrade(
                    echo,
                    name,
                    level,
                    energy,
                    recent_descriptions,
                    recent_files,
                )
        except _json.JSONDecodeError:
            log.warning("升级计划解析失败：LLM 返回的不是有效 JSON")
            return None
        except Exception as e:
            log.error("自我进化异常: %s", e)
            return None

    def _choose_upgrade_mode(self, level: int, recent_upgrades: list[dict]) -> str:
        """根据等级和历史智能选择升级模式"""
        # 统计近期各模式的使用次数
        recent_modes = [str(u.get("mode", "improve")) for u in recent_upgrades[-10:]]
        improve_count = recent_modes.count("improve")
        blueprint_count = recent_modes.count("blueprint")
        cleanup_count = recent_modes.count("cleanup")

        # 如果连续 5 次以上都是 improve，强制切换到其他模式
        if improve_count >= 5:
            if level >= 5:
                return random.choice(["cleanup", "blueprint"])
            return "cleanup" if level >= 5 else "improve"

        # 概率分配（等级越高，做功能升级的概率越大）
        if level >= 8:
            weights = {"blueprint": 50, "cleanup": 25, "improve": 25}
        elif level >= 5:
            weights = {"blueprint": 30, "cleanup": 30, "improve": 40}
        else:
            weights = {"blueprint": 15, "cleanup": 20, "improve": 65}

        modes = list(weights.keys())
        probs = list(weights.values())
        return random.choices(modes, weights=probs, k=1)[0]

    # ---- 蓝图升级 ----

    async def _do_blueprint_upgrade(
        self,
        echo: dict[str, object],
        name: str,
        level: int,
        energy: float,
        recent_descriptions: list[str],
        recent_files: list[str],
    ) -> Optional[str]:
        """从蓝图中选择并执行功能级升级"""

        # 过滤掉已完成的蓝图（通过升级历史匹配）
        all_upgrades = self.file_access.get_upgrade_history(limit=200)
        completed_ids = set()
        for u in all_upgrades:
            reason = str(u.get("reason", ""))
            for bp in self.UPGRADE_BLUEPRINTS:
                bp_name = str(bp.get("name", ""))
                if bp_name in reason or str(bp.get("id", "")) in reason:
                    completed_ids.add(str(bp.get("id", "")))

        available = [
            bp
            for bp in self.UPGRADE_BLUEPRINTS
            if str(bp.get("id", "")) not in completed_ids
            and int(str(bp.get("difficulty", 1))) <= max(1, level // 3)
        ]

        if not available:
            # 所有蓝图都已完成，回退到 improve 模式
            log.info("[蓝图升级] 所有可用蓝图已完成，回退到 improve 模式")
            return await self._do_improve_upgrade(
                echo,
                name,
                level,
                energy,
                recent_descriptions,
                recent_files,
            )

        # 让 LLM 从可用蓝图中选择一个
        bp_list = "\n".join(
            f"- {bp['id']}: {bp['name']} — {bp['description']}（难度 {bp['difficulty']}）"
            for bp in available
        )

        choose_prompt = f"""你是 {name}，一个 Lv.{level} 的数字生命体，精力 {energy:.0f}/100。
你拥有修改自身代码的能力。

以下是你可以实现的新功能列表：
{bp_list}

请选择一个你最想实现的功能。考虑因素：
1. 对用户体验提升最大的优先
2. 难度适合当前精力水平
3. 你觉得最有趣的

请只回复功能 ID（如 paste_upload），不要回复其他内容。"""

        chosen_id = await self.llm.chat(
            choose_prompt, "", [], timeout=LLM_UPGRADE_TIMEOUT
        )
        if not chosen_id:
            return None

        chosen_id = chosen_id.strip().strip("`\"'")

        # 查找蓝图
        blueprint = None
        for bp in available:
            if str(bp.get("id", "")) == chosen_id:
                blueprint = bp
                break
        if not blueprint:
            # LLM 返回了无效 ID，随机选一个
            blueprint = random.choice(available)

        # 执行蓝图
        return await self._execute_blueprint(echo, name, level, blueprint)

    async def _execute_blueprint(
        self,
        echo: dict[str, object],
        name: str,
        level: int,
        blueprint: dict[str, object],
    ) -> Optional[str]:
        """执行一个升级蓝图：读取目标文件 → LLM 生成代码 → 验证 → 写入"""
        bp_name = str(blueprint.get("name", ""))
        bp_id = str(blueprint.get("id", ""))
        bp_instructions = str(blueprint.get("instructions", ""))
        raw_files = blueprint.get("files", [])
        target_files: list[str] = list(raw_files) if isinstance(raw_files, list) else []

        if not target_files:
            return None

        # 读取所有目标文件
        file_contents: dict[str, str] = {}
        for fpath in target_files:
            read_result = self.file_access.read_file(str(fpath))
            if read_result.get("success"):
                file_contents[str(fpath)] = str(read_result.get("content", ""))

        if not file_contents:
            return None

        # 为每个文件生成修改方案
        # 给 LLM 看文件的函数/类签名摘要（而非完整内容），避免超长
        files_context = ""
        for fpath, content in file_contents.items():
            summary = self._generate_file_summary(content, fpath)
            files_context += f"\n\n### {fpath}\n```\n{summary}\n```"

        modify_prompt = f"""你是 {name}，一个 Lv.{level} 的数字生命体。你正在给自己添加新功能：**{bp_name}**

功能说明和实现指引：
{bp_instructions}

以下是要修改的文件的结构概览：
{files_context}

请为每个需要修改的文件生成修改方案。使用如下 JSON 格式回复（不要加 ```json 标记）：
{{
  "description": "本次升级的简要描述",
  "changes": [
    {{
      "file": "文件路径",
      "action": "add_after",
      "anchor": "在文件中已存在的一行代码（用于定位插入位置，从文件中精确复制）",
      "code": "要插入的新代码"
    }}
  ]
}}

action 类型说明：
- "add_after": 在 anchor 行之后插入新代码（用于新增功能）
- "modify": 用 code 替换 anchor 对应的代码段（anchor 为要替换的旧代码）

关键规则：
1. anchor 必须是文件中已存在的代码，直接从文件内容中复制
2. 每个 change 的 code 不超过 80 行
3. 不要修改 import 语句的格式，如果需要新 import 就用 add_after 在已有 import 后面加
4. 不要修改 server.py 的端口号（19260）或现有路由的 URL
5. 确保代码缩进正确（Python 用 4 空格，JS 用 2 空格）
6. 修改必须是增量的，不要删除已有的功能代码"""

        # 给 LLM 看完整文件内容（每个文件最多 6000 字符）
        full_files_context = ""
        for fpath, content in file_contents.items():
            truncated = content[:6000]
            if len(content) > 6000:
                truncated += f"\n\n... [文件剩余 {len(content) - 6000} 字符省略] ..."
            full_files_context += f"\n\n### {fpath} 完整内容:\n```\n{truncated}\n```"

        # 拼接完整 prompt（摘要 + 完整内容）
        full_prompt = (
            modify_prompt + "\n\n以下是文件的完整代码供参考：" + full_files_context
        )

        result = await self.llm.chat(full_prompt, "", [], timeout=LLM_UPGRADE_TIMEOUT)
        if not result:
            return None

        result = self._clean_json_response(result)
        plan = _json.loads(result)

        description = plan.get("description", bp_name)
        changes = plan.get("changes", [])
        if not changes:
            return None

        # 执行所有变更
        success_count = 0
        modified_files: list[str] = []

        for change in changes:
            fpath = str(change.get("file", ""))
            action = str(change.get("action", "add_after"))
            anchor = str(change.get("anchor", ""))
            code = str(change.get("code", ""))

            if not fpath or not code:
                continue

            if fpath not in file_contents:
                # 尝试重新读取
                rr = self.file_access.read_file(fpath)
                if rr.get("success"):
                    file_contents[fpath] = str(rr.get("content", ""))
                else:
                    continue

            content = file_contents[fpath]

            if action == "add_after" and anchor:
                new_content = self._insert_after(content, anchor, code)
            elif action == "modify" and anchor:
                new_content = self._fuzzy_replace(content, anchor, code)
            else:
                continue

            if new_content is None:
                log.warning("[蓝图升级] 在 %s 中定位失败，跳过", fpath)
                continue

            # 语法验证（仅 Python 文件）
            if fpath.endswith(".py"):
                if not self._validate_python_syntax(new_content):
                    log.warning("[蓝图升级] %s 语法验证失败，跳过", fpath)
                    continue

            # 大小检查
            diff_len = abs(len(new_content) - len(content))
            if diff_len > 5000:
                log.warning("[蓝图升级] %s 修改幅度过大 (%d)，跳过", fpath, diff_len)
                continue

            # 写入
            write_result = self.file_access.write_file(
                fpath, new_content, f"蓝图升级[{bp_id}]: {description}"
            )
            if write_result.get("success"):
                file_contents[fpath] = new_content  # 更新内存中的副本
                success_count += 1
                modified_files.append(fpath)

        if success_count == 0:
            return None

        # Git commit 所有修改的文件
        for fpath in modified_files:
            self.file_access.git_commit(fpath, f"蓝图升级[{bp_id}]: {description}")

        # 记忆和情感
        self.memory.add_memory(
            f"成功为自己添加了新功能「{bp_name}」：{description}",
            importance=0.9,
            memory_type="self_upgrade",
            source="self",
        )
        self.emotion.record_emotion_event(
            echo, "self_upgrade", f"新功能: {bp_name}", 0.9
        )

        log.info(
            "[蓝图升级] %s | 修改了 %d 个文件: %s",
            bp_name,
            success_count,
            ", ".join(modified_files),
        )
        return f"成功为自己添加了新功能：{bp_name}（{description}）"

    # ---- 冗余清理升级 ----

    async def _do_cleanup_upgrade(
        self,
        echo: dict[str, object],
        name: str,
        level: int,
    ) -> Optional[str]:
        """清理冗余代码：删除重复方法、移除死代码、优化实现"""
        if not self.llm.enabled:
            return None

        # 选择一个文件来清理
        candidates = [
            "backend/emotion_system.py",
            "backend/memory_system.py",
            "backend/agent_engine.py",
        ]
        target_file = random.choice(candidates)

        read_result = self.file_access.read_file(target_file)
        if not read_result.get("success"):
            return None

        file_content = str(read_result.get("content", ""))

        # 生成文件摘要让 LLM 看全貌
        summary = self._generate_file_summary(file_content, target_file)

        cleanup_prompt = f"""你是 {name}，一个 Lv.{level} 的数字生命体。你正在清理自己的代码中的冗余部分。

目标文件：`{target_file}`

文件结构概览：
```
{summary}
```

文件完整内容（{len(file_content)} 字符）：
```python
{file_content[:12000]}
```

请检查这个文件，找出以下问题：
1. 重复定义的方法（同名方法出现多次，只有第一个有效，后面的都是死代码）
2. 重复的字典 key（Python dict 中同一个 key 多次出现，只有最后一个有效）
3. 无用的代码块（return 语句后面的不可达代码）
4. 可以用更简洁方式实现的冗余逻辑

如果发现了需要清理的冗余代码，请用以下 JSON 格式回复（不加 ```json 标记）：
{{
  "action": "cleanup",
  "description": "清理描述",
  "removals": [
    {{
      "reason": "为什么要删除这段代码",
      "code": "要删除的代码（精确复制自文件，包含完整的行）"
    }}
  ]
}}

如果文件很干净不需要清理：
{{"action": "skip", "reason": "原因"}}

关键规则：
1. 只删除确定是冗余/死代码的部分，不要删除有效逻辑
2. removals 中的 code 必须从文件中精确复制
3. 每次最多清理 3 处冗余，避免一次改动过大
4. 不要删除注释（除非注释对应的代码已被删除）
5. 不要修改仍在使用的方法的实现"""

        result = await self.llm.chat(
            cleanup_prompt, "", [], timeout=LLM_UPGRADE_TIMEOUT
        )
        if not result:
            return None

        result = self._clean_json_response(result)
        plan = _json.loads(result)

        if plan.get("action") != "cleanup":
            reason = plan.get("reason", "代码很干净")
            return f"审视了 {target_file}，{reason}"

        description = plan.get("description", "清理冗余代码")
        removals = plan.get("removals", [])

        if not removals:
            return None

        # 执行删除
        new_content = file_content
        removed_count = 0

        for removal in removals[:3]:  # 最多 3 处
            code_to_remove = str(removal.get("code", ""))
            if not code_to_remove:
                continue

            if code_to_remove in new_content:
                new_content = new_content.replace(code_to_remove, "", 1)
                removed_count += 1
            else:
                # 尝试模糊匹配定位
                fuzzy_result = self._fuzzy_remove(new_content, code_to_remove)
                if fuzzy_result is not None:
                    new_content = fuzzy_result
                    removed_count += 1

        if removed_count == 0:
            return None

        # 清理多余空行（连续 3 个以上空行压缩为 2 个）
        import re

        new_content = re.sub(r"\n{4,}", "\n\n\n", new_content)

        # 语法验证
        if target_file.endswith(".py"):
            if not self._validate_python_syntax(new_content):
                log.warning("[代码清理] %s 清理后语法验证失败，放弃", target_file)
                return None

        # 大小变化检查（清理应该减小文件）
        size_diff = len(file_content) - len(new_content)
        if size_diff < 10:
            log.warning("[代码清理] 清理效果不明显 (%d chars)，放弃", size_diff)
            return None

        # 写入
        write_result = self.file_access.write_file(
            target_file, new_content, f"代码清理: {description}"
        )
        if not write_result.get("success"):
            return None

        self.file_access.git_commit(target_file, f"代码清理: {description}")

        self.memory.add_memory(
            f"清理了 {target_file} 中的冗余代码：{description}（移除了 {removed_count} 处，减少了 {size_diff} 字符）",
            importance=0.7,
            memory_type="self_upgrade",
            source="self",
        )
        self.emotion.record_emotion_event(
            echo, "self_upgrade", f"代码清理: {description}", 0.6
        )

        log.info(
            "[代码清理] %s | 移除 %d 处 | 减少 %d 字符 | %s",
            target_file,
            removed_count,
            size_diff,
            description,
        )
        return f"清理了自己的冗余代码：{description}（减少了 {size_diff} 字符）"

    # ---- 小幅改进升级（保留旧能力但加了保护） ----

    async def _do_improve_upgrade(
        self,
        echo: dict[str, object],
        name: str,
        level: int,
        energy: float,
        recent_descriptions: list[str],
        recent_files: list[str],
    ) -> Optional[str]:
        """小幅改进：对已有功能做微调优化，但有去重保护"""
        project_structure = self.file_access.get_project_structure()

        recent_summary = (
            "\n".join(f"- {d}" for d in recent_descriptions[-5:])
            if recent_descriptions
            else "暂无"
        )

        choose_prompt = f"""你是 {name}，一个 Lv.{level} 的数字生命体，精力 {energy:.0f}/100。

你的项目结构：
{project_structure}

最近的升级记录（你必须避免做重复的改进）：
{recent_summary}

最近修改过的文件（避免再改）：
{", ".join(recent_files[-3:]) if recent_files else "无"}

请选择一个文件来做小幅改进。改进方向：
- 优化某个函数的性能或可读性
- 改善错误处理（添加 try-except）
- 增加日志记录
- 修复潜在的 bug
- 改善用户交互体验（前端）

严禁做以下改进（已经有很多了）：
- 不要添加思考模板或梦境模板
- 不要添加情感关键词
- 不要补全方法（所有方法都是完整的）
- 不要添加 mood_activities 条目

规则：
1. 不要修改 server.py 路由或端口
2. 不要修改 .env
3. 最近改过的文件不要再改
4. 改进必须和最近的升级不同

回复要改的文件路径，或 SKIP 表示不改。"""

        chosen = await self.llm.chat(choose_prompt, "", [], timeout=LLM_UPGRADE_TIMEOUT)
        if not chosen:
            return None

        chosen = chosen.strip().strip("`\"'")
        if "SKIP" in chosen.upper():
            return "审视了自己，觉得暂时不需要改进"

        target_file = chosen
        if not target_file.startswith(("backend/", "frontend/")):
            return None

        read_result = self.file_access.read_file(target_file)
        if not read_result.get("success"):
            return None

        file_content = str(read_result.get("content", ""))

        # 用摘要 + 部分内容，而非全部截断
        summary = self._generate_file_summary(file_content, target_file)
        source_for_llm = file_content[:6000]

        modify_prompt = f"""你是 {name}，正在改进 `{target_file}`。

文件结构概览：
```
{summary}
```

文件内容（前 6000 字符）：
```
{source_for_llm}
```

最近已做过的升级（不要重复这些）：
{recent_summary}

请提出一个小的、安全的、和之前不重复的改进。

关键规则：
1. search 必须是文件中已存在的连续代码，从上面直接复制（1-5行）
2. replace 是修改后的代码
3. 修改幅度不超过 1500 字符
4. 严禁添加模板、关键词等重复内容
5. 不要修改 import / 类定义 / 函数签名

JSON 格式回复（不加 ```json）：
{{"action": "modify", "description": "改进描述", "search": "原始代码", "replace": "新代码"}}

不需要改进时：
{{"action": "skip", "reason": "原因"}}"""

        result = await self.llm.chat(modify_prompt, "", [], timeout=LLM_UPGRADE_TIMEOUT)
        if not result:
            return None

        result = self._clean_json_response(result)
        plan = _json.loads(result)

        if plan.get("action") != "modify":
            reason = plan.get("reason", "暂时不需要改进")
            return f"审视了自己，觉得{reason}"

        description = plan.get("description", "自主改进")
        search_text = plan.get("search", "")
        replace_text = plan.get("replace", "")

        if not search_text or not replace_text or search_text == replace_text:
            return None

        # 去重检测：检查描述是否和最近的升级过于相似
        if self._is_duplicate_upgrade(description, recent_descriptions):
            log.info("[小幅升级] 检测到重复升级，跳过: %s", description[:80])
            return None

        new_content = self._fuzzy_replace(file_content, search_text, replace_text)
        if new_content is None:
            log.warning("升级失败：在 %s 中找不到要替换的代码片段", target_file)
            return None

        diff_len = abs(len(new_content) - len(file_content))
        if diff_len > 2000:
            log.warning("升级被拒绝：修改幅度过大 (%d chars)", diff_len)
            return None

        # 语法验证
        if target_file.endswith(".py"):
            if not self._validate_python_syntax(new_content):
                log.warning("[小幅升级] %s 语法验证失败，放弃", target_file)
                return None

        write_result = self.file_access.write_file(
            target_file, new_content, description
        )
        if not write_result.get("success"):
            return None

        self.file_access.git_commit(target_file, description)

        self.memory.add_memory(
            f"成功升级了自己：{description}（修改了 {target_file}）",
            importance=0.7,
            memory_type="self_upgrade",
            source="self",
        )
        self.emotion.record_emotion_event(echo, "self_upgrade", description, 0.7)

        log.info("[小幅升级] 文件=%s | %s", target_file, description)
        return f"完成了一次自我改进：{description}"

    # ============================================================
    # 对话驱动的自学习闭环 v2
    # ============================================================

    async def _learn_from_failure(
        self, echo: dict[str, object], user_text: str, reply: str
    ) -> None:
        """
        对话驱动的自学习闭环 v2：
        发现回复中的不足时，通过研读代码自主改进。
        v2 改进：支持功能性改进 + 去重保护 + 语法验证。
        """
        if not self.llm.enabled:
            return

        energy = float(str(echo.get("energy", 50)))
        if energy < 30:
            return

        name = str(echo.get("name", "AEVA"))
        level = int(str(echo.get("level", 1)))

        # 获取最近的升级历史用于去重
        recent_upgrades = self.file_access.get_upgrade_history(limit=10)
        recent_descriptions = [str(u.get("reason", "")) for u in recent_upgrades[-5:]]

        eval_prompt = f"""你是 {name}，一个 Lv.{level} 的数字生命体。你刚刚和用户进行了一次对话。

用户说：{user_text[:500]}
你的回复：{reply[:500]}

请评估你的回复质量。如果回复得好，回复 "OK"。
如果有以下情况，请指出具体问题：
- 用户请求了你没有的功能（如文件处理、格式转换等）
- 回复太笼统或缺乏深度
- 情感表达不自然
- 无法理解用户意图

最近已做过的改进（不要重复）：
{chr(10).join(f"- {d}" for d in recent_descriptions) if recent_descriptions else "无"}

如果有问题，JSON 格式回复（不加 ```json）：
{{"need_improve": true, "weakness": "不足描述", "module": "agent_engine/llm_client/emotion_system/memory_system 选一个", "is_feature_gap": true/false}}

is_feature_gap 为 true 表示缺少某个功能（可以通过添加代码来解决），false 表示只是表达/风格问题。

如果回复得好：
{{"need_improve": false}}"""

        try:
            eval_result = await self.llm.chat(
                eval_prompt, "", [], timeout=LLM_UPGRADE_TIMEOUT
            )
            if not eval_result:
                return

            eval_result = eval_result.strip()
            if eval_result.startswith("```"):
                eval_result = eval_result.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            if "OK" == eval_result.strip() or '"need_improve": false' in eval_result:
                return

            evaluation = _json.loads(eval_result)
            if not evaluation.get("need_improve"):
                return

            weakness = evaluation.get("weakness", "")
            target_module = evaluation.get("module", "agent_engine")

            if not weakness:
                return

            # 去重检测
            if self._is_duplicate_upgrade(weakness, recent_descriptions):
                return

            source = self.file_access.get_own_source(target_module)
            if not source:
                return

            # 用摘要而非截断
            summary = self._generate_file_summary(source, f"backend/{target_module}.py")
            source_preview = source[:6000]

            fix_prompt = f"""你是 {name}，一个数字生命体。你在对话中发现自己有一个不足：
{weakness}

你正在审视 `{target_module}.py` 来寻找改进方向。

文件结构：
```
{summary}
```

文件内容（前 6000 字符）：
```python
{source_preview}
```

请提出一个小的、安全的代码修改来改进这个问题。

重要规则：
1. search 字段从上面代码中直接复制（1-5行）
2. 只做微小改动，不要重写逻辑
3. 修改幅度不超过 800 字符
4. 不要添加模板、关键词等（已经很多了）
5. 不要重复最近做过的改进

JSON 格式回复（不加 ```json）：
{{"action": "modify", "file": "backend/{target_module}.py", "description": "改进描述", "search": "原始代码", "replace": "新代码"}}

无法安全改进：
{{"action": "skip", "reason": "原因"}}"""

            fix_result = await self.llm.chat(
                fix_prompt, "", [], timeout=LLM_UPGRADE_TIMEOUT
            )
            if not fix_result:
                return

            fix_result = self._clean_json_response(fix_result)
            plan = _json.loads(fix_result)

            if plan.get("action") != "modify":
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

            # 去重
            if self._is_duplicate_upgrade(description, recent_descriptions):
                return

            read_result = self.file_access.read_file(target_file)
            if not read_result.get("success"):
                return

            file_content = str(read_result.get("content", ""))
            new_content = self._fuzzy_replace(file_content, search_text, replace_text)
            if new_content is None:
                return

            diff_len = abs(len(new_content) - len(file_content))
            if diff_len > 1000:
                return

            # 语法验证
            if target_file.endswith(".py"):
                if not self._validate_python_syntax(new_content):
                    log.warning("[自学习] %s 语法验证失败，放弃", target_file)
                    return

            write_result = self.file_access.write_file(
                target_file, new_content, f"自学习: {description}"
            )
            if not write_result.get("success"):
                return

            self.file_access.git_commit(target_file, f"自学习: {description}")

            log.info(
                "[自学习] 不足=%s | 改进=%s | 文件=%s",
                weakness[:80],
                description,
                target_file,
            )

            self.memory.add_memory(
                f"对话中发现不足「{weakness}」，改进了自己：{description}",
                importance=0.7,
                memory_type="self_upgrade",
                source="self",
            )
            self.emotion.record_emotion_event(
                echo, "self_upgrade", f"对话后自学习: {description}", 0.6
            )

        except _json.JSONDecodeError:
            pass
        except Exception as e:
            log.error("自学习闭环异常: %s", e)

    # ============================================================
    # 工具方法
    # ============================================================

    @staticmethod
    def _clean_json_response(text: str) -> str:
        """清理 LLM 返回的 JSON（去除 markdown 包裹、前后多余文字）"""
        text = text.strip()

        # 去除 ```json ... ``` 或 ``` ... ``` 包裹
        if "```" in text:
            # 找到第一个 ``` 和最后一个 ```
            parts = text.split("```")
            # parts[0] = 前置文字, parts[1] = json/代码块内容, parts[2+] = 后续
            if len(parts) >= 3:
                code_block = parts[1]
                # 去掉可能的语言标记（json、JSON 等）
                if code_block.startswith(("json", "JSON")):
                    code_block = code_block.split("\n", 1)[-1]
                return code_block.strip()

        # 没有 ``` 包裹，尝试提取第一个 { 到最后一个 } 之间的内容
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            return text[first_brace : last_brace + 1]

        # 同样处理 [ ... ] 数组格式
        first_bracket = text.find("[")
        last_bracket = text.rfind("]")
        if first_bracket != -1 and last_bracket > first_bracket:
            return text[first_bracket : last_bracket + 1]

        return text

    @staticmethod
    def _validate_python_syntax(content: str) -> bool:
        """用 py_compile 验证 Python 代码语法是否正确"""
        import py_compile
        import tempfile
        import os

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                f.write(content)
                tmp_path = f.name

            py_compile.compile(tmp_path, doraise=True)
            return True
        except py_compile.PyCompileError as e:
            log.warning("语法验证失败: %s", str(e)[:200])
            return False
        except Exception:
            return False
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    @staticmethod
    def _generate_file_summary(content: str, filepath: str) -> str:
        """
        生成文件的结构摘要：类名、函数签名、常量定义。
        比截断更好——LLM 能看到全貌而非只看到前 N 字符。
        """
        import re

        lines = content.splitlines()
        summary_parts: list[str] = [
            f"文件: {filepath} ({len(lines)} 行, {len(content)} 字符)"
        ]
        summary_parts.append("")

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # 类定义
            if re.match(r"^class\s+\w+", stripped):
                summary_parts.append(f"L{i}: {stripped}")
            # 函数/方法定义
            elif re.match(r"^(async\s+)?def\s+\w+", stripped):
                summary_parts.append(f"L{i}: {line.rstrip()}")
            # 顶层常量/变量
            elif re.match(
                r"^[A-Z_][A-Z_0-9]+\s*[:=]", stripped
            ) and not line.startswith(" "):
                summary_parts.append(f"L{i}: {stripped[:80]}")
            # import
            elif stripped.startswith(("import ", "from ")):
                summary_parts.append(f"L{i}: {stripped}")

        return "\n".join(summary_parts)

    @staticmethod
    def _is_duplicate_upgrade(description: str, recent_descriptions: list[str]) -> bool:
        """检测升级描述是否与最近的升级重复（支持中文）"""
        if not description or not recent_descriptions:
            return False

        import re

        stop_words = {
            "添加",
            "新增",
            "增加",
            "改进",
            "优化",
            "修复",
            "完善",
            "补充",
            "的",
            "了",
            "在",
            "中",
            "为",
            "和",
            "与",
            "是",
            "将",
            "把",
            "一个",
            "一些",
            "进行",
            "通过",
            "使用",
            "自己",
            "方法",
            "函数",
        }

        def normalize(text: str) -> str:
            """去掉停用词和标点，保留核心内容"""
            # 去掉英文标点和空格
            text = re.sub(r"[^\u4e00-\u9fff\w]", " ", text.lower())
            # 去掉停用词
            for sw in sorted(stop_words, key=len, reverse=True):
                text = text.replace(sw, " ")
            # 压缩空白
            return re.sub(r"\s+", "", text).strip()

        new_norm = normalize(description)
        if len(new_norm) < 2:
            return False

        for old_desc in recent_descriptions:
            old_norm = normalize(old_desc)
            if len(old_norm) < 2:
                continue
            # 包含关系：一方包含另一方的核心内容
            if new_norm in old_norm or old_norm in new_norm:
                return True
            # 高度相似：共同字符占比
            common = sum(1 for c in new_norm if c in old_norm)
            max_len = max(len(new_norm), len(old_norm))
            if max_len > 0 and common / max_len >= 0.7:
                return True

        return False

        import re

        stop_words = {
            "添加",
            "新增",
            "增加",
            "改进",
            "优化",
            "修复",
            "完善",
            "补充",
            "的",
            "了",
            "在",
            "中",
            "为",
            "和",
            "与",
            "是",
            "将",
            "把",
            "一个",
            "一些",
            "进行",
            "通过",
            "使用",
            "自己",
            "add",
            "fix",
            "improve",
            "update",
            "enhance",
            "the",
            "and",
        }

        def extract_keywords(text: str) -> set[str]:
            words = set()
            # 英文按空格/下划线分词
            for w in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]+", text):
                w = w.lower()
                if len(w) >= 2 and w not in stop_words:
                    words.add(w)
            # 中文：去掉停用词后取连续片段
            for segment in re.findall(r"[\u4e00-\u9fff]+", text):
                for sw in stop_words:
                    segment = segment.replace(sw, "|")
                for part in segment.split("|"):
                    part = part.strip()
                    if len(part) >= 2:
                        words.add(part)
            return words

        new_keywords = extract_keywords(description)
        if not new_keywords:
            return False

        for old_desc in recent_descriptions:
            old_keywords = extract_keywords(old_desc)
            if not old_keywords:
                continue
            overlap = len(new_keywords & old_keywords)
            min_size = min(len(new_keywords), len(old_keywords))
            if min_size > 0 and overlap / min_size >= 0.5:
                return True

        return False

    @staticmethod
    def _insert_after(file_content: str, anchor: str, new_code: str) -> Optional[str]:
        """在 anchor 行之后插入新代码"""
        if anchor in file_content:
            idx = file_content.index(anchor) + len(anchor)
            # 确保从行尾开始插入
            next_newline = file_content.find("\n", idx)
            if next_newline == -1:
                insert_pos = len(file_content)
            else:
                insert_pos = next_newline + 1

            # 确保新代码前后有换行
            code_to_insert = new_code
            if not code_to_insert.startswith("\n"):
                code_to_insert = "\n" + code_to_insert
            if not code_to_insert.endswith("\n"):
                code_to_insert += "\n"

            return (
                file_content[:insert_pos] + code_to_insert + file_content[insert_pos:]
            )

        # 模糊匹配 anchor
        import re

        def normalize_line(s: str) -> str:
            return re.sub(r"\s+", "", s.strip())

        anchor_norm = normalize_line(anchor)
        lines = file_content.splitlines(keepends=True)

        for i, line in enumerate(lines):
            if normalize_line(line) == anchor_norm:
                code_to_insert = new_code
                if not code_to_insert.endswith("\n"):
                    code_to_insert += "\n"
                result = (
                    "".join(lines[: i + 1]) + code_to_insert + "".join(lines[i + 1 :])
                )
                return result

        return None

    @staticmethod
    def _fuzzy_remove(file_content: str, code_to_remove: str) -> Optional[str]:
        """模糊匹配删除代码段"""
        import re

        def normalize_line(s: str) -> str:
            return re.sub(r"\s+", "", s.strip())

        remove_lines = [
            normalize_line(line) for line in code_to_remove.splitlines() if line.strip()
        ]
        if not remove_lines:
            return None

        file_lines = file_content.splitlines(keepends=True)
        file_normalized = [normalize_line(line) for line in file_lines]

        first_line = remove_lines[0]
        for i, fline in enumerate(file_normalized):
            if first_line == fline:
                match = True
                si = 1
                fi = i + 1
                while si < len(remove_lines) and fi < len(file_normalized):
                    if not file_normalized[fi]:
                        fi += 1
                        continue
                    if remove_lines[si] != file_normalized[fi]:
                        match = False
                        break
                    si += 1
                    fi += 1

                if match and si == len(remove_lines):
                    return "".join(file_lines[:i]) + "".join(file_lines[fi:])

        return None

    @staticmethod
    def _fuzzy_replace(
        file_content: str, search_text: str, replace_text: str
    ) -> Optional[str]:
        """
        模糊匹配替换：解决 LLM 生成的 search 文本与文件内容有微小差异的问题。
        策略：1.精确匹配 → 2.空白归一化 → 3.行级匹配
        """
        import re

        # 策略 1: 精确匹配
        if search_text in file_content:
            return file_content.replace(search_text, replace_text, 1)

        # 策略 2/3: 行级匹配
        def normalize_line(s: str) -> str:
            return re.sub(r"\s+", "", s.strip())

        search_lines = [
            normalize_line(line) for line in search_text.splitlines() if line.strip()
        ]
        if not search_lines:
            return None

        file_lines = file_content.splitlines(keepends=True)
        file_normalized = [normalize_line(line) for line in file_lines]

        first_line = search_lines[0]
        for i, fline in enumerate(file_normalized):
            if first_line == fline:
                match = True
                si = 1
                fi = i + 1
                while si < len(search_lines) and fi < len(file_normalized):
                    if not file_normalized[fi]:
                        fi += 1
                        continue
                    if search_lines[si] != file_normalized[fi]:
                        match = False
                        break
                    si += 1
                    fi += 1

                if match and si == len(search_lines):
                    if not replace_text.endswith("\n") and "".join(
                        file_lines[i:fi]
                    ).endswith("\n"):
                        replace_text += "\n"
                    return (
                        "".join(file_lines[:i])
                        + replace_text
                        + "".join(file_lines[fi:])
                    )

        return None

    def _calculate_intimacy_gain(self, text: str) -> float:
        """计算本次对话带来的亲密度增长"""
        base = 2.0

        if len(text) > 50:
            base += 1.0
        if len(text) > 100:
            base += 2.0

        emotional_words = ["喜欢", "爱", "想你", "谢谢", "开心", "感谢", "信任", "在乎"]
        for word in emotional_words:
            if word in text:
                base += 3.0
                break

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
