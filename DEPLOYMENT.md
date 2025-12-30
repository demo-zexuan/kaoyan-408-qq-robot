# 部署指南

<div align="center">

**考研408 QQ Robot 部署文档**

[环境要求](#环境要求) • [快速开始](#快速开始) • [配置说明](#配置说明) • [服务启动](#服务启动)

</div>

---

## 目录

- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [服务启动](#服务启动)
- [常见问题](#常见问题)
- [监控与维护](#监控与维护)
- [开发相关](#开发相关)

---

## 环境要求

### 软件要求

| 软件 | 版本要求 | 说明 |
|-----|---------|------|
| Python | 3.11+ | 推荐使用 3.11 |
| Redis | 6.0+ | 用于缓存和会话管理 |
| NapCat | 最新版 | NTQQ 实现 |
| NoneBot2 | 2.3.0+ | QQ 机器人框架 |

### 硬件要求

| 资源 | 最低配置 | 推荐配置 |
|-----|---------|---------|
| CPU | 2核 | 4核+ |
| 内存 | 2GB | 4GB+ |
| 存储 | 10GB | 20GB+ |

---

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/yourusername/kaoyan-408-qq-robot.git
cd kaoyan-408-qq-robot
```

### 2. 安装依赖

使用 uv 安装依赖（推荐）：

```bash
# 安装 uv
pip install uv

# 同步依赖
uv sync
```

或使用 pip：

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

复制并编辑环境配置文件：

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置必要的参数：

```env
# LLM 配置
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o

# Redis 配置
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0

# NapCat 连接
ONEBOT_WS_URLS=["ws://127.0.0.1:3001"]
ONEBOT_V12_ACCESS_TOKEN=your_token_here
```

### 4. 启动 Redis 服务

```bash
docker-compose up -d redis
```

或使用系统 Redis：

```bash
redis-server
```

### 5. 启动 NapCat

参考 NapCat 文档配置并启动 NapCat 服务。

### 6. 启动机器人

```bash
uv run python src/bot.py
```

或使用 NoneBot CLI：

```bash
nb run
```

---

## 配置说明

### 环境变量配置

| 变量名 | 说明 | 默认值 |
|-------|------|--------|
| `ENVIRONMENT` | 运行环境 (dev/prod) | dev |
| `DEBUG` | 调试模式 | true |
| `HOST` | 监听地址 | 127.0.0.1 |
| `PORT` | 监听端口 | 8080 |
| `LLM_API_KEY` | LLM API 密钥 | - |
| `LLM_BASE_URL` | LLM API 地址 | https://api.openai.com/v1 |
| `LLM_MODEL` | LLM 模型名称 | gpt-4o |
| `REDIS_HOST` | Redis 主机 | 127.0.0.1 |
| `REDIS_PORT` | Redis 端口 | 6379 |
| `ONEBOT_WS_URLS` | OneBot WebSocket 地址 | ws://127.0.0.1:3001 |

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

### Token 控制配置

```env
DEFAULT_USER_QUOTA=50000      # 默认总配额
DAILY_TOKEN_LIMIT=5000         # 每日限制
MINUTE_RATE_LIMIT=200          # 每分钟请求限制
```

### 上下文配置

```env
CONTEXT_EXPIRE_HOURS=24        # 上下文过期时间(小时)
MAX_CONTEXT_PER_USER=10        # 每用户最大上下文数
MAX_MESSAGES_PER_CONTEXT=200   # 每上下文最大消息数
```

---

## 服务启动

### Docker 部署

1. 构建 Docker 镜像：

```bash
docker build -t kaoyan-408-robot .
```

2. 启动服务：

```bash
docker-compose up -d
```

Docker Compose 服务架构：

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Compose                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│  │   Robot     │    │   Redis     │    │   NapCat    │    │
│  │  (Python)   │ ←→ │  (Cache)    │    │  (NTQQ)     │    │
│  │   :8080     │    │   :6379     │    │   :3001     │    │
│  └─────────────┘    └─────────────┘    └─────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 本地开发

1. 启动 Redis：

```bash
docker-compose up -d redis
# 或
redis-server
```

2. 启动机器人：

```bash
uv run python src/bot.py
```

### 生产环境

#### 使用 systemd 管理

创建 `/etc/systemd/system/kaoyan-robot.service`：

```ini
[Unit]
Description=Kaoyan 408 QQ Robot
After=network.target redis.service

[Service]
Type=simple
User=robot
WorkingDirectory=/path/to/kaoyan-408-qq-robot
Environment="PATH=/path/to/kaoyan-408-qq-robot/.venv/bin"
ExecStart=/path/to/uv run python src/bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl enable kaoyan-robot
sudo systemctl start kaoyan-robot
```

服务管理命令：

```bash
# 查看状态
sudo systemctl status kaoyan-robot

# 停止服务
sudo systemctl stop kaoyan-robot

# 重启服务
sudo systemctl restart kaoyan-robot

# 查看日志
sudo journalctl -u kaoyan-robot -f
```

生产环境部署架构：

```
┌─────────────────────────────────────────────────────────────┐
│                        生产环境                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│  │  Nginx      │    │  Robot      │    │  Redis      │    │
│  │  (反向代理)  │ ←→ │  (systemd)  │ ←→ │  (systemd)  │    │
│  │   :443      │    │   :8080     │    │   :6379     │    │
│  └─────────────┘    └─────────────┘    └─────────────┘    │
│                            ↓                                 │
│                      ┌─────────────┐                        │
│                      │   NapCat    │                        │
│                      │   :3001     │                        │
│                      └─────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 常见问题

### Q: 无法连接到 Redis？

检查 Redis 是否启动：

```bash
redis-cli ping
# 应返回 PONG
```

### Q: LLM 调用失败？

检查 API 密钥和网络连接：

```bash
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $LLM_API_KEY"
```

### Q: NapCat 连接失败？

检查 NapCat 配置和 WebSocket 地址：

1. 确保 NapCat 已启动
2. 检查 `ONEBOT_WS_URLS` 配置
3. 验证 `ONEBOT_V12_ACCESS_TOKEN`

### Q: 如何查看日志？

日志文件位于 `./logs/robot.log`，支持日志轮转。

```bash
# 实时查看日志
tail -f ./logs/robot.log

# 查看最近 100 行
tail -n 100 ./logs/robot.log
```

### Q: 如何重置用户数据？

删除数据库文件：

```bash
rm ./data/db/kaoyan_408.db
```

### Q: 如何备份配置？

```bash
# 备份环境配置
cp .env .env.backup

# 备份数据库
cp ./data/db/kaoyan_408.db ./backups/kaoyan_408_$(date +%Y%m%d).db
```

---

## 监控与维护

### 日志管理

日志按大小轮转，默认配置：

- 单文件最大：10MB
- 保留文件数：5
- 日志级别：INFO

修改配置：

```env
LOG_LEVEL=DEBUG
LOG_ROTATION_SIZE=20MB
LOG_BACKUP_COUNT=10
```

日志结构：

```
logs/
├── robot.log           # 当前日志
├── robot.log.1         # 历史日志 1
├── robot.log.2         # 历史日志 2
├── robot.log.3         # 历史日志 3
└── robot.log.4         # 历史日志 4
```

### 数据备份

定期备份数据库：

```bash
# 手动备份
cp ./data/db/kaoyan_408.db ./backups/kaoyan_408_$(date +%Y%m%d).db

# 使用 cron 定时备份 (每天凌晨 2 点)
0 2 * * * cp /path/to/kaoyan-408-qq-robot/data/db/kaoyan_408.db /path/to/backups/kaoyan_408_$(date +\%Y\%m\%d).db
```

### 性能监控

使用 Redis 监控：

```bash
# 查看 Redis 统计信息
redis-cli info stats

# 查看内存使用
redis-cli info memory

# 实时监控
redis-cli monitor
```

### 系统监控

推荐使用以下工具：

- **htop**: 系统资源监控
- **iotop**: IO 监控
- **netstat**: 网络连接监控

```bash
# 安装监控工具
sudo apt install htop iotop

# 查看系统资源
htop

# 查看网络连接
netstat -tunlp | grep 8080
```

---

## 开发相关

### 运行测试

```bash
# 单元测试
uv run pytest tests/unit/ -v

# 集成测试
uv run pytest tests/integration/ -v

# 所有测试
uv run pytest tests/ -v

# 带覆盖率报告
uv run pytest tests/ --cov=src --cov-report=html
```

测试覆盖：

- 单元测试: 109 tests
- 集成测试: 13 tests
- 总计: 122+ tests

### 代码检查

```bash
# 类型检查
uv run mypy src/

# 代码格式化
uv run black src/
uv run isort src/

# 代码检查
uv run pylint src/
```

### 调试模式

启用调试模式：

```env
DEBUG=true
LOG_LEVEL=DEBUG
```

使用 VS Code 调试配置：

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Robot",
            "type": "debugpy",
            "request": "launch",
            "module": "src.bot",
            "console": "integratedTerminal",
            "env": {
                "DEBUG": "true"
            }
        }
    ]
}
```

---

## 更新日志

### v0.1.0 (2025-12-30)

- 初始版本发布
- 实现核心功能模块
- 支持 LLM 对话、天气查询、角色扮演
- 实现用户管理和 Token 控制
- 122+ 测试用例覆盖

---

## 获取帮助

- 提交 Issue: [GitHub Issues](https://github.com/demo-zexuan/kaoyan-408-qq-robot/issues)
- 查看文档: [README.md](README.md)
