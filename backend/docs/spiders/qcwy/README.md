# QCWY Provider

这是 spider 服务内部的前程无忧采集器实现，不再作为独立项目维护。

## 调用方式

优先通过 spider 服务 API 调用：

```text
POST /spider/qcwy/jobs
```

服务层入口：

```text
app/server/spider/src/providers/qcwy/provider.py
```

底层采集器：

```text
app/server/spider/src/QCWY/qcwy_spider
```

## 配置来源

依赖统一维护在：

```text
backend/requirements.txt
```

浏览器路径等运行配置统一放在：

```text
backend/.env
```

例如：

```env
QCWY_BROWSER_EXECUTABLE_PATH="C:\Program Files\Google\Chrome\Application\chrome.exe"
```

## 运行产物

以下目录是运行产物，不提交 Git：

```text
.browser_profile/
data/
data_test/
__pycache__/
```
