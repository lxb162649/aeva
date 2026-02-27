# logger.py — AEVA 统一日志模块
# 所有模块通过 get_logger(name) 获取 logger 实例
# 日志同时输出到控制台和文件，方便排查问题
#
# 用法：
#   from logger import get_logger
#   log = get_logger("Agent")
#   log.info("自主行为完成")
#   log.warning("精力不足，跳过升级")
#   log.error("LLM 调用失败: %s", err)

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

# ---- 路径配置 ----
LOG_DIR = Path("/home/lxb/桌面/aeva/data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "aeva.log"

# ---- 日志格式 ----
# 控制台：简洁格式，带颜色标签
CONSOLE_FMT = "[%(asctime)s] [%(name)-12s] %(levelname)-5s | %(message)s"
CONSOLE_DATE_FMT = "%H:%M:%S"

# 文件：完整格式，含日期和行号
FILE_FMT = "%(asctime)s | %(name)-12s | %(levelname)-7s | %(filename)s:%(lineno)d | %(message)s"
FILE_DATE_FMT = "%Y-%m-%d %H:%M:%S"

# ---- 全局配置（只执行一次） ----
_initialized = False


def _setup_root() -> None:
    """初始化根 logger 配置"""
    global _initialized
    if _initialized:
        return
    _initialized = True

    root = logging.getLogger("AEVA")
    root.setLevel(logging.DEBUG)

    # 避免重复添加 handler
    if root.handlers:
        return

    # 1. 控制台 handler — INFO 及以上
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(CONSOLE_FMT, datefmt=CONSOLE_DATE_FMT))
    root.addHandler(console)

    # 2. 文件 handler — DEBUG 及以上，轮转 5MB × 3 个备份
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(FILE_FMT, datefmt=FILE_DATE_FMT))
    root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    获取一个命名 logger。
    所有 logger 都是 AEVA 根 logger 的子 logger，共享相同的 handler。

    参数:
        name: 模块标识，如 "Server", "Agent", "LLM", "FileAccess"

    示例:
        log = get_logger("Agent")
        log.info("自主行为周期完成，执行了 %d 个动作", len(actions))
    """
    _setup_root()
    return logging.getLogger(f"AEVA.{name}")
