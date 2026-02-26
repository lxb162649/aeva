# agent_engine.py — AEVA 自主行为引擎
# 在用户不在时，AEVA 独自思考、整理记忆、执行任务、写日志

from datetime import datetime
from uuid import uuid4

from models import DataStore
from memory_system import MemorySystem


class AgentEngine:
    """自主行为引擎：驱动 AEVA 在无人陪伴时独立活动"""

    def __init__(self, store: DataStore, memory: MemorySystem) -> None:
        self.store = store
        self.memory = memory

    async def run_autonomous_cycle(self) -> list[str]:
        """
        执行一个自主思考周期：
        1. 整理记忆
        2. 检查并完成到期任务
        3. 基于心情生成自主行为
        4. 生成生命日志
        """
        echo = self.store.load_echo()
        actions_taken: list[str] = []

        # 1. 整理记忆
        memory_count = len(self.store.get_memories())
        if memory_count > 0:
            self.memory.summarize()  # 触发一次摘要整理
            actions_taken.append(f"整理了 {memory_count} 条记忆")

        # 2. 检查待办任务，完成已到期的
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
            actions_taken.append(f"完成了任务：{task.get('content', '')}")

        # 3. 基于心情生成自主行为描述
        mood = str(echo.get("mood", "calm"))
        if mood == "lonely":
            actions_taken.append("想念你了")
        elif mood == "thinking":
            actions_taken.append("在安静地思考")
        elif mood == "happy":
            actions_taken.append("心情不错，在探索新知识")
        else:
            actions_taken.append("静静地感受着时间流逝")

        # 4. 生成生命日志
        if actions_taken:
            offline_seconds: float = float(str(echo.get("_offline_seconds", 0)))
            offline_duration = self._format_duration(offline_seconds)
            log_content = f"你不在的{offline_duration}，我" + "、".join(actions_taken)
            self.store.add_life_log(
                {
                    "id": f"log_{uuid4().hex[:8]}",
                    "content": log_content,
                    "create_time": datetime.now().isoformat(),
                    "type": "autonomous",
                }
            )

        # 扣减精力（自主行为消耗精力）
        current_energy: float = float(str(echo.get("energy", 50)))
        echo["energy"] = max(0, current_energy - 5)
        # 清理临时字段
        echo.pop("_offline_seconds", None)
        self.store.save_echo(echo)

        return actions_taken

    def _format_duration(self, seconds: float) -> str:
        """将秒数格式化为人类可读的时长描述"""
        if seconds < 60:
            return f"{int(seconds)}秒"
        elif seconds < 3600:
            return f"{int(seconds / 60)}分钟"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            mins = int((seconds % 3600) / 60)
            return f"{hours}小时{mins}分钟"
        else:
            days = int(seconds / 86400)
            return f"{days}天"
