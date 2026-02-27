# server.py — AEVA FastAPI 服务 v2
# 整合 LLM 对话、情感系统、分层记忆、增强自主行为
# 提供 REST API、WebSocket 聊天、静态文件服务

import asyncio
import json
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from models import DataStore
from memory_system import MemorySystem
from emotion_system import EmotionSystem
from agent_engine import AgentEngine, ACTIVITIES
from time_engine import TimeEngine
from llm_client import LLMClient

# ---- 路径配置 ----
BASE_DIR = Path("/home/lxb/桌面/aeva")
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"

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
            print(f"[AutoLoop] 自主行为异常: {e}")


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

    print(
        f"[AEVA] 服务已启动 | LLM: {'已启用' if llm.enabled else '未配置'} | 端口: 19260"
    )

    yield

    # 关闭
    engine.stop()
    if autonomous_task:
        autonomous_task.cancel()
    print("[AEVA] 服务已停止")


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


# ============================================================
# WebSocket 聊天
# ============================================================


@app.websocket("/ws/chat")
async def chat(ws: WebSocket) -> None:
    """WebSocket 聊天端点：接收用户消息，返回 AEVA 回复"""
    await ws.accept()
    try:
        while True:
            data = await ws.receive_text()
            msg: dict[str, str] = json.loads(data)
            user_text = msg.get("text", "").strip()

            if not user_text:
                continue

            # 加载状态和对话历史
            echo = store.load_echo()
            chat_history = store.get_chat_history_for_llm(limit=40)

            # 记录用户消息到对话历史
            store.add_chat_message("user", user_text)

            # 更新活跃时间
            echo["last_active"] = datetime.now().isoformat()

            # 聊天消耗精力
            current_energy = float(str(echo.get("energy", 50)))
            echo["energy"] = max(0.0, current_energy - 1.5)
            store.save_echo(echo)

            # 通过 AgentEngine 处理消息（含 LLM 调用）
            reply = await agent.handle_user_message(user_text, echo, chat_history)

            # 记录 AEVA 回复到对话历史
            store.add_chat_message("assistant", reply)

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
        pass
    except Exception as e:
        print(f"[WS] 异常: {e}")


# ---- 挂载前端静态文件 ----
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


# ---- 主入口 ----
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=19260)
