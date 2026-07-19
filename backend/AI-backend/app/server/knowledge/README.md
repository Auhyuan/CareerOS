# Knowledge 服务

Knowledge 是 AI-backend 内部的统一知识库模块。切片、向量化、Milvus 存储、检索和 PostgreSQL 入库队列都由该模块管理，不单独部署。

## 核心存储

- PostgreSQL：统一使用 `career_ai` 数据库；Agent 与 Knowledge 分别使用 `agent`、`knowledge` Schema。
- `knowledge` Schema：保存知识库定义、文件关联、入库任务、分块证据与索引配置快照。
- 文件服务：原始上传文件和转换后的 `content.md`。
- Milvus：分块向量、全文检索字段和检索元数据。

建表脚本：

```text
sql/20260718_create_knowledge_tables.sql
```

## 入库流程

```text
上传文件
  → 创建知识库
  → 提交 documents/submit
  → ingestion_runs 进入 pending
  → Worker 使用 FOR UPDATE SKIP LOCKED 抢占
  → 文件内容源
  → Split
  → Embedding
  → Milvus
  → knowledge_chunks
  → 任务 completed / 文档 indexed
```

Worker 默认关闭。完成建表并准备好 Embedding 与 Milvus 后，在 `.env` 设置：

```env
KNOWLEDGE_INGESTION_WORKER_ENABLED=true
```

## 当前接口

```text
GET  /knowledge/health
GET  /knowledge/capabilities
POST /knowledge/bases/create
POST /knowledge/bases/search
POST /knowledge/documents/submit
POST /knowledge/ingestion/status
POST /knowledge/ingestion/retry
POST /knowledge/split/preview
POST /knowledge/embedding/preview
POST /knowledge/retrieval/search
```

## 仍待补充

- 知识库修改、软删除及 Collection 回收。
- 文档移除和 Milvus 向量删除任务接口。
- 正式 `kb_ids` 检索映射。
- 批量 Embedding 与批量 Milvus 写入性能优化。
- 面向 Agent 的知识库检索工具和检索结果注入。
