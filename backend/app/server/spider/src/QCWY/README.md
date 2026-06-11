# 前程无忧岗位采集工具

这个目录是一个独立的前程无忧岗位采集小项目。短期目标很简单：根据不同城市和岗位关键词，采集原始岗位信息并保存到本地。

## 安装依赖

```powershell
cd D:\study\get_job_data\QCWY
pip install -r requirements.txt
playwright install chromium
```

## 使用 `.env` 运行

编辑 `.env`：

```env
QCWY_KEYWORDS=测试工程师,Java
QCWY_CITIES=上海,北京
QCWY_MAX_PAGES=1
```

运行：

```powershell
python run.py
```

## 使用命令行覆盖配置

```powershell
python run.py --keyword 测试工程师 --city 上海 --pages 1
python run.py --keyword Java,后端开发 --city 北京,杭州 --pages 2
python run.py --mode browser --keyword 测试工程师 --city 上海 --pages 1
```

默认使用 `browser` 模式，会打开浏览器并捕获页面自己的岗位接口返回。如果页面出现验证或登录提示，请在浏览器里手动处理后重新运行；浏览器数据会保存在 `.browser_profile`，后续可以复用登录态。

## 输出结果

默认输出到 `data` 目录：

```text
data/
  raw/                    # 每一页接口返回的完整原始 JSON
  processed/              # 汇总后的 CSV 和 Excel
```

第一版会保留 `raw_json` 字段，方便后续继续做字段清洗、入库和岗位画像分析。
