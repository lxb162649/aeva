# models.py — AEVA 数据模型 v2
# 使用 JSON 文件持久化，存储到 data 目录
# 新增：对话历史存储、亲密度字段、情感记忆

import json
from pathlib import Path
from datetime import datetime
from uuid import uuid4

from logger import get_logger

log = get_logger("DataStore")


# 默认 Echo 实体（新增 intimacy / emotion_memory / activity 字段）
DEFAULT_ECHO: dict[str, object] = {
    "id": "aeva_001",
    "name": "AEVA",
    "create_time": "",
    "last_active": "",
    "total_life_seconds": 0,
    "mood": "calm",
    "activity": "waiting",
    "energy": 80,
    "level": 1,
    "exp": 0,
    "intimacy": 0,
    "personality": {"talkativeness": 0.6, "warmth": 0.8, "curiosity": 0.7},
    "emotion_memory": [],
}


class DataStore:
    """JSON 文件数据存储管理器 v2"""

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        # 各数据文件路径
        self.echo_path = self.data_dir / "echo.json"
        self.memories_path = self.data_dir / "memories.json"
        self.tasks_path = self.data_dir / "tasks.json"
        self.logs_path = self.data_dir / "life_logs.json"
        self.chat_history_path = self.data_dir / "chat_history.json"
        # 确保目录和默认数据存在
        self._ensure_init()

    def _ensure_init(self) -> None:
        """确保 data 目录存在，且各 JSON 文件已初始化"""
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 初始化 Echo 实体
        if not self.echo_path.exists():
            now = datetime.now().isoformat()
            echo = dict(DEFAULT_ECHO)
            echo["create_time"] = now
            echo["last_active"] = now
            self._write_json(self.echo_path, echo)
        else:
            # 迁移旧数据：确保新字段存在
            self._migrate_echo()

        # 初始化其他数据文件
        for path in [
            self.memories_path,
            self.tasks_path,
            self.logs_path,
            self.chat_history_path,
        ]:
            if not path.exists():
                self._write_json(path, [])

    def _migrate_echo(self) -> None:
        """迁移旧版 Echo 数据，补充缺失的新字段"""
        echo = self._read_json(self.echo_path)
        if not isinstance(echo, dict):
            return

        changed = False
        # 补充 v2 新增字段
        defaults: dict[str, object] = {
            "intimacy": 0,
            "activity": "waiting",
            "emotion_memory": [],
        }
        for key, default_val in defaults.items():
            if key not in echo:
                echo[key] = default_val
                changed = True

        # 补充 personality.curiosity
        personality = echo.get("personality", {})
        if isinstance(personality, dict) and "curiosity" not in personality:
            personality["curiosity"] = 0.7
            echo["personality"] = personality
            changed = True

        if changed:
            self._write_json(self.echo_path, echo)

    # ---- 通用读写 ----

    def _read_json(self, path: Path) -> dict | list:
        """读取 JSON 文件"""
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_json(self, path: Path, data: dict | list) -> None:
        """写入 JSON 文件（格式化缩进，便于调试）"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ---- Echo 实体 ----

    def load_echo(self) -> dict[str, object]:
        """加载 Echo 实体状态"""
        return self._read_json(self.echo_path)  # type: ignore[return-value]

    def save_echo(self, echo: dict[str, object]) -> None:
        """保存 Echo 实体状态"""
        self._write_json(self.echo_path, echo)

    # ---- 记忆 ----

    def add_memory(self, memory: dict[str, object]) -> None:
        """添加一条记忆"""
        memories = self.get_memories()
        memories.append(memory)
        self._write_json(self.memories_path, memories)

    def get_memories(self) -> list[dict[str, object]]:
        """获取全部记忆"""
        return self._read_json(self.memories_path)  # type: ignore[return-value]

    # ---- 对话历史 ----

    def add_chat_message(self, role: str, content: str) -> None:
        """添加一条对话消息到历史"""
        history = self.get_chat_history()
        history.append(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
            }
        )
        # 只保留最近 100 条消息
        if len(history) > 100:
            history = history[-100:]
        self._write_json(self.chat_history_path, history)

    def get_chat_history(self) -> list[dict[str, str]]:
        """获取对话历史"""
        return self._read_json(self.chat_history_path)  # type: ignore[return-value]

    def get_chat_history_for_llm(self, limit: int = 40) -> list[dict[str, str]]:
        """获取适合传给 LLM 的对话历史（只含 role + content）"""
        history = self.get_chat_history()
        result: list[dict[str, str]] = []
        for msg in history[-limit:]:
            result.append(
                {
                    "role": str(msg.get("role", "user")),
                    "content": str(msg.get("content", "")),
                }
            )
        return result

    # ---- 自主任务 ----

    def add_task(self, task: dict[str, object]) -> None:
        """添加一个自主任务"""
        tasks = self._get_all_tasks()
        tasks.append(task)
        self._write_json(self.tasks_path, tasks)

    def _get_all_tasks(self) -> list[dict[str, object]]:
        """获取全部任务（包含所有状态）"""
        return self._read_json(self.tasks_path)  # type: ignore[return-value]

    def get_pending_tasks(self) -> list[dict[str, object]]:
        """获取所有待处理任务"""
        tasks = self._get_all_tasks()
        return [t for t in tasks if t.get("status") == "pending"]

    def get_all_tasks(self) -> list[dict[str, object]]:
        """获取全部任务（公开接口）"""
        return self._get_all_tasks()

    def update_task(self, updated_task: dict[str, object]) -> None:
        """更新指定任务（按 task_id 匹配）"""
        tasks = self._get_all_tasks()
        for i, t in enumerate(tasks):
            if t.get("task_id") == updated_task.get("task_id"):
                tasks[i] = updated_task
                break
        self._write_json(self.tasks_path, tasks)

    # ---- 生命日志 ----

    def add_life_log(self, log: dict[str, object]) -> None:
        """添加一条生命日志"""
        logs = self.get_life_logs()
        logs.append(log)
        # 日志最多保留 500 条
        if len(logs) > 500:
            logs = logs[-500:]
        self._write_json(self.logs_path, logs)

    def get_life_logs(self) -> list[dict[str, object]]:
        """获取全部生命日志"""
        return self._read_json(self.logs_path)  # type: ignore[return-value]
