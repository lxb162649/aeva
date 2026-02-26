# models.py — AEVA 数据模型
# 使用 JSON 文件持久化，存储到 data 目录

import json
from pathlib import Path
from datetime import datetime
from uuid import uuid4
from typing import Optional


# 默认 Echo 实体
DEFAULT_ECHO: dict[str, object] = {
    "id": "aeva_001",
    "name": "AEVA",
    "create_time": "",
    "last_active": "",
    "total_life_seconds": 0,
    "mood": "calm",
    "energy": 80,
    "level": 1,
    "exp": 0,
    "personality": {"talkativeness": 0.6, "warmth": 0.8},
}


class DataStore:
    """JSON 文件数据存储管理器"""

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        # 各数据文件路径
        self.echo_path = self.data_dir / "echo.json"
        self.memories_path = self.data_dir / "memories.json"
        self.tasks_path = self.data_dir / "tasks.json"
        self.logs_path = self.data_dir / "life_logs.json"
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

        # 初始化记忆列表
        if not self.memories_path.exists():
            self._write_json(self.memories_path, [])

        # 初始化任务列表
        if not self.tasks_path.exists():
            self._write_json(self.tasks_path, [])

        # 初始化生命日志
        if not self.logs_path.exists():
            self._write_json(self.logs_path, [])

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
        self._write_json(self.logs_path, logs)

    def get_life_logs(self) -> list[dict[str, object]]:
        """获取全部生命日志"""
        return self._read_json(self.logs_path)  # type: ignore[return-value]
