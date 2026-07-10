# 文档转 Markdown 设计方案

## 1. 目标

文件服务需要把用户上传的附件整理为 Agent 可安全、按需读取的内容源。

核心原则：

> 不把附件全文直接注入模型上下文，只注入文件清单与内容地图。Agent 需要正文时，按 file_id 和行范围调用读取工具。

该方案覆盖文件上传后的格式判断、Markdown 转换、Outline 抽取和 Agent 读取契约。

## 2. 总体流程

```text
用户上传原文件
  -> 保存原文件与文件记录
  -> 判断是否需要转换为 Markdown
     -> 不需要：原文件作为可读源
     -> 需要：生成 content.md 作为可读源
  -> 对可读源抽取 Outline
     -> 有标题：保存标题、层级和行号
     -> 无标题：保存前 5 行非空预览
  -> Agent 中间件注入文件清单与 Outline
  -> Agent 按需调用 read_uploaded_file(file_id, start_line, end_line)
  -> 工具返回指定范围内容，并进行长度保护
```

## 3. 文件分类

### 3.1 不转换的文件

以下文件不需要转 Markdown，原文件本身就是 Agent 的可读内容源：

| 类型 | 示例 | 处理方式 |
|---|---|---|
| 纯文本 | `.txt`、`.log` | 按 UTF-8 优先读取，必要时兼容 GBK 等编码 |
| Markdown | `.md` | 直接读取 |
| 结构化文本 | `.json`、`.csv`、`.yaml`、`.yml` | 直接读取 |
| 代码 | `.py`、`.java`、`.ts`、`.vue`、`.sql` 等 | 直接读取 |
| 图片 | `.png`、`.jpg`、`.jpeg`、`.webp` 等 | 不转 Markdown，不提供文本正文 |

不转换不代表跳过 Outline。

- 文本、代码、结构化文本仍然执行 Outline 抽取。
- 若没有可识别标题，则降级为前 5 行非空内容预览。
- 图片没有可读文本时，Outline 为空，并标识为“图片文件，暂未启用视觉识别”。

### 3.2 需要转换的文件

| 类型 | 目标产物 | 建议转换器 |
|---|---|---|
| PDF | `content.md` | PDF Markdown 转换器 |
| Word | `content.md` | MarkItDown |
| Excel | `content.md` | MarkItDown |
| PowerPoint | `content.md` | MarkItDown |

PDF 的主转换器可以使用 `pymupdf4llm`，但接入前必须确认其 AGPL v3 许可证是否适合项目部署模式。若不适合，使用 MarkItDown 或其他许可证兼容的 PDF 转换器。

扫描件 OCR 不作为第一版默认能力。后续单独接入 OCR 时，需要明确 OCR 引擎、语言包、成本和失败降级策略。

## 4. 存储结构

转换产物不能用 `原文件.with_suffix('.md')` 直接保存。用户上传 Markdown 文件时，这会覆盖原文件。

统一使用每个文件独立目录：

```text
data/uploads/{file_id}/
  original.pdf
  content.md
```

- `original.*`：用户上传的原始文件。
- `content.md`：转换后的 Markdown；仅对需要转换的文件生成。
- 不转换的文本类文件直接以 `original.*` 作为内容源。

## 5. 数据记录

文件记录除基本上传信息外，后续需要保存以下转换元数据：

| 字段 | 说明 |
|---|---|
| `content_path` | Agent 实际读取的内容源路径，可能是原文件或 `content.md` |
| `content_type` | `original_text`、`markdown`、`image` 等 |
| `conversion_status` | `pending`、`processing`、`success`、`failed`、`not_required` |
| `conversion_error` | 转换失败原因 |
| `converter_name` | 使用的转换器，例如 `markitdown` |
| `outline` | JSONB，保存标题、层级、起始行号等 |
| `converted_at` | 最近一次成功转换时间 |

第一版可以继续缓存解析后的 Markdown 文本，但长期应以磁盘中的内容源文件为主，数据库保存状态、路径和 Outline，避免大文档正文长期占用数据库字段。

## 6. Outline 抽取

Outline 是附件的内容地图，用于帮助 Agent 决定要读取哪个范围，而不是全文摘要。

### 6.1 标题识别

第一版识别标准 Markdown 标题：

```text
# 一级标题
## 二级标题
### 三级标题
```

每个条目至少包含：

```json
{
  "level": 2,
  "title": "岗位职责",
  "line_number": 36
}
```

### 6.2 限制与降级

- 最多注入 50 个 Outline 条目。
- 超出时增加截断标记，并提示 Agent 使用行范围读取。
- 无标题时，取前 5 行非空内容作为 `preview`。
- 图片或没有可读文本的文件，Outline 为空并保留文件类型说明。

## 7. Agent 上下文注入

`FileContextMiddleware` 只注入本次请求 `file_ids` 白名单内的文件信息：

```xml
<uploaded_files>
- file_id=abc123; name=岗位说明书.pdf; type=markdown
  Outline:
  - L12: 一、岗位职责
  - L45: 二、任职要求

请在需要正文时调用 read_uploaded_file。
</uploaded_files>
```

中间件不得注入完整文件正文，避免多个附件或长文档直接耗尽上下文。

## 8. 文件读取工具契约

工具名称：`read_uploaded_file`

建议参数：

```json
{
  "file_id": "abc123",
  "start_line": 1,
  "end_line": 200
}
```

约束：

1. 每次只能读取一个 `file_id`。
2. `file_id` 必须属于本次 Agent 运行的 `file_ids` 白名单。
3. `start_line`、`end_line` 均基于可读内容源的行号。
4. 未传行范围时，只返回受长度限制的开头预览，而不返回全文。
5. 返回内容超过上限时，保留头尾并提示 Agent 缩小行范围继续读取。
6. 图片文件应返回“当前未启用视觉识别，无法读取图片正文”的明确说明。

## 9. 转换时机与缓存

第一版采用懒转换：

1. 上传时仅保存原文件和数据库记录。
2. Agent 首次需要该文件的 Outline 或正文时执行转换。
3. 转换成功后缓存 `content.md`、Outline 与转换状态。
4. 后续请求直接复用缓存，不重复转换。

这样不会让上传接口因大 PDF、Word 或 OCR 耗时而阻塞，同时又能在 Agent 真正使用文件时获得统一 Markdown 内容。

## 10. 后续增强

- 接入扫描件 OCR，并支持中文语言包。
- 支持 Word、Excel、PPT 的表格专项转换质量优化。
- 增加 `search_uploaded_file` 工具，供 Agent 在单个大文件中按关键词定位行范围。
- 增加会话与附件关联，使后续消息可自动复用已上传文件。
- 增加文件上传数量、单文件大小和单次总大小限制。
- 增加转换任务的异步队列与前端状态展示。
