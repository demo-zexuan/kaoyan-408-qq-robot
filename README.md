# 考研408 QQ Robot

<div align="center">

**基于 LangGraph 的智能对话 QQ 机器人**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![NoneBot2](https://img.shields.io/badge/NoneBot2-2.3.0+-green.svg)](https://nonebot.dev/)
[![LangGraph](https://img.shields.io/badge/LangGraph-latest-orange.svg)](https://github.com/langchain-ai/langgraph)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[功能特性](#功能特性) • [快速开始](#快速开始) • [部署指南](#部署指南) • [项目结构](#项目结构)

</div>

---

## 目录

- [功能特性](#功能特性)
- [快速开始](#快速开始)
- [系统架构](#系统架构)
- [核心模块](#核心模块)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [开发指南](#开发指南)
- [配置说明](#配置说明)
- [常见问题](#常见问题)

---

## 功能特性

| 功能模块 | 描述 |
|---------|------|
| **上下文管理** | 支持动态创建、更新、删除对话上下文，支持多轮对话和多用户协作 |
| **自然语言理解** | 集成 LangGraph，实现智能对话状态管理和流程控制 |
| **意图识别** | 支持闲聊、天气查询、角色扮演等多种意图类型，可扩展自定义意图 |
| **Token 控制** | 实现 Token 分配、使用监控，防止恶意消耗系统资源 |
| **用户封禁** | 支持对异常用户进行临时/永久封禁处理 |

### 意图类型

```python
class IntentType(Enum):
    CHAT = "chat"              # 普通闲聊
    WEATHER = "weather"        # 天气查询
    ROLE_PLAY = "role_play"   # 角色扮演
    CONTEXT_CREATE = "context_create"    # 创建上下文
    CONTEXT_JOIN = "context_join"        # 加入上下文
    CONTEXT_LEAVE = "context_leave"      # 离开上下文
    CONTEXT_END = "context_end"          # 结束上下文
    USER_BAN = "user_ban"      # 用户封禁
```

---

## 快速开始

### 环境要求

- Python 3.11+
- Redis 6.0+
- NapCat (最新版)

### 安装

```bash
# 克隆项目
git clone https://github.com/yourusername/kaoyan-408-qq-robot.git
cd kaoyan-408-qq-robot

# 安装依赖
pip install uv
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件填入必要配置
```

### 启动

```bash
# 启动 Redis
docker-compose up -d redis

# 启动机器人
uv run python src/bot.py
```

详细部署说明请参考 [部署指南](#部署指南)。

---

## 系统架构

### 架构概览

```
┌─────────────────────────────────────────────────────────────────────┐
│                          客户端层                                    │
│  ┌──────────────┐                   ┌──────────────┐               │
│  │  QQ Client   │ ←───────────────→ │    NapCat    │               │
│  └──────────────┘  QQ 协议          └──────────────┘               │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│                          框架层                                      │
│                        ┌──────────────┐                             │
│                        │  NoneBot2    │                             │
│                        └──────────────┘                             │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│                       业务逻辑层                                      │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ 消息处理                    │ │
│  │  ┌──────────────┐  ┌──────────────┐                          │ │
│  │  │ MessageRouter│  │IntentRecognizer│                         │ │
│  │  └──────────────┘  └──────────────┘                          │ │
│  ├───────────────────────────────────────────────────────────────┤ │
│  │ 对话引擎                                                            │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │ │
│  │  │ContextManager│  │LangGraphMgr  │  │RolePlayModule│        │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘        │ │
│  ├───────────────────────────────────────────────────────────────┤ │
│  │ 用户管理                                                            │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │ │
│  │  │  UserManager │  │TokenController│ │  BanManager  │        │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘        │ │
│  ├───────────────────────────────────────────────────────────────┤ │
│  │ 工具服务                                                            │ │
│  │  ┌──────────────┐  ┌──────────────┐                          │ │
│  │  │ WeatherService│  │  ChatService │                          │ │
│  │  └──────────────┘  └──────────────┘                          │ │
│  └───────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
            ↓                               ↓
┌───────────────────────┐     ┌───────────────────────────┐
│  存储层                │     │  外部服务                  │
│  ┌───────┐  ┌───────┐ │     │  ┌───────┐  ┌───────┐    │
│  │ Redis │  │ DB    │ │     │  │  LLM  │  │Weather │    │
│  └───────┘  └───────┘ │     │  └───────┘  └───────┘    │
└───────────────────────┘     └───────────────────────────┘
```

### 消息处理流程

```
┌──────┐     ┌──────┐     ┌───────┐     ┌──────┐     ┌──────┐     ┌──────┐
│ 用户 │ ──→ │ QQ   │ ──→ │NoneBot│ ──→ │Router│ ──→ │Intent│ ──→ │Handler│
└──────┘     └──────┘     └───────┘     └──────┘     └──────┘     └──────┘
                                                          ↓
                                          ┌───────────────────────────────┐
                                          │  根据意图类型路由               │
                                          ├───────────────────────────────┤
                                          │ 命令格式 → 命令处理器           │
                                          │ 闲聊意图 → ChatHandler         │
                                          │ 天气查询 → WeatherHandler      │
                                          │ 角色扮演 → RolePlayHandler     │
                                          │ 上下文操作 → ContextHandler    │
                                          │ 未知意图 → DefaultHandler      │
                                          └───────────────────────────────┘
```

### 意图识别与路由

```
                    收到用户消息
                         ↓
                    提取消息内容
                         ↓
                    预处理消息
                         ↓
              ┌──────────────────────┐
              │  是否命中命令？       │
              └──────────────────────┘
               ↙                    ↘
             是                      否
             ↓                        ↓
        命令路由                意图识别
             ↓                        ↓
        执行命令         ┌─────────────────────┐
                        │  识别到的意图？      │
                        └─────────────────────┘
                         ↙       ↘       ↘      ↘
                       闲聊      天气    角色扮演  上下文
                        ↓        ↓       ↓        ↓
                    闲聊服务  天气服务  角色管理  上下文管理
                         ↙        ↓       ↘        ↘
                         └──────────────────────────┘
                                     ↓
                                返回响应
```

---

## 核心模块

### 模块职责

| 模块 | 职责 |
|-----|------|
| **MessageRouter** | 消息入口，负责消息分发、路由、权限检查 |
| **IntentRecognizer** | 意图识别，决定消息流向哪个处理器 |
| **ContextManager** | 管理对话上下文的生命周期 |
| **LangGraphManager** | LangGraph 图的编译、执行、状态管理 |
| **RolePlayModule** | 管理角色扮演场景、角色定义 |
| **UserManager** | 用户信息管理、认证 |
| **TokenController** | Token 分配、监控、限流 |
| **BanManager** | 用户封禁策略执行 |

### 上下文管理

```
┌─────────────────────────────────────────────────────────────┐
│                     上下文生命周期                            │
└─────────────────────────────────────────────────────────────┘

     创建 ──→ 活跃 ──→ 暂停
       │         │         │
       │         │         └──→ 活跃 (恢复)
       │         │
       │         ├──→ 过期 ──→ 归档 ──→ 删除
       │         │                ↘
       │         └────────────────→ 删除
       │
       └──────────────────→ 删除 (用户主动结束)
```

### 上下文数据结构

```python
class Context(BaseModel):
    """对话上下文"""
    # 基础信息
    context_id: str           # 上下文唯一标识
    type: ContextType         # 上下文类型 (PRIVATE/GROUP/MULTI_USER/ROLE_PLAY)

    # 参与者
    creator_id: str           # 创建者ID
    participants: List[str]   # 参与者列表

    # 消息历史
    messages: List[ChatMessage]
    max_messages: int = 100   # 最大消息数

    # 状态
    status: ContextStatus     # ACTIVE/PAUSED/EXPIRED/ARCHIVED/DELETED
    state: Optional[RobotState]

    # 元数据
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime]
```

### LangGraph 对话引擎

```
┌─────────────────────────────────────────────────────────────────────┐
│                       主对话图 (MainGraph)                            │
└─────────────────────────────────────────────────────────────────────┘

     输入处理 ──→ 意图路由 ──→ ┌─────────────────────────┐
                                      │ 根据意图路由        │
                                      ├─────────────────────┤
                                      │ 闲聊 → 闲聊子图     │
                                      │ 天气 → 天气子图     │
                                      │ 角色 → 角色子图     │
                                      └─────────────────────┘
                                            ↓           ↓           ↓
                                    ┌───────────┐ ┌──────────┐ ┌───────────┐
                                    │ 闲聊子图   │ │天气子图   │ │角色子图    │
                                    │ - 加载历史│ │ - 解析地点│ │ - 加载角色 │
                                    │ - 生成回复│ │ - 调用API │ │ - 应用约束 │
                                    │ - 优化输出│ │ - 格式化  │ │ - 生成回复 │
                                    └───────────┘ └──────────┘ └───────────┘
                                            ↓           ↓           ↓
                                    ┌───────────────────────────────────────┐
                                    │            响应生成                    │
                                    └───────────────────────────────────────┘
                                                ↓
                                    ┌───────────────────────────────────────┐
                                    │            上下文更新                  │
                                    └───────────────────────────────────────┘
```

### LangGraph 状态定义

```python
class RobotState(BaseModel):
    """机器人对话状态"""
    # 消息相关
    messages: List[str] = Field(default_factory=list)
    current_input: str = ""
    response: str = ""

    # 上下文相关
    context_id: str = ""
    context_type: str = ""
    participants: List[str] = Field(default_factory=list)

    # 意图相关
    intent: str = ""
    intent_confidence: float = 0.0
    extracted_entities: Dict[str, Any] = Field(default_factory=dict)

    # 角色扮演相关
    role_play_mode: bool = False
    current_role: str = ""
    role_settings: Dict[str, Any] = Field(default_factory=dict)

    # 元数据
    step_count: int = 0
    token_usage: int = 0
    last_action: str = ""
```

---

## 技术栈

| 组件 | 技术选型 | 说明 |
|-----|---------|------|
| **QQ 框架** | NoneBot2 | 异步机器人框架 |
| **QQ 客户端** | NapCat | NTQQ 实现 |
| **对话引擎** | LangGraph | 状态图对话管理 |
| **LLM 框架** | LangChain | LLM 应用框架 |
| **数据验证** | Pydantic | 数据模型与验证 |
| **缓存** | Redis | 上下文/Token 缓存 |
| **数据库** | SQLite/PostgreSQL | 持久化存储 |
| **异步运行时** | asyncio | 异步任务处理 |

---

## 项目结构

```
kaoyan-408-qq-robot/
├── .env                        # 环境变量配置
├── .env.dev                    # 开发环境配置
├── pyproject.toml              # 项目配置
├── docker-compose.yml          # Docker 服务配置
├── README.md                   # 本文档
├── DEPLOYMENT.md               # 部署指南
│
├── resource/                   # 资源文件
│   ├── roles/                  # 角色配置目录
│   ├── prompts/                # 提示词模板目录
│   └── knowledge/              # 知识库目录
│
├── data/                       # 数据目录
│   └── db/                     # 数据库文件目录
│
├── logs/                       # 日志目录
│
├── tests/                      # 测试目录
│   ├── unit/                   # 单元测试 (109 tests)
│   └── integration/            # 集成测试 (13 tests)
│
└── src/
    ├── bot.py                  # NoneBot 入口
    │
    ├── core/                   # 核心模块
    │   ├── router.py           # 消息路由器
    │   ├── intent.py           # 意图识别器
    │   ├── context.py          # 上下文管理器
    │   ├── langgraph.py        # LangGraph 管理器
    │   └── state.py            # 状态定义
    │
    ├── modules/                # 功能模块
    │   ├── chat.py             # 闲聊模块
    │   ├── weather.py          # 天气模块
    │   ├── role_play.py        # 角色扮演模块
    │   └── context_cmd.py      # 上下文命令
    │
    ├── managers/               # 管理器
    │   ├── user.py             # 用户管理器
    │   ├── token.py            # Token 控制器
    │   └── ban.py              # 封禁管理器
    │
    ├── services/               # 服务层
    │   └── llm_service.py      # LLM 服务
    │
    ├── service/                # 其他服务
    │   └── weather_service.py  # 天气服务
    │
    ├── storage/                # 存储层
    │   ├── database.py         # 数据库操作
    │   ├── cache.py            # 缓存操作
    │   ├── models.py           # Pydantic 数据模型
    │   └── orm_models.py       # SQLAlchemy ORM 模型
    │
    ├── plugins/                # NoneBot 插件
    │   └── llm-endpoint/
    │       └── __init__.py     # 插件入口
    │
    └── utils/                  # 工具函数
        ├── config.py           # 配置加载
        ├── logger.py           # 日志
        └── helpers.py          # 辅助函数
```

---

## 开发指南

### 运行测试

```bash
# 单元测试
uv run pytest tests/unit/ -v

# 集成测试
uv run pytest tests/integration/ -v

# 所有测试 (共 122+ 测试用例)
uv run pytest tests/ -v

# 带覆盖率报告
uv run pytest tests/ --cov=src --cov-report=html
```

### 代码检查

```bash
# 类型检查
uv run mypy src/

# 代码格式化
uv run black src/
uv run isort src/
```

### 添加新意图

1. 在 `IntentType` 枚举中添加新意图
2. 在 `intent.py` 中添加识别逻辑
3. 创建对应的处理器模块
4. 在路由器中注册新路由

### 添加新角色

1. 在 `resource/roles/` 创建角色配置文件
2. 实现 `RolePlayConfig` 加载逻辑
3. 添加角色特定的提示词模板
4. 测试角色对话效果

---

## 配置说明

### 环境变量配置

```env
# NoneBot 配置
HOST=127.0.0.1
PORT=8080
COMMAND_START=["/"]
COMMAND_SEP=["."]

# NapCat 连接
ONEBOT_WS_URLS=["ws://127.0.0.1:3001"]

# LLM 配置
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4
LLM_MAX_TOKENS=2000
LLM_TEMPERATURE=0.7

# Redis 配置
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0

# Token 控制
DEFAULT_USER_QUOTA=10000
DAILY_TOKEN_LIMIT=1000
MINUTE_RATE_LIMIT=100

# 上下文配置
CONTEXT_EXPIRE_HOURS=24
MAX_CONTEXT_PER_USER=5
MAX_MESSAGES_PER_CONTEXT=100
```

### LLM 服务配置

支持多种 LLM 服务：

#### OpenAI
```env
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
LLM_API_KEY=sk-...
```

#### 通义千问
```env
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus
LLM_API_KEY=sk-...
```

#### DeepSeek
```env
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
LLM_API_KEY=sk-...
```

---

## 常见问题

### Q: 如何查看日志？

A: 日志文件位于 `./logs/robot.log`，支持日志轮转。

### Q: 如何重置用户数据？

A: 删除数据库文件：
```bash
rm ./data/db/kaoyan_408.db
```

### Q: Token 配额不足怎么办？

A: 可以在配置文件中调整 `DEFAULT_USER_QUOTA` 和 `DAILY_TOKEN_LIMIT`。

### Q: 如何自定义角色？

A: 在 `resource/roles/` 目录下创建角色配置文件，参考现有格式。

---

## 部署指南

详细的部署说明请参考 [DEPLOYMENT.md](DEPLOYMENT.md)。

---

## 许可证

MIT License

---

## 贡献

欢迎提交 Issue 和 Pull Request！

---

## 致谢

- [NoneBot2](https://nonebot.dev/) - 优秀的 Python 机器人框架
- [LangGraph](https://github.com/langchain-ai/langgraph) - 强大的状态图框架
- [NapCat](https://github.com/NapNeko/NapCatQQ-Plugin) - NTQQ 实现
