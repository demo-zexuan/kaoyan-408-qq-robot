# 考研408 QQ Robot - 开发计划

## 开发阶段划分

```
Phase 1: 基础设施搭建 (Foundation) ✅
    |
    v
Phase 2: 核心模块开发 (Core Modules) ✅
    |
    v
Phase 3: 用户管理系统 (User Management) ✅
    |
    v
Phase 4: 功能模块开发 (Feature Modules) ✅
    |
    v
Phase 5: 集成与测试 (Integration & Testing) 🚧 进行中
```

---

## Phase 1: 基础设施搭建 ✅ 已完成

### 1.1 项目结构调整 ✅
- [x] 创建 `src/core/` 目录
- [x] 创建 `src/modules/` 目录
- [x] 创建 `src/managers/` 目录
- [x] 创建 `src/services/` 目录
- [x] 创建 `src/storage/` 目录
- [x] 创建 `resource/roles/` 目录
- [x] 创建 `resource/prompts/` 目录

### 1.2 配置管理 ✅
- [x] 实现 `src/utils/config.py` - 配置加载器
- [x] 更新 `.env` 添加必要配置项
- [x] 实现配置验证逻辑
- [x] 修复导入路径错误 (2025-12-30)
- [x] 修复 .env 行内注释问题 (2025-12-30)

### 1.3 数据模型定义 ✅
- [x] 创建 `src/storage/models.py`
  - [x] `Context` 模型
  - [x] `ChatMessage` 模型
  - [x] `User` 模型
  - [x] `TokenQuota` 模型
  - [x] `BanRecord` 模型
  - [x] `RolePlayConfig` 模型
- [x] 创建 `src/storage/orm_models.py` - SQLAlchemy ORM模型

### 1.4 存储层实现 ✅
- [x] 创建 `src/storage/database.py` - 数据库操作
  - [x] 初始化SQLite连接 (使用aiosqlite)
  - [x] 创建表结构
  - [x] 实现CRUD基础操作
  - [x] 实现Repository模式 (UserRepository, ContextRepository等)
- [x] 创建 `src/storage/cache.py` - Redis缓存操作
  - [x] Redis连接管理
  - [x] 上下文缓存操作 (ContextCache)
  - [x] Token缓存操作 (TokenCache)
  - [x] 用户状态缓存操作 (UserCache)
  - [x] 封禁缓存操作 (BanCache)
  - [x] 统一缓存管理器 (CacheManager)

### 1.5 日志与工具 ✅
- [x] 创建 `src/utils/logger.py` - 统一日志 (基于loguru)
- [x] 创建 `src/utils/helpers.py` - 辅助函数
  - [x] 文本清理函数 (TextHelper)
  - [x] 实体提取函数 (EntityHelper)
  - [x] ID生成函数 (IDHelper)
  - [x] 日期时间辅助 (DatetimeHelper)

### 1.6 环境配置 ✅
- [x] 创建 `docker-compose.yml` - NapCat服务
- [x] 移动 `docker-compose.yml` 到根目录 (2025-12-30)
- [x] 创建 `.env.example` - 环境变量模板
- [x] 配置 `pyproject.toml` - 项目依赖和工具配置

### 1.7 单元测试 ✅
- [x] 创建 `tests/unit/test_database.py` - 数据库测试 (16 tests)
- [x] 创建 `tests/unit/test_helpers.py` - 工具函数测试 (19 tests)

### 1.8 Bug修复 ✅ (2025-12-30)
- [x] 修复 `src/utils/config.py` 导入路径错误 (`utils.path_config` → `src.utils.path_config`)
- [x] 修复 `src/utils/logger.py` 导入路径错误 (`utils import get_config` → `from src.utils.config import get_config`)
- [x] 修复 `.env` 文件行内注释导致的环境变量解析错误
- [x] 修复 `tests/unit/test_core.py` 中 MessageRouter fixture 参数错误

---

## Phase 2: 核心模块开发 ✅ 已完成

### 2.1 状态定义 (`src/core/state.py`) ✅
- [x] 定义 `RobotState` Pydantic模型
- [x] 定义 `IntentType` 枚举
- [x] 定义 `RouteTarget` 枚举
- [x] 定义 `ProcessingStage` 枚举
- [x] 定义 `IntentResult` 辅助模型
- [x] 定义 `MessageProcessingResult` 辅助模型
- [x] 实现状态工具函数 (create_initial_state, clone_state, is_terminal_state)

### 2.2 意图识别 (`src/core/intent.py`) ✅
- [x] 定义 `IntentRule` 数据模型
- [x] 实现 `IntentRecognizer` 类
  - [x] 关键词匹配识别
  - [x] 正则表达式识别
  - [x] LLM意图分类接口 (预留)
- [x] 定义意图识别规则配置 (DEFAULT_INTENT_RULES)
- [x] 实现单例模式 (get_intent_recognizer)

### 2.3 上下文管理器 (`src/core/context.py`) ✅
- [x] 实现 `ContextManager` 类
  - [x] `create_context()` - 创建上下文
  - [x] `get_context()` - 获取上下文
  - [x] `update_context()` - 更新上下文
  - [x] `delete_context()` - 删除上下文
  - [x] `add_participant()` - 添加参与者
  - [x] `remove_participant()` - 移除参与者
  - [x] `add_message()` - 添加消息
  - [x] `get_messages()` - 获取消息历史
  - [x] `list_active_contexts()` - 列出活跃上下文
  - [x] `cleanup_expired()` - 清理过期上下文
  - [x] `pause_context()` - 暂停上下文
  - [x] `resume_context()` - 恢复上下文
- [x] 实现上下文存储策略
  - [x] `RedisContextStorage` - Redis缓存存储
  - [x] `DatabaseContextStorage` - 数据库持久化
  - [x] `HybridContextStorage` - 混合存储策略
- [x] 实现单例模式 (get_context_manager)

### 2.4 LangGraph管理器 (`src/core/langgraph.py`) ✅
- [x] 实现 `LangGraphManager` 类
  - [x] 图初始化 `_build_graph()`
  - [x] 图编译 `compile()`
  - [x] 异步执行 `process()`
- [x] 实现基础节点
  - [x] `input_processor_node` - 输入预处理
  - [x] `intent_classifier_node` - 意图分类
  - [x] `context_loader_node` - 上下文加载
  - [x] `response_generator_node` - 响应生成
  - [x] `error_handler_node` - 错误处理
- [x] 实现条件边函数
  - [x] `route_by_intent()` - 意图路由
  - [x] `should_continue_after_input()` - 输入检查
  - [x] `should_continue_after_context()` - 上下文检查
  - [x] `should_end()` - 终止判断
- [x] 实现辅助函数 (state_to_messages, messages_to_state)
- [x] 实现单例模式 (get_langgraph_manager)

### 2.5 消息路由器 (`src/core/router.py`) ✅
- [x] 实现 `MessageRouter` 类
  - [x] `route_message()` - 消息路由入口
  - [x] `_pre_check()` - 预检查 (封禁、配额)
  - [x] `_get_or_create_context()` - 上下文管理
  - [x] `handle_chat_intent()` - 处理聊天意图
  - [x] `handle_weather_intent()` - 处理天气意图
  - [x] `handle_role_play_intent()` - 处理角色扮演
  - [x] `handle_context_intent()` - 处理上下文操作
- [x] 实现单例模式 (get_message_router)

### 2.6 单元测试 ✅
- [x] 创建 `tests/unit/test_core.py` - 核心模块测试 (30 tests)
  - [x] TestRobotState (2 tests)
  - [x] TestStateHelpers (3 tests)
  - [x] TestIntentRecognizer (7 tests)
  - [x] TestContextManager (7 tests)
  - [x] TestContextStorage (3 tests)
  - [x] TestLangGraphManager (2 tests)
  - [x] TestMessageRouter (3 tests)
  - [x] TestIntentResult (1 test)
  - [x] TestMessageProcessingResult (2 tests)

---

## Phase 3: 用户管理系统 ✅ 已完成

### 3.1 用户管理器 (`src/managers/user.py`) ✅
- [x] 实现 `UserManager` 类
  - [x] `get_user()` - 获取用户信息
  - [x] `create_user()` - 创建用户
  - [x] `get_or_create_user()` - 获取或创建用户
  - [x] `update_user()` - 更新用户
  - [x] `update_nickname()` - 更新昵称
  - [x] `ban_user()` / `unban_user()` - 封禁/解封用户
  - [x] `activate_user()` / `deactivate_user()` - 激活/停用用户
  - [x] `get_user_context()` - 获取用户当前上下文
  - [x] `set_user_context()` - 设置用户当前上下文
  - [x] `clear_user_context()` - 清除用户当前上下文
  - [x] `create_private_context()` - 创建私聊上下文
  - [x] `update_last_active()` - 更新最后活跃时间
  - [x] `get_active_users()` - 获取活跃用户列表
  - [x] `count_active_users()` - 统计活跃用户数量
  - [x] `is_user_active()` / `is_user_banned()` - 用户状态检查
  - [x] `get_user_metadata()` / `update_user_metadata()` - 元数据管理

### 3.2 Token控制器 (`src/managers/token.py`) ✅
- [x] 实现 `TokenController` 类
  - [x] `get_quota()` - 获取用户配额
  - [x] `get_remaining_quota()` - 获取剩余配额
  - [x] `get_daily_remaining()` - 获取今日剩余配额
  - [x] `get_usage_info()` - 获取使用情况
  - [x] `check_quota()` - 检查配额是否足够
  - [x] `check_minute_limit()` / `check_daily_limit()` - 限制检查
  - [x] `consume()` - 消耗Token
  - [x] `add_quota()` - 增加用户配额
  - [x] `reset_user()` - 重置用户使用记录
  - [x] `reset_daily()` - 重置每日配额
  - [x] `set_daily_limit()` - 设置每日限制
  - [x] `set_minute_limit()` - 设置每分钟限制
  - [x] 默认配额: 总配额50000, 每日5000, 每分钟200

### 3.3 封禁管理器 (`src/managers/ban.py`) ✅
- [x] 实现 `BanManager` 类
  - [x] `check_ban_status()` - 检查封禁状态
  - [x] `is_banned()` - 检查用户是否被封禁
  - [x] `get_ban_reason()` - 获取封禁原因
  - [x] `get_remaining_ban_time()` - 获取剩余封禁时间
  - [x] `ban_user()` - 封禁用户
  - [x] `unban_user()` - 解封用户
  - [x] `ban_user_for_spam()` - 封禁刷屏用户
  - [x] `ban_user_for_abuse()` - 封禁滥用用户
  - [x] `ban_user_permanently()` - 永久封禁用户
  - [x] `detect_abuse()` - 异常行为检测
  - [x] `list_ban_records()` - 列出封禁记录
- [x] 实现检测规则
  - [x] 短时间大量请求检测 (10次/60秒)
  - [x] Token消耗异常检测 (单次1000/每分钟5000)
  - [x] 刷屏检测 (5条消息/10秒)
  - [x] 重复内容检测 (3次重复/30秒)

### 3.4 数据库补充 ✅
- [x] `BanRecordRepository.update()` - 更新封禁记录
- [x] `TokenQuotaRepository.increment_used()` - 同时更新used和daily_used

### 3.5 单元测试 ✅
- [x] 创建 `tests/unit/test_managers.py` - 管理器模块测试 (29 tests)
  - [x] TestUserManager (8 tests)
  - [x] TestTokenController (9 tests)
  - [x] TestBanManager (9 tests)
  - [x] TestDetectionRules (2 tests)

### 3.6 Bug修复 ✅
- [x] 修复 ContextManager 导入路径
- [x] 移除无效的缓存操作 (set/get/delete)
- [x] 修复 TokenController consume 方法使用更新后的quota
- [x] 修复 list_ban_records 的 async/await 语法
- [x] 修复 increment_used 同时更新 used 和 daily_used

---

## Phase 4: 功能模块开发 ✅ 已完成

### 4.1 LLM服务 (`src/services/llm_service.py`) ✅
- [x] 实现 `LLMService` 类
  - [x] 初始化LLM客户端 (支持多厂商: OpenAI/通义千问/DeepSeek等)
  - [x] `chat()` - 对话接口
  - [x] `classify_intent()` - 意图分类
  - [x] `estimate_tokens()` - Token估算
  - [x] `stream_chat()` - 流式对话

### 4.2 天气服务 (`src/service/weather_service.py`) ✅
- [x] 实现 `WeatherService` 类
  - [x] `get_weather()` - 获取天气
  - [x] `parse_location()` - 解析地点
  - [x] `format_response()` - 格式化响应

### 4.3 闲聊模块 (`src/modules/chat.py`) ✅
- [x] 实现 `ChatModule` 类
  - [x] `handle()` - 处理闲聊请求
  - [x] 加载对话历史
  - [x] 生成回复
  - [x] 保存对话记录
  - [x] `handle_stream()` - 流式对话

### 4.4 天气模块 (`src/modules/weather.py`) ✅
- [x] 实现 `WeatherModule` 类
  - [x] `handle()` - 处理天气查询
  - [x] 地点解析
  - [x] API调用
  - [x] 结果格式化

### 4.5 角色扮演模块 (`src/modules/role_play.py`) ✅
- [x] 实现 `RolePlayModule` 类
  - [x] `create_role()` - 创建角色
  - [x] `list_roles()` - 列出角色
  - [x] `activate_role()` - 激活角色
  - [x] `generate_response()` - 生成角色回复
- [x] 创建默认角色配置
  - [x] 助手角色 (assistant)
  - [x] 老师角色 (teacher)
  - [x] 幽默角色 (humorous)

### 4.6 上下文命令模块 (`src/modules/context_cmd.py`) ✅
- [x] 实现 `ContextCommandModule` 类
  - [x] `cmd_create_context()` - 创建上下文命令
  - [x] `cmd_join_context()` - 加入上下文命令
  - [x] `cmd_leave_context()` - 离开上下文命令
  - [x] `cmd_end_context()` - 结束上下文命令
  - [x] `cmd_show_history()` - 查看历史命令
  - [x] `cmd_list_contexts()` - 列出上下文命令

### 4.7 NoneBot插件更新 (`src/plugins/llm-endpoint/`) ✅
- [x] 重写 `__init__.py` 集成新的消息路由器
- [x] 移除旧的测试命令
- [x] 添加新的事件处理器
- [x] 修复硬编码API密钥问题 (2025-12-30)

### 4.8 单元测试 ✅
- [x] 创建 `tests/unit/test_services_and_modules.py` - 服务和模块测试 (15 tests)
  - [x] TestLLMService (3 tests)
  - [x] TestWeatherService (2 tests)
  - [x] TestChatModule (3 tests)
  - [x] TestWeatherModule (2 tests)
  - [x] TestRolePlayModule (2 tests)
  - [x] TestContextCommandModule (2 tests)
  - [x] TestIntegration (1 test)

---

## Phase 5: 集成与测试 🚧 进行中

### 5.1 Bug修复与代码质量 ✅ (2025-12-30)
- [x] 修复导入路径错误 (config.py, logger.py)
- [x] 修复 .env 行内注释问题
- [x] 修复 docker-compose.yml 位置 (移至根目录)
- [x] 修复硬编码API密钥问题
- [x] 修复测试fixture参数问题
- [x] 所有109个单元测试通过 ✅

### 5.2 配置LLM服务 ⏳ 待完成
- [ ] 在 .env 中配置有效的 LLM_API_KEY
- [ ] 测试LLM连接 (weather_service, llm_service)
- [ ] 验证各模块与LLM的集成

### 5.3 Resource目录配置 ⏳ 待完成
- [ ] 添加默认角色配置到 `resource/roles/`
  - [ ] assistant.json
  - [ ] teacher.json
  - [ ] humorous.json
- [ ] 添加提示词模板到 `resource/prompts/`
  - [ ] chat_prompt.txt
  - [ ] role_play_prompt.txt
- [ ] 添加408知识库到 `resource/knowledge/` (可选)

### 5.4 集成测试 ⏳ 待完成
- [ ] 端到端消息流程测试
  - [ ] 闲聊流程测试
  - [ ] 天气查询流程测试
  - [ ] 角色扮演流程测试
  - [ ] 上下文操作流程测试
- [ ] 多用户协作场景测试
- [ ] Token限制功能测试
- [ ] 封禁机制功能测试

### 5.5 部署准备 ⏳ 待完成
- [ ] 配置生产环境 (.env.prod)
- [ ] 启动Redis服务 (docker-compose up)
- [ ] 启动NapCat服务
- [ ] 启动NoneBot机器人
- [ ] 编写部署文档

### 5.6 性能优化 ⏳ 可选
- [ ] 添加缓存优化策略
- [ ] 优化数据库查询
- [ ] 添加请求去重机制
- [ ] 添加响应限流

---

## 开发优先级矩阵

| 模块 | 优先级 | 依赖 | 预估复杂度 | 状态 |
|-----|-------|------|-----------|------|
| 配置管理 | P0 | 无 | 低 | ✅ |
| 数据模型 | P0 | 无 | 低 | ✅ |
| 存储层 | P0 | 数据模型 | 中 | ✅ |
| 状态定义 | P0 | 无 | 低 | ✅ |
| 意图识别 | P0 | 状态定义 | 中 | ✅ |
| 上下文管理 | P0 | 存储层、状态 | 高 | ✅ |
| LangGraph管理 | P0 | 上下文、意图 | 高 | ✅ |
| 消息路由 | P0 | 以上所有 | 中 | ✅ |
| 用户管理 | P1 | 存储层 | 中 | ✅ |
| Token控制 | P1 | 用户管理 | 中 | ✅ |
| 封禁管理 | P1 | 用户管理 | 中 | ✅ |
| LLM服务 | P1 | 无 | 中 | ✅ |
| 闲聊模块 | P1 | LLM服务、上下文 | 低 | ✅ |
| 天气模块 | P2 | 天气服务 | 低 | ✅ |
| 角色扮演 | P2 | LLM服务、上下文 | 中 | ✅ |
| 上下文命令 | P2 | 上下文管理 | 低 | ✅ |
| Resource配置 | P1 | 角色扮演 | 低 | ⏳ |
| 集成测试 | P1 | 所有模块 | 高 | ⏳ |
| 部署准备 | P1 | 所有模块 | 中 | ⏳ |
| 性能优化 | P3 | 所有模块 | 中 | ⏳ |

---

## 当前项目结构

```
kaoyan-408-qq-robot/
├── src/
│   ├── core/              ✅ 核心模块
│   │   ├── state.py       - 状态定义
│   │   ├── intent.py      - 意图识别
│   │   ├── context.py     - 上下文管理
│   │   ├── langgraph.py   - LangGraph管理
│   │   └── router.py      - 消息路由
│   ├── storage/           ✅ 存储层
│   │   ├── models.py      - Pydantic数据模型
│   │   ├── orm_models.py  - SQLAlchemy ORM模型
│   │   ├── database.py    - 数据库操作
│   │   └── cache.py       - Redis缓存
│   ├── utils/             ✅ 工具模块
│   │   ├── config.py      - 配置管理
│   │   ├── logger.py      - 日志管理
│   │   ├── path_config.py - 路径配置
│   │   └── helpers.py     - 辅助函数
│   ├── managers/          ✅ 管理器模块
│   │   ├── user.py        - 用户管理器
│   │   ├── token.py       - Token控制器
│   │   ├── ban.py         - 封禁管理器
│   │   └── __init__.py    - 模块导出
│   ├── modules/           ✅ 功能模块
│   │   ├── chat.py        - 闲聊模块
│   │   ├── weather.py     - 天气模块
│   │   ├── role_play.py   - 角色扮演模块
│   │   ├── context_cmd.py - 上下文命令
│   │   └── __init__.py
│   ├── service/           ✅ 服务层 (部分)
│   │   ├── weather_service.py - 天气服务
│   │   └── indent_service.py
│   ├── services/          ✅ 服务层 (部分)
│   │   └── llm_service.py - LLM服务
│   ├── plugins/           ✅ NoneBot插件
│   │   └── llm-endpoint/  - LLM端点插件
│   ├── bot.py             ✅ NoneBot入口
│   └── test/              ⚠️ 辅助测试目录
├── tests/                 ✅ 测试目录
│   └── unit/              ✅ 单元测试
│       ├── test_database.py   - 数据库测试 (16 tests)
│       ├── test_helpers.py    - 工具测试 (19 tests)
│       ├── test_core.py       - 核心测试 (30 tests)
│       ├── test_managers.py   - 管理器测试 (29 tests)
│       └── test_services_and_modules.py - 服务和模块测试 (15 tests)
├── resource/              ⏳ 待配置
│   ├── roles/             - 角色配置目录 (空)
│   ├── prompts/           - 提示词目录 (空)
│   └── knowledge/         - 知识库目录 (空)
├── data/                  ✅ 数据目录
├── logs/                  ✅ 日志目录
├── docker-compose.yml     ✅ NapCat服务 (已移至根目录)
├── .env                   ✅ 环境配置
├── .env.dev               ✅ 开发环境配置
├── .env.prod              ✅ 生产环境配置
├── pyproject.toml         ✅ 项目配置
├── README.md              ✅ 设计文档
└── TODO.md                ✅ 开发计划 (本文件)
```

---

## 测试状态

| 模块 | 测试文件 | 测试数 | 状态 |
|-----|---------|--------|------|
| 数据库 | test_database.py | 16 | ✅ 通过 |
| 工具函数 | test_helpers.py | 19 | ✅ 通过 |
| 核心模块 | test_core.py | 30 | ✅ 通过 |
| 管理器模块 | test_managers.py | 29 | ✅ 通过 |
| 服务和模块 | test_services_and_modules.py | 15 | ✅ 通过 |
| **总计** | - | **109** | **✅ 全部通过** |

---

## 开发注意事项

1. **依赖管理**：所有新增依赖需添加到 `pyproject.toml`
2. **类型注解**：使用Pydantic模型，确保类型安全
3. **异步设计**：所有I/O操作使用async/await
4. **错误处理**：添加适当的异常捕获和日志
5. **测试先行**：核心模块编写单元测试
6. **注释规范**：使用 `# 1. # I. # (1)` 风格注释
7. **导入规范**：使用 `from src.xxx` 绝对导入，避免相对导入

---

## 当前状态

- [x] 设计文档完成 (README.md)
- [x] 开发计划确认 (TODO.md)
- [x] Phase 1 完成 - 基础设施搭建
- [x] Phase 2 完成 - 核心模块开发
- [x] Phase 3 完成 - 用户管理系统
- [x] Phase 4 完成 - 功能模块开发
- [x] Phase 5 Bug修复完成 - 所有单元测试通过
- [ ] Phase 5 待完成 - Resource配置、LLM配置、集成测试、部署准备

---

## 下一步计划

### 立即可开始：Phase 5 剩余任务

1. **配置LLM服务** (高优先级)
   - 在 `.env` 中设置 `LLM_API_KEY`
   - 测试LLM连接
   - 验证对话功能

2. **配置Resource目录** (高优先级)
   - 添加默认角色配置文件
   - 添加提示词模板
   - (可选) 添加408知识库

3. **集成测试** (中优先级)
   - 端到端消息流程测试
   - 多用户协作测试
   - 封禁机制测试

4. **部署准备** (中优先级)
   - 配置生产环境
   - 启动Redis服务
   - 启动NapCat服务
   - 启动NoneBot机器人
   - 编写部署文档

5. **性能优化** (低优先级，可选)
   - 缓存优化
   - 数据库查询优化
   - 请求去重
   - 响应限流
