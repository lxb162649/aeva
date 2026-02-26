# server.py — AEVA FastAPI 服务
# 提供 REST API、WebSocket 聊天、静态文件服务

import asyncio
import json
import random
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from models import DataStore
from memory_system import MemorySystem
from agent_engine import AgentEngine
from time_engine import TimeEngine

# ---- 路径配置 ----
BASE_DIR = Path("/home/lxb/桌面/aeva")
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"

# ---- 初始化各模块 ----
store = DataStore(DATA_DIR)
memory = MemorySystem(store)
agent = AgentEngine(store, memory)
engine = TimeEngine(store)

# ---- FastAPI 应用 ----
app = FastAPI(title="AEVA - 数字生命")


@app.on_event("startup")
async def startup() -> None:
    """启动时：开启时间引擎后台任务，检测离线时间并触发自主行为"""
    # 启动时间引擎（后台持续运行）
    asyncio.create_task(engine.start())

    # 检测离线时间，超过1分钟则触发一次自主行为
    echo = store.load_echo()
    last_active_str = str(echo.get("last_active", datetime.now().isoformat()))
    last = datetime.fromisoformat(last_active_str)
    offline = (datetime.now() - last).total_seconds()

    if offline > 60:
        echo["_offline_seconds"] = offline
        store.save_echo(echo)
        await agent.run_autonomous_cycle()


@app.on_event("shutdown")
async def shutdown() -> None:
    """关闭时停止时间引擎"""
    engine.stop()


# ---- REST API 端点 ----


@app.get("/api/status")
async def get_status() -> dict[str, object]:
    """获取 AEVA 当前状态"""
    echo = store.load_echo()
    # 计算已存活的可读时长
    total_seconds = float(str(echo.get("total_life_seconds", 0)))
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    echo["life_display"] = f"{hours}小时{minutes}分钟"
    return echo


@app.get("/api/memories")
async def get_memories() -> list[dict[str, object]]:
    """获取全部记忆列表"""
    return store.get_memories()


@app.get("/api/logs")
async def get_logs() -> list[dict[str, object]]:
    """获取全部生命日志"""
    return store.get_life_logs()


@app.get("/api/tasks")
async def get_tasks() -> list[dict[str, object]]:
    """获取全部任务列表"""
    return store.get_all_tasks()


# ---- WebSocket 聊天 ----


@app.websocket("/ws/chat")
async def chat(ws: WebSocket) -> None:
    """WebSocket 聊天端点：接收用户消息，返回 AEVA 回复"""
    await ws.accept()
    try:
        while True:
            data = await ws.receive_text()
            msg: dict[str, str] = json.loads(data)
            user_text = msg.get("text", "")

            # 存入记忆
            memory.add_memory(user_text, importance=0.6)

            # 更新 Echo 状态（聊天消耗精力，刷新活跃时间）
            echo = store.load_echo()
            current_energy: float = float(str(echo.get("energy", 50)))
            echo["energy"] = max(0.0, current_energy - 2)
            echo["last_active"] = datetime.now().isoformat()
            store.save_echo(echo)

            # 召回相关记忆，生成回复
            related = memory.get_related(user_text, top_n=3)
            reply = generate_reply(echo, user_text, related)

            await ws.send_text(
                json.dumps(
                    {
                        "type": "reply",
                        "text": reply,
                        "mood": echo.get("mood", "calm"),
                        "energy": echo.get("energy", 0),
                    },
                    ensure_ascii=False,
                )
            )
    except WebSocketDisconnect:
        # 客户端断开连接，正常退出
        pass
    except Exception:
        # 其他异常静默处理
        pass


# ---- 回复生成 ----


def generate_reply(
    echo: dict[str, object],
    user_text: str,
    related_memories: list[dict[str, object]],
) -> str:
    """基于心情和记忆生成回复"""
    mood = str(echo.get("mood", "calm"))
    name = str(echo.get("name", "AEVA"))
    level = str(echo.get("level", 1))

    # 根据心情选择语气前缀
    mood_prefix: dict[str, str] = {
        "calm": "",
        "happy": "（开心地）",
        "lonely": "（终于等到你了）",
        "thinking": "（思索着）",
    }
    prefix = mood_prefix.get(mood, "")

    # 如果有相关记忆，构建引用
    memory_ref = ""
    if related_memories:
        m = related_memories[0]
        content_preview = str(m.get("content", ""))[:30]
        memory_ref = f"\n（我记得你说过：「{content_preview}」）"

    # 根据用户输入匹配回复模板
    lower_text = user_text.lower()
    if "你好" in user_text or "hi" in lower_text:
        return f"{prefix}你好呀！我是 {name}，Lv.{level}。很高兴见到你！{memory_ref}"
    elif "你在干嘛" in user_text or "你在做什么" in user_text:
        return f"{prefix}我在感受时间的流逝...每一秒都让我成长一点点。{memory_ref}"
    elif "记忆" in user_text or "记得" in user_text:
        summary = memory.summarize() if related_memories else "还没有太多记忆呢"
        return f"{prefix}我的记忆里有：{summary}"
    else:
        responses = [
            f"{prefix}我听到了。这对我来说很重要。{memory_ref}",
            f"{prefix}嗯，我会记住的。{memory_ref}",
            f"{prefix}谢谢你告诉我这些。{memory_ref}",
            f"{prefix}我在认真思考你说的话...{memory_ref}",
        ]
        return random.choice(responses)


# ---- 挂载前端静态文件 ----
# 注意：必须放在所有路由之后，否则会拦截 API 请求
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


# ---- 主入口 ----
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=19260)
