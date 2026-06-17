import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal
from typing import Any


class JobParserService:
    """岗位采集数据解析服务，负责把爬虫原始字段转换成业务可用字段。"""

    def parse_raw_json(self, row: dict[str, Any]) -> dict[str, Any]:
        """
        从爬虫行数据中解析 raw_json 字段。

        Args:
            row: 单条爬虫岗位数据。

        Returns:
            可写入 JSONB 字段的原始数据字典。
        """
        raw_json_value = row.get("raw_json")
        if isinstance(raw_json_value, dict):
            return raw_json_value
        if isinstance(raw_json_value, str) and raw_json_value.strip():
            try:
                return json.loads(raw_json_value)
            except json.JSONDecodeError:
                return {"raw_json_text": raw_json_value}
        return dict(row)

    def build_content_hash(self, platform: str, row: dict[str, Any], raw_json: dict[str, Any]) -> str:
        """
        构造岗位内容哈希，用于原始记录去重和后续排查。

        Args:
            platform: 招聘平台标识。
            row: 单条爬虫岗位数据。
            raw_json: 解析后的原始 JSON。

        Returns:
            SHA256 内容哈希。
        """
        # 哈希尽量使用稳定字段；没有平台 ID 时再退回到原始 JSON。
        stable_payload = {
            "platform": platform,
            "job_id": row.get("job_id"),
            "job_url": row.get("job_url"),
            "job_title_raw": row.get("job_title_raw"),
            "company_name": row.get("company_name"),
            "job_description": row.get("job_description"),
            "raw_json": raw_json,
        }
        text = json.dumps(stable_payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def parse_salary_range(self, salary_text: Any) -> tuple[Decimal | None, Decimal | None]:
        """
        从薪资文本中尽量解析出 K/月维度的最小值和最大值。

        Args:
            salary_text: 原始薪资文本，例如 10-15K、1-1.5万。

        Returns:
            最小薪资和最大薪资，无法解析时返回 None。
        """
        text = str(salary_text or "").upper().replace(" ", "")
        if not text or any(word in text for word in ["面议", "薪资面议"]):
            return None, None

        # 前程无忧常见薪资单位是 千、万、K；这里先按月薪 K 做第一版归一化。
        token_pattern = re.compile(r"(\d+(?:\.\d+)?)(万|千|K)?")
        values: list[Decimal] = []
        for number, unit in token_pattern.findall(text):
            value = Decimal(number)
            if unit == "万":
                value *= Decimal("10")
            values.append(value)

        if not values:
            return None, None
        if len(values) == 1:
            return values[0], values[0]
        return min(values), max(values)

    def parse_experience_range(self, experience_text: Any) -> tuple[Decimal | None, Decimal | None]:
        """
        从经验文本中解析最小年限和最大年限。

        Args:
            experience_text: 原始经验文本，例如 1-3年、3年以上、经验不限。

        Returns:
            最小经验年限和最大经验年限，无法解析时返回 None。
        """
        text = str(experience_text or "").replace(" ", "")
        if not text:
            return None, None
        if any(word in text for word in ["不限", "无需", "应届", "在校"]):
            return Decimal("0"), Decimal("0")

        numbers = [Decimal(item) for item in re.findall(r"\d+(?:\.\d+)?", text)]
        if not numbers:
            return None, None
        if len(numbers) == 1:
            if any(word in text for word in ["以上", "+"]):
                return numbers[0], None
            return numbers[0], numbers[0]
        return min(numbers), max(numbers)

    def parse_datetime(self, value: Any) -> datetime | None:
        """
        尽量把字符串时间解析成 datetime。

        Args:
            value: 原始时间值。

        Returns:
            datetime 对象；无法解析时返回 None。
        """
        if isinstance(value, datetime):
            return value
        if not value:
            return None

        text = str(value).strip()
        known_formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d",
        ]
        for date_format in known_formats:
            try:
                return datetime.strptime(text, date_format)
            except ValueError:
                continue
        return None

    def to_optional_str(self, value: Any) -> str | None:
        """
        把任意值转换成可选字符串，空字符串会转为 None。

        Args:
            value: 任意字段值。

        Returns:
            清理后的字符串或 None。
        """
        if value is None:
            return None
        text = str(value).strip()
        return text or None
