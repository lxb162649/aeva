# file_access.py — AEVA 文件系统访问模块
# 允许 AEVA 在安全沙箱内读写自身项目文件，用于自我审视和升级
# 所有操作限制在项目根目录内，禁止访问系统敏感文件

import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

from logger import get_logger

log = get_logger("FileAccess")


# ---- 安全配置 ----
PROJECT_ROOT = Path("/home/lxb/桌面/aeva")

# 允许读取的目录
READABLE_DIRS = [
    PROJECT_ROOT / "backend",
    PROJECT_ROOT / "frontend",
    PROJECT_ROOT / "data",
]

# 允许写入的目录（更严格）
WRITABLE_DIRS = [
    PROJECT_ROOT / "backend",
    PROJECT_ROOT / "frontend",
    PROJECT_ROOT / "data",
]

# 禁止访问的文件（即使在允许目录内）
FORBIDDEN_FILES = {".env", ".env.example", "credentials", "secrets"}

# 备份目录
BACKUP_DIR = PROJECT_ROOT / "data" / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# 升级日志
UPGRADE_LOG_PATH = PROJECT_ROOT / "data" / "upgrade_logs.json"


class FileAccess:
    """
    AEVA 的文件系统访问能力。
    在安全沙箱内允许读写项目文件，用于：
    - 审视自身代码，了解自己的结构
    - 修改自身代码，实现自我升级
    - 读取数据文件，了解自身状态
    所有写操作会自动备份原文件。
    """

    def __init__(self) -> None:
        self.project_root = PROJECT_ROOT
        self.upgrade_history: list[dict] = self._load_upgrade_logs()

    # ============================================================
    # 安全检查
    # ============================================================

    def _is_safe_path(self, path: Path, for_write: bool = False) -> bool:
        """检查路径是否在安全沙箱内"""
        try:
            resolved = path.resolve()
        except (OSError, ValueError):
            return False

        # 检查文件名是否被禁止
        if resolved.name in FORBIDDEN_FILES:
            return False

        # 不允许访问隐藏文件（.开头，除了特定文件）
        for part in resolved.parts:
            if part.startswith(".") and part not in (".", ".."):
                return False

        # 检查是否在允许的目录内
        allowed_dirs = WRITABLE_DIRS if for_write else READABLE_DIRS
        for allowed in allowed_dirs:
            try:
                resolved.relative_to(allowed.resolve())
                return True
            except ValueError:
                continue

        return False

    # ============================================================
    # 读取能力
    # ============================================================

    def read_file(self, filepath: str) -> dict[str, object]:
        """
        读取项目内的文件内容。
        返回: {"success": bool, "content": str, "error": str, "size": int}
        """
        path = self._resolve_path(filepath)

        if not self._is_safe_path(path, for_write=False):
            return {"success": False, "content": "", "error": f"禁止访问: {filepath}"}

        if not path.exists():
            return {"success": False, "content": "", "error": f"文件不存在: {filepath}"}

        if not path.is_file():
            return {"success": False, "content": "", "error": f"不是文件: {filepath}"}

        # 限制读取大小 (500KB)
        size = path.stat().st_size
        if size > 500 * 1024:
            return {"success": False, "content": "", "error": f"文件过大: {size} bytes"}

        try:
            content = path.read_text(encoding="utf-8")
            return {
                "success": True,
                "content": content,
                "error": "",
                "size": len(content),
                "path": str(path.relative_to(self.project_root)),
            }
        except UnicodeDecodeError:
            return {"success": False, "content": "", "error": "文件不是文本格式"}
        except Exception as e:
            return {"success": False, "content": "", "error": str(e)}

    def list_dir(self, dirpath: str = "") -> dict[str, object]:
        """
        列出目录内容。
        返回: {"success": bool, "entries": list, "error": str}
        """
        path = self._resolve_path(dirpath) if dirpath else self.project_root

        if not self._is_safe_path(path, for_write=False):
            # 允许列出根目录
            if path.resolve() != self.project_root.resolve():
                return {
                    "success": False,
                    "entries": [],
                    "error": f"禁止访问: {dirpath}",
                }

        if not path.exists() or not path.is_dir():
            return {"success": False, "entries": [], "error": f"目录不存在: {dirpath}"}

        entries: list[dict[str, str]] = []
        try:
            for item in sorted(path.iterdir()):
                # 跳过隐藏文件和不安全路径
                if item.name.startswith("."):
                    continue
                if item.name in ("node_modules", "__pycache__", ".venv", "venv"):
                    continue

                entry_type = "dir" if item.is_dir() else "file"
                size = ""
                if item.is_file():
                    size = str(item.stat().st_size)

                entries.append(
                    {
                        "name": item.name,
                        "type": entry_type,
                        "size": size,
                        "path": str(item.relative_to(self.project_root)),
                    }
                )
        except PermissionError:
            return {"success": False, "entries": [], "error": "权限不足"}

        return {"success": True, "entries": entries, "error": ""}

    def get_project_structure(self) -> str:
        """获取项目文件结构的文本表示，供 LLM 了解自身结构"""
        lines: list[str] = ["AEVA 项目结构:"]
        for dir_path in READABLE_DIRS:
            if not dir_path.exists():
                continue
            rel = dir_path.relative_to(self.project_root)
            lines.append(f"\n{rel}/")
            self._tree(dir_path, lines, prefix="  ", depth=0, max_depth=3)
        return "\n".join(lines)

    def _tree(
        self, path: Path, lines: list[str], prefix: str, depth: int, max_depth: int
    ) -> None:
        """递归生成目录树"""
        if depth >= max_depth:
            return
        try:
            items = sorted(path.iterdir())
        except PermissionError:
            return

        for item in items:
            if item.name.startswith(".") or item.name in (
                "node_modules",
                "__pycache__",
                ".venv",
                "venv",
                "uploads",
            ):
                continue
            if item.is_dir():
                lines.append(f"{prefix}{item.name}/")
                self._tree(item, lines, prefix + "  ", depth + 1, max_depth)
            else:
                size = item.stat().st_size
                lines.append(f"{prefix}{item.name} ({size}B)")

    # ============================================================
    # 写入能力（自我升级的核心）
    # ============================================================

    def write_file(
        self, filepath: str, content: str, reason: str = ""
    ) -> dict[str, object]:
        """
        写入文件（会自动备份原文件）。
        filepath: 相对于项目根目录的路径
        content: 新文件内容
        reason: 修改原因（记入升级日志）
        返回: {"success": bool, "error": str, "backup_path": str}
        """
        path = self._resolve_path(filepath)

        if not self._is_safe_path(path, for_write=True):
            return {
                "success": False,
                "error": f"禁止写入: {filepath}",
                "backup_path": "",
            }

        # 写入前备份
        backup_path = ""
        if path.exists():
            backup_path = self._backup_file(path)

        try:
            # 确保父目录存在
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

            # 记录升级日志
            self._log_upgrade(filepath, reason, backup_path)

            return {
                "success": True,
                "error": "",
                "backup_path": backup_path,
                "path": str(path.relative_to(self.project_root)),
            }
        except Exception as e:
            # 写入失败，尝试恢复备份
            if backup_path:
                self._restore_backup(backup_path, path)
            return {"success": False, "error": str(e), "backup_path": ""}

    def _backup_file(self, path: Path) -> str:
        """备份文件到 data/backups/ 目录"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rel = path.relative_to(self.project_root)
        safe_name = str(rel).replace("/", "__").replace("\\", "__")
        backup_name = f"{timestamp}_{safe_name}"
        backup_path = BACKUP_DIR / backup_name

        try:
            shutil.copy2(path, backup_path)
            return str(backup_path)
        except Exception as e:
            log.error("备份失败: %s", e)
            return ""

    def _restore_backup(self, backup_path: str, target: Path) -> bool:
        """从备份恢复文件"""
        try:
            shutil.copy2(backup_path, target)
            return True
        except Exception:
            return False

    # ============================================================
    # 升级日志
    # ============================================================

    def _load_upgrade_logs(self) -> list[dict]:
        """加载升级历史"""
        if UPGRADE_LOG_PATH.exists():
            try:
                import json

                return json.loads(UPGRADE_LOG_PATH.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    def _log_upgrade(self, filepath: str, reason: str, backup_path: str) -> None:
        """记录一次文件修改"""
        import json

        entry = {
            "time": datetime.now().isoformat(),
            "file": filepath,
            "reason": reason or "自主升级",
            "backup": backup_path,
        }
        self.upgrade_history.append(entry)

        # 最多保留 200 条记录
        if len(self.upgrade_history) > 200:
            self.upgrade_history = self.upgrade_history[-200:]

        try:
            UPGRADE_LOG_PATH.write_text(
                json.dumps(self.upgrade_history, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            log.error("写入升级日志失败: %s", e)

    def get_upgrade_history(self, limit: int = 20) -> list[dict]:
        """获取最近的升级记录"""
        return self.upgrade_history[-limit:]

    # ============================================================
    # Git 操作（自我升级后自动提交）
    # ============================================================

    def git_commit(self, filepath: str, message: str) -> dict[str, object]:
        """
        将指定文件的修改提交到 Git 仓库。
        自我升级后自动调用，让每次代码修改都有完整的版本记录。
        返回: {"success": bool, "error": str, "commit_hash": str}
        """
        try:
            # 1. git add 指定文件
            add_result = subprocess.run(
                ["git", "add", filepath],
                capture_output=True,
                text=True,
                cwd=str(self.project_root),
                timeout=10,
            )
            if add_result.returncode != 0:
                return {
                    "success": False,
                    "error": f"git add 失败: {add_result.stderr.strip()}",
                    "commit_hash": "",
                }

            # 2. git commit
            commit_msg = f"[AEVA 自我升级] {message}"
            commit_result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                capture_output=True,
                text=True,
                cwd=str(self.project_root),
                timeout=15,
            )
            if commit_result.returncode != 0:
                stderr = commit_result.stderr.strip()
                # "nothing to commit" 不算失败
                if (
                    "nothing to commit" in stderr
                    or "nothing to commit" in commit_result.stdout
                ):
                    return {
                        "success": True,
                        "error": "",
                        "commit_hash": "",
                        "note": "无变更需要提交",
                    }
                return {
                    "success": False,
                    "error": f"git commit 失败: {stderr}",
                    "commit_hash": "",
                }

            # 3. 获取刚刚提交的 commit hash
            log_result = subprocess.run(
                ["git", "log", "-1", "--format=%h"],
                capture_output=True,
                text=True,
                cwd=str(self.project_root),
                timeout=5,
            )
            commit_hash = (
                log_result.stdout.strip() if log_result.returncode == 0 else ""
            )

            log.info("Git 提交成功: %s - %s", commit_hash, commit_msg)
            return {
                "success": True,
                "error": "",
                "commit_hash": commit_hash,
            }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "git 操作超时", "commit_hash": ""}
        except FileNotFoundError:
            return {"success": False, "error": "git 未安装", "commit_hash": ""}
        except Exception as e:
            return {"success": False, "error": str(e), "commit_hash": ""}

    # ============================================================
    # 工具
    # ============================================================

    def _resolve_path(self, filepath: str) -> Path:
        """将相对路径解析为绝对路径"""
        p = Path(filepath)
        if p.is_absolute():
            return p
        return self.project_root / filepath

    def get_own_source(self, module_name: str) -> Optional[str]:
        """
        快捷方法：读取自身某个模块的源代码。
        module_name: 如 "agent_engine", "llm_client", "emotion_system" 等
        """
        path = f"backend/{module_name}.py"
        result = self.read_file(path)
        if result["success"]:
            return str(result["content"])
        return None
