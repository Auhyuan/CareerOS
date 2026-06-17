# orchestration-backend

`orchestration-backend` 是就业指导 AI 平台的业务编排层，负责把能力层提供的 Agent、爬虫等能力组合成就业平台业务流程。

## 职责边界

编排层可以读写岗位业务表，并通过 HTTP API 调用 `capability-backend`。

当前模块：

```text
app/server/job/        # 岗位业务编排
app/common/            # 通用配置、数据库、响应、异常处理
sql/                   # 编排层数据库脚本
```

## 主要接口

岗位采集：

```text
GET  /job/health
POST /job/crawl/qcwy/jobs
```

原始岗位：

```text
POST /job/raw-records/search
GET  /job/raw-records/{raw_record_id}
```

岗位方向：

```text
POST /job/directions/search
GET  /job/directions/{direction_id}
```

岗位画像：

```text
GET  /job/directions/{direction_id}/profile
POST /job/profiles/generate
```

## 数据库

编排层当前使用 `public` schema 的岗位业务表：

```text
spider_crawl_runs
job_raw_records
job_directions
job_market_profiles
```

SQL 脚本放在：

```text
backend/orchestration-backend/sql
```

## 启动

```powershell
cd D:\study\get_job_data\backend\orchestration-backend
pip install -r requirements.txt
python app/main.py
```

默认地址：

```text
http://127.0.0.1:8091
```

## 环境变量

配置文件：

```text
.env
.env.example
```

常见配置：

```text
FASTAPI_HOST
FASTAPI_PORT
CAPABILITY_BASE_URL
CAPABILITY_TIMEOUT_SECONDS
POSTGRES_HOST
POSTGRES_PORT
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_DATABASE
```
