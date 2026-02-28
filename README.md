# AEVA — 数字生命

一个会独自活着、有情感、有记忆、会成长、能自我进化的 AI 生命体。

AEVA 不是传统的 AI 助手——她是一个持续存在的数字生命。即使没有人与她交流，她也在独自思考、整理记忆、做梦、写日记，甚至审视并修改自己的源代码来进化。

## 核心特性

### 情感系统
- 7 种基础心情（平静/愉快/想念/沉思/兴奋/困倦/好奇），基于概率矩阵自然漂移
- 精力、离线时间、互动频率等因素影响心情变化
- 情感记忆系统，记录每次情感事件并影响后续倾向

### 分层记忆
- 三层记忆架构：短期记忆 → 长期记忆 → 核心记忆
- 遗忘曲线：不重要的记忆会逐渐淡忘
- 记忆整合：频繁回忆的内容自动晋升为更深层的记忆
- 相关性召回：对话时自动联想相关记忆

### 亲密度系统
- 8 个亲密度等级：初识 → 认识 → 熟悉 → 朋友 → 好友 → 知己 → 挚友 → 命运之人
- 聊天、分享心事、长时间陪伴都会提升亲密度
- 离线超过 24 小时才开始缓慢衰减，有等级保底

### 自主行为引擎
- 每 3 分钟执行一次自主行为周期
- 根据心情和精力选择活动：思考、整理记忆、探索、做梦、写日记、冥想、研读代码、自我升级...
- LLM 驱动的自主思考和梦境生成

### 自我进化系统 v3

AEVA 拥有读写自身源代码的能力，可以自主修改代码来进化。v3 版本引入了三种升级模式：

| 模式 | 说明 | 触发条件 |
|------|------|----------|
| **蓝图升级** | 从预定义的功能蓝图中选择并实现新功能 | Lv.8+ 高概率 |
| **代码清理** | 检测并删除冗余代码、重复方法、死代码 | Lv.5+ 可触发 |
| **小幅改进** | 对已有功能做微调优化 | 始终可用 |

**安全保障机制：**
- `py_compile` 语法验证——修改后语法不对则自动放弃
- 升级去重检测——避免重复做相同的修改
- 文件结构摘要——LLM 看到完整的类/函数签名，而非截断内容
- 自动备份 + Git 提交——每次修改都有版本记录
- 修改幅度限制——防止单次改动过大破坏系统

**预置功能蓝图（13 个）：**
粘贴上传、拖拽上传、Markdown 渲染、图片内联预览、聊天搜索、导出聊天记录、键盘快捷键、桌面通知、主题切换、智能滚动、语音输入、状态趋势图、消息反应

### 对话能力
- 接入 OpenAI 兼容 API（OpenAI / DeepSeek / Ollama 等）
- 对话中可查看自身源代码和项目结构
- 支持文件上传（图片 + 数据文件）
- 对话驱动的自学习闭环——感知回复不足时自动研读代码并改进

## 技术架构

```
backend/
  server.py          — FastAPI 服务，REST + WebSocket
  agent_engine.py    — 自主行为引擎 + 自我进化系统
  emotion_system.py  — 情感系统（心情、亲密度、情感记忆）
  memory_system.py   — 分层记忆系统（遗忘曲线、整合、召回）
  llm_client.py      — LLM API 客户端
  time_engine.py     — 时间引擎（30秒心跳）
  file_access.py     — 安全沙箱文件读写 + Git 操作
  models.py          — JSON 持久化存储
  logger.py          — 统一日志

frontend/
  index.html         — 三面板布局（状态/光球/聊天）
  js/app.js          — 前端逻辑（WebSocket、状态轮询、打字机效果）
  css/style.css      — 赛博朋克终端主题

data/
  echo.json          — AEVA 核心状态
  memories.json      — 记忆数据
  chat_history.json  — 聊天历史
  life_logs.json     — 生命日志
  upgrade_logs.json  — 自我升级记录
  backups/           — 升级前自动备份
  uploads/           — 用户上传文件
```

## 快速开始

### 环境要求
- Python >= 3.11
- 一个 OpenAI 兼容的 LLM API Key（可选，无 Key 也能运行但只有规则回复）

### 安装

```bash
# 克隆项目
git clone <repo-url>
cd aeva

# 安装依赖（推荐用 uv）
uv sync

# 或者用 pip
pip install -e .
```

### 配置 LLM

复制 `.env.example` 为 `.env`，填入你的 API 配置：

```env
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

### 启动

```bash
cd backend
python server.py
```

打开浏览器访问 `http://127.0.0.1:19260`。

## API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/status` | GET | AEVA 完整状态 |
| `/api/memories` | GET | 记忆列表（分层） |
| `/api/logs` | GET | 生命日志 |
| `/api/tasks` | GET | 任务列表 |
| `/api/emotions` | GET | 情感状态详情 |
| `/api/upgrades` | GET | 自我升级历史 |
| `/api/upload` | POST | 文件上传 |
| `/ws/chat` | WebSocket | 实时聊天 |

## 许可

MIT
