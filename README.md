# OpenDataAgent

MySQL-only 的 Skill 驱动通用 Agent 平台 MVP。

## 目录结构

- `frontend/`: Vue 3 + Element Plus + TailwindCSS + ECharts 聊天台
- `backend/`: FastAPI + MySQL + Worker + Claude Agent SDK 适配层
- `skills/`: 文件优先的 skill 包
- `docs/`: 设计与实施计划

## 快速启动

### 1. Node 环境

```bash
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
nvm use
```

### 2. 安装前端依赖

```bash
cd frontend
npm install
```

### 3. 初始化 MySQL schema

默认连接：

- host: `127.0.0.1`
- port: `3306`
- user: `root`
- password: `root`
- database: `opendata_agent`

可通过环境变量覆盖：

- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_DATABASE`

### 4. 启动 API

```bash
PYTHONPATH=backend python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 5. 启动 Worker

```bash
PYTHONPATH=backend python3 -m app.worker.main
```

### 6. 启动前端

```bash
cd frontend
npm run dev
```

## 运行测试

```bash
PYTHONPATH=backend pytest backend/tests -q
```

