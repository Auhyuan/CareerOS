# 就业指导 AI 平台 Python 后端

这是就业指导 AI 平台的 Python 后端工程。当前已经拆成两个独立 FastAPI 服务：

- `capability-backend`：基础能力层，提供 Agent、模型调用、爬虫采集等通用能力。
- `orchestration-backend`：业务编排层，负责岗位数据入库、岗位方向、岗位画像等业务流程。

Java 后端负责登录、权限、用户、菜单、页面流程和统一调用入口；Python 后端不做权限管理，只提供业务能力接口。

## 目录结构

```text
backend/
  capability-backend/        # 基础能力层
    app/
      server/
        agent/               # 通用 Agent 能力
        spider/              # 招聘数据采集能力
    sql/                     # 能力层数据库脚本

  orchestration-backend/     # 业务编排层
    app/
      server/
        job/                 # 岗位业务编排
    sql/                     # 编排层数据库脚本

docs/                        # 项目级设计文档
```

## 服务边界

### capability-backend

基础能力层只提供通用能力，不直接写岗位业务表。

当前能力：

- Agent 运行：`/agent/run`
- Agent 会话：`/agent/conversations/*`
- Agent 模板：`/agent/templates/*`
- 前程无忧爬虫：`/spider/qcwy/jobs`

### orchestration-backend

业务编排层负责就业平台业务流程和业务数据入库。

当前能力：

- 采集并入库前程无忧岗位：`/job/crawl/qcwy/jobs`
- 查询原始岗位池：`/job/raw-records/search`
- 查询岗位方向字典：`/job/directions/search`
- 查询岗位画像：`/job/profiles/{profile_id}`
- 岗位画像生成占位接口：`/job/profiles/generate`

## 调用链路

```text
Java / 前端
  -> orchestration-backend:8091 /job/crawl/qcwy/jobs
      -> capability-backend:8090 /spider/qcwy/jobs
      <- 返回岗位采集 rows
      -> orchestration-backend 写入 PostgreSQL
  <- 返回 crawl_run_id / ingest_stats / rows
```

## 启动方式

推荐使用 Python 3.12。

启动能力层：

```powershell
cd D:\study\get_job_data\backend\capability-backend
pip install -r requirements.txt
python app/main.py
```

默认地址：

```text
http://127.0.0.1:8090
```

启动编排层：

```powershell
cd D:\study\get_job_data\backend\orchestration-backend
pip install -r requirements.txt
python app/main.py
```

默认地址：

```text
http://127.0.0.1:8091
```

## 数据库职责

能力层使用 `agent` schema 保存 Agent 相关表：

- `agent.agent_conversations`
- `agent.agent_messages`
- `agent.agent_templates`
- LangGraph checkpointer 表

编排层使用 `public` schema 保存岗位业务表：

- `spider_crawl_runs`
- `job_raw_records`
- `job_directions`
- `job_market_profiles`

## 核心业务链路

```text
招聘平台原始岗位
  -> job_raw_records
  -> Agent 聚合分析
  -> job_market_profiles
  -> 前端页面展示
```

前端后续主要展示的是岗位画像，而不是招聘网站上的单条岗位。

## 文档

- [架构图](docs/架构图.md)
- [AC-验收标准文档](docs/AC-验收标准文档.md)
- [TDD-技术标准文档](docs/TDD-技术标准文档.md)
- [ERD-数据库设计](docs/ERD-数据库设计.md)
- [API-SPEC接口文档](docs/API-SPEC接口文档.md)
- [就业指导AI平台-产品设计文档](docs/就业指导AI平台-产品设计文档.md)
