# server.py — AEVA FastAPI 服务 v2
# 整合 LLM 对话、情感系统、分层记忆、增强自主行为
# 提供 REST API、WebSocket 聊天、静态文件服务

# 加载 .env 环境变量（必须在其他模块导入之前）
from dotenv import load_dotenv
from pathlib import Path as _Path

load_dotenv(_Path(__file__).resolve().parent.parent / ".env")

import asyncio
import json
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.staticfiles import StaticFiles

from models import DataStore
from memory_system import MemorySystem
from emotion_system import EmotionSystem
from agent_engine import AgentEngine, ACTIVITIES
from time_engine import TimeEngine
from llm_client import LLMClient
from file_access import FileAccess
from logger import get_logger

log = get_logger("Server")

# ---- 路径配置 ----
BASE_DIR = Path("/home/lxb/桌面/aeva")
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"
UPLOADS_DIR = DATA_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# ---- 字数限制 ----
MAX_INPUT_CHARS = 20000
MAX_OUTPUT_CHARS = 20000

# ---- 初始化各模块 ----
store = DataStore(DATA_DIR)
memory = MemorySystem(store)
emotion = EmotionSystem(store)
llm = LLMClient()
agent = AgentEngine(store, memory, emotion, llm)
engine = TimeEngine(store, emotion)

# ---- 自主行为定时任务 ----
autonomous_task: asyncio.Task | None = None  # type: ignore[type-arg]


async def autonomous_loop() -> None:
    """每 3 分钟执行一次自主行为"""
    while True:
        await asyncio.sleep(180)
        try:
            await agent.run_autonomous_cycle()
        except Exception as e:
            log.error("自主行为异常: %s", e)


# ---- FastAPI 生命周期 ----


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """启动和关闭时的生命周期管理"""
    global autonomous_task

    # 启动时间引擎
    asyncio.create_task(engine.start())

    # 启动自主行为循环
    autonomous_task = asyncio.create_task(autonomous_loop())

    # 检测离线时间，超过1分钟则触发一次自主行为
    echo = store.load_echo()
    last_active_str = str(echo.get("last_active", datetime.now().isoformat()))
    try:
        last = datetime.fromisoformat(last_active_str)
        offline = (datetime.now() - last).total_seconds()
    except (ValueError, TypeError):
        offline = 0

    if offline > 60:
        echo["_offline_seconds"] = offline
        store.save_echo(echo)
        await agent.run_autonomous_cycle()

    log.info(
        "服务已启动 | LLM: %s | 端口: 19260", "已启用" if llm.enabled else "未配置"
    )

    yield

    # 关闭
    engine.stop()
    if autonomous_task:
        autonomous_task.cancel()
    log.info("服务已停止")


# ---- FastAPI 应用 ----
app = FastAPI(title="AEVA - 数字生命", lifespan=lifespan)


# ============================================================
# REST API 端点
# ============================================================


@app.get("/api/status")
async def get_status() -> dict[str, object]:
    """获取 AEVA 完整状态（含亲密度、活动、情感信息）"""
    echo = store.load_echo()

    # 计算可读时长
    total_seconds = float(str(echo.get("total_life_seconds", 0)))
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    echo["life_display"] = f"{hours}小时{minutes}分钟"

    # 亲密度信息
    intimacy_info = emotion.get_intimacy_level(echo)
    echo["intimacy_info"] = intimacy_info

    # 心情显示信息
    mood = str(echo.get("mood", "calm"))
    mood_display = emotion.get_mood_display(mood)
    echo["mood_display"] = mood_display

    # 活动显示信息
    activity = str(echo.get("activity", "waiting"))
    activity_info = ACTIVITIES.get(activity, ACTIVITIES.get("waiting", {}))
    echo["activity_display"] = {
        "zh": activity_info.get("zh", "等待中"),
        "emoji": activity_info.get("emoji", "⏳"),
    }

    # 记忆统计
    echo["memory_stats"] = memory.get_memory_stats()

    return echo


@app.get("/api/memories")
async def get_memories() -> dict[str, object]:
    """获取记忆列表（含分层信息和统计）"""
    all_memories = store.get_memories()
    stats = memory.get_memory_stats()

    # 按层级分组
    layers: dict[str, list[dict[str, object]]] = {
        "core": [],
        "long_term": [],
        "short_term": [],
    }
    for m in all_memories:
        layer = str(m.get("layer", "short_term"))
        if layer in layers:
            layers[layer].append(m)

    return {
        "memories": all_memories,
        "layers": layers,
        "stats": stats,
    }


@app.get("/api/logs")
async def get_logs(limit: int = 50) -> dict[str, object]:
    """获取生命日志（支持分页）"""
    all_logs = store.get_life_logs()
    return {
        "logs": all_logs[-limit:],
        "total": len(all_logs),
    }


@app.get("/api/tasks")
async def get_tasks() -> list[dict[str, object]]:
    """获取全部任务列表"""
    return store.get_all_tasks()


@app.get("/api/emotions")
async def get_emotions() -> dict[str, object]:
    """获取情感状态详情"""
    echo = store.load_echo()
    return {
        "mood": str(echo.get("mood", "calm")),
        "mood_display": emotion.get_mood_display(str(echo.get("mood", "calm"))),
        "energy": float(str(echo.get("energy", 50))),
        "intimacy": emotion.get_intimacy_level(echo),
        "recent_emotions": emotion.get_recent_emotions(echo, limit=10),
        "emotion_tendency": emotion.get_emotion_tendency(echo),
    }


@app.get("/api/upgrades")
async def get_upgrades(limit: int = 20) -> dict[str, object]:
    """获取 AEVA 的自我升级历史（代码自改）"""
    fa = FileAccess()
    history = fa.get_upgrade_history(limit=limit)
    return {
        "upgrades": history,
        "total": len(fa.upgrade_history),
    }


# ============================================================
# 文件上传 API
# ============================================================

ALLOWED_EXTENSIONS = {
    # 图片
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".webp",
    ".svg",
    # 数据文件
    ".csv",
    ".json",
    ".txt",
    ".xlsx",
    ".xls",
    ".pdf",
    ".doc",
    ".docx",
    ".xml",
    ".yaml",
    ".yml",
    ".md",
    ".log",
    ".tsv",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@app.post("/api/upload")
async def upload_files(files: list[UploadFile] = File(...)) -> dict[str, object]:
    """上传文件（图片、数据文件），返回文件信息列表"""
    import uuid

    uploaded: list[dict[str, str]] = []
    for file in files:
        # 检查扩展名
        ext = Path(file.filename or "unknown").suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            continue

        # 读取文件内容
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            continue

        # 生成唯一文件名
        unique_name = f"{uuid.uuid4().hex[:12]}_{file.filename}"
        save_path = UPLOADS_DIR / unique_name
        save_path.write_bytes(content)

        # 判断文件类型
        is_image = ext in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"}
        file_type = "image" if is_image else "data"

        # 对于文本类数据文件，提取文本内容摘要
        text_content = ""
        if file_type == "data" and ext in {
            ".csv",
            ".json",
            ".txt",
            ".md",
            ".log",
            ".xml",
            ".yaml",
            ".yml",
            ".tsv",
        }:
            try:
                text_content = content.decode("utf-8", errors="ignore")[:5000]
            except Exception:
                text_content = ""

        uploaded.append(
            {
                "filename": file.filename or "unknown",
                "saved_name": unique_name,
                "type": file_type,
                "ext": ext,
                "size": str(len(content)),
                "text_content": text_content,
            }
        )

    return {"files": uploaded, "count": len(uploaded)}


# ============================================================
# 斜杠命令列表 API
# ============================================================


@app.get("/api/slash-commands")
async def get_slash_commands() -> dict[str, object]:
    """返回所有可用的斜杠命令定义，供前端自动补全使用"""
    return {"commands": agent.SLASH_COMMANDS}


# ============================================================
# WebSocket 聊天
# ============================================================


@app.websocket("/ws/chat")
async def chat(ws: WebSocket) -> None:
    """WebSocket 聊天端点：接收用户消息，返回 AEVA 回复（支持文件附件和斜杠命令）"""
    await ws.accept()
    try:
        while True:
            data = await ws.receive_text()
            msg: dict[str, object] = json.loads(data)
            user_text = str(msg.get("text", "")).strip()
            files_info: list[dict[str, str]] = msg.get("files", [])  # type: ignore[assignment]

            if not user_text and not files_info:
                continue

            # 输入字数限制
            if len(user_text) > MAX_INPUT_CHARS:
                user_text = user_text[:MAX_INPUT_CHARS]

            # ---- 斜杠命令拦截 ----
            if agent.is_slash_command(user_text):
                echo = store.load_echo()
                log.info("[斜杠命令] %s", user_text[:200])

                # 记录命令到聊天历史
                store.add_chat_message("user", user_text)

                # 执行命令，传入 ws.send_text 以支持中间进度消息
                reply = await agent.handle_slash_command(
                    user_text, echo, ws_send=ws.send_text
                )

                # 输出限制
                if len(reply) > MAX_OUTPUT_CHARS:
                    reply = reply[:MAX_OUTPUT_CHARS]

                store.add_chat_message("assistant", reply)
                log.info("[命令结果] %s", reply[:200])

                echo = store.load_echo()
                intimacy_info = emotion.get_intimacy_level(echo)

                await ws.send_text(
                    json.dumps(
                        {
                            "type": "reply",
                            "text": reply,
                            "mood": echo.get("mood", "calm"),
                            "mood_display": emotion.get_mood_display(
                                str(echo.get("mood", "calm"))
                            ),
                            "energy": echo.get("energy", 0),
                            "intimacy": intimacy_info,
                        },
                        ensure_ascii=False,
                    )
                )
                continue

            # ---- 普通消息处理 ----
            # 如果有文件附件，将文件信息附加到消息中
            file_context = ""
            if files_info:
                file_parts: list[str] = []
                for f in files_info:
                    fname = f.get("filename", "")
                    ftype = f.get("type", "")
                    if ftype == "image":
                        file_parts.append(f"[用户上传了图片: {fname}]")
                    else:
                        text_content = f.get("text_content", "")
                        if text_content:
                            # 截取文件内容摘要
                            preview = text_content[:3000]
                            file_parts.append(
                                f"[用户上传了文件 {fname}，内容如下：\n{preview}]"
                            )
                        else:
                            file_parts.append(f"[用户上传了文件: {fname}]")
                file_context = "\n".join(file_parts)

            # 组合最终消息
            full_text = user_text
            if file_context:
                full_text = (
                    f"{user_text}\n{file_context}" if user_text else file_context
                )

            # 加载状态和对话历史
            echo = store.load_echo()
            chat_history = store.get_chat_history_for_llm(limit=40)

            # 记录用户消息到对话历史
            store.add_chat_message("user", full_text)
            log.info("[用户] %s", full_text[:200])

            # 更新活跃时间
            echo["last_active"] = datetime.now().isoformat()

            # 聊天消耗精力
            current_energy = float(str(echo.get("energy", 50)))
            echo["energy"] = max(0.0, current_energy - 1.5)
            store.save_echo(echo)

            # 通过 AgentEngine 处理消息（含 LLM 调用）
            reply = await agent.handle_user_message(full_text, echo, chat_history)

            # 输出字数限制
            if len(reply) > MAX_OUTPUT_CHARS:
                reply = reply[:MAX_OUTPUT_CHARS]

            # 记录 AEVA 回复到对话历史
            store.add_chat_message("assistant", reply)
            log.info("[AEVA] %s", reply[:200])

            # 重新加载最新状态（handle_user_message 可能更新了状态）
            echo = store.load_echo()
            intimacy_info = emotion.get_intimacy_level(echo)

            await ws.send_text(
                json.dumps(
                    {
                        "type": "reply",
                        "text": reply,
                        "mood": echo.get("mood", "calm"),
                        "mood_display": emotion.get_mood_display(
                            str(echo.get("mood", "calm"))
                        ),
                        "energy": echo.get("energy", 0),
                        "intimacy": intimacy_info,
                    },
                    ensure_ascii=False,
                )
            )

    except WebSocketDisconnect:
        log.debug("WebSocket 客户端断开")
    except Exception as e:
        log.error("WebSocket 异常: %s", e)


# ---- 挂载前端静态文件 ----
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


# ---- 主入口 ----
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=19260, access_log=False)
