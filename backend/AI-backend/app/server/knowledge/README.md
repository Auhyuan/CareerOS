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

Worker 是知识入库流程的基础组件，会随 AI-backend 自动启动，不提供关闭开关。部署前需要完成建表并准备好 Embedding 与 Milvus。入库时按 Embedding 模型 `extra_config.batch_size` 分批调用模型并批量写入 Milvus；未配置时每批 32 条，允许范围为 1 到 256。

## 文档切片配置

创建知识库时的 `split_config` 是默认切片配置。提交文档时可以通过 `split_method` 或 `split_strategy` 覆盖本次文档配置，两者只能选择一个；都不传时继承知识库默认配置。配置快照会保存到 `ingestion_runs.payload.split_config`，重试时继续使用。

```json
{
  "knowledge_id": "kb_xxx",
  "file_id": "file_xxx",
  "split_strategy": {
    "type": "markdown_document_header_then_recursive",
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "headers": ["#", "##", "###", "####"]
  }
}
```

## 可用性检查

AI-backend 启动时会固定检查 PostgreSQL 和 Milvus，任一基础依赖不可用都会终止服务启动。`/knowledge/health` 只表示路由已经挂载；运行期间可调用
`/knowledge/health/readiness`，确认 PostgreSQL 和 Milvus 均为 `ok`，并确认响应中的 `worker` 为 `enabled`。具体 Embedding 与 Rerank 模型通过模型配置测试或对应预览接口验证。

## 当前接口

```text
GET  /knowledge/health
GET  /knowledge/health/readiness
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
- 面向 Agent 的知识库检索工具和检索结果注入。
