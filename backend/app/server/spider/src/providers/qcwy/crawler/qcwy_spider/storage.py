import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd


def safe_filename(text):
    """把城市、关键词等文本转换成适合作为文件名的字符串。"""
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", str(text).strip())
    return cleaned or "unknown"


class ResultWriter:
    """负责保存前程无忧接口返回的原始 JSON 和汇总表格。"""

    def __init__(self, output_dir):
        """
        初始化输出目录，并准备 raw、debug、processed 三类子目录。

        Args:
            output_dir: 本次采集任务的输出根目录。
        """
        self.output_dir = Path(output_dir)
        self.raw_dir = self.output_dir / "raw"
        self.debug_dir = self.output_dir / "debug"
        self.processed_dir = self.output_dir / "processed"

        # 创建目录时使用 parents=True，方便调用方直接配置多级输出路径。
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def save_raw_page(self, keyword, city, page_num, payload):
        """
        保存单页接口返回的完整 JSON，便于后续重新清洗或排查字段。

        Args:
            keyword: 当前采集关键词。
            city: 当前采集城市。
            page_num: 当前采集页码。
            payload: 接口返回的原始 JSON 字典。
        """
        file_name = f"{safe_filename(keyword)}_{safe_filename(city)}_page_{page_num}.json"
        file_path = self.raw_dir / file_name

        with file_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)

        return file_path

    def save_rows(self, rows, save_csv=True, save_excel=True):
        """
        保存所有岗位行到 CSV 和 Excel，方便人工查看第一批原始结果。

        Args:
            rows: 已标准化的岗位数据列表。
            save_csv: 是否输出 CSV 文件。
            save_excel: 是否输出 Excel 文件。
        """
        if not rows:
            return None, None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        df = pd.DataFrame(rows)
        csv_path = self.processed_dir / f"qcwy_jobs_{timestamp}.csv"
        excel_path = self.processed_dir / f"qcwy_jobs_{timestamp}.xlsx"

        # CSV 适合程序继续处理；utf-8-sig 可以避免 Excel 打开中文乱码。
        if save_csv:
            df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        else:
            csv_path = None

        # Excel 适合先手动检查字段质量。
        if save_excel:
            df.to_excel(excel_path, index=False)
        else:
            excel_path = None

        return csv_path, excel_path

    def save_debug_text(self, keyword, city, page_num, name, content):
        """
        保存调试文本，例如 WAF 响应、页面 HTML 或可见文本。

        Args:
            keyword: 当前采集关键词。
            city: 当前采集城市或城市编码。
            page_num: 当前采集页码。
            name: 调试文件类型名称。
            content: 需要保存的文本内容。
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = (
            f"{safe_filename(keyword)}_{safe_filename(city)}_"
            f"page_{page_num}_{safe_filename(name)}_{timestamp}.txt"
        )
        file_path = self.debug_dir / file_name

        with file_path.open("w", encoding="utf-8") as file:
            file.write(content or "")

        return file_path
