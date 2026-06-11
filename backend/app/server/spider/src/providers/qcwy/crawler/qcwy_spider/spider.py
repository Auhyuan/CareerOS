import json
import time
from datetime import datetime
from urllib.parse import urlencode

import requests

from .city_codes import resolve_city_code
from .storage import ResultWriter


class QcwySpider:
    """前程无忧岗位搜索接口爬虫。"""

    SEARCH_PAGE_URL = "https://we.51job.com/pc/search"
    SEARCH_API_URL = "https://we.51job.com/api/job/search-pc"

    def __init__(self, config):
        """
        初始化请求会话、配置和结果写入器。

        Args:
            config: 前程无忧爬虫运行配置。
        """
        self.config = config
        self.session = requests.Session()
        self.writer = ResultWriter(config.output_dir)
        self.collected_rows = []

        # 设置常见浏览器请求头，尽量模拟正常搜索页请求。
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": "https://we.51job.com/pc/search",
                "Origin": "https://we.51job.com",
            }
        )

        # 如果调用方提供 Cookie，则直接带上，适合遇到登录或风控时临时试跑。
        if self.config.cookie:
            self.session.headers.update({"Cookie": self.config.cookie})

    def run(self):
        """按照关键词和城市组合批量采集岗位数据，并保存结果。"""
        for keyword in self.config.keywords:
            for city in self.config.cities:
                self.fetch_keyword_city(keyword, city)

        csv_path, excel_path = self.writer.save_rows(
            self.collected_rows,
            save_csv=self.config.save_csv,
            save_excel=self.config.save_excel,
        )

        print(f"采集完成，共获取 {len(self.collected_rows)} 条岗位记录")
        if csv_path:
            print(f"CSV 已保存：{csv_path}")
        if excel_path:
            print(f"Excel 已保存：{excel_path}")
        return {
            "rows": self.collected_rows,
            "csv_path": str(csv_path) if csv_path else None,
            "excel_path": str(excel_path) if excel_path else None,
        }

    def fetch_keyword_city(self, keyword, city):
        """
        采集某一个关键词和城市组合下的多页岗位数据。

        Args:
            keyword: 岗位关键词。
            city: 城市名称或前程无忧城市编码。
        """
        city_code = resolve_city_code(city)
        print(f"开始采集：关键词={keyword}，城市={city}，城市编码={city_code}")

        # 先访问搜索页，让服务端下发必要 Cookie；部分情况下可以提高接口请求成功率。
        self.warmup_search_page(keyword, city_code)

        for page_num in range(1, self.config.max_pages + 1):
            payload = self.fetch_page(keyword, city_code, page_num)
            if payload is None:
                print(f"第 {page_num} 页请求失败，停止当前组合")
                break

            if self.config.save_raw_json:
                self.writer.save_raw_page(keyword, city, page_num, payload)

            jobs = self.extract_job_list(payload)
            rows = [self.normalize_job(job, keyword, city, city_code, page_num) for job in jobs]
            self.collected_rows.extend(rows)

            print(f"第 {page_num} 页完成，解析到 {len(rows)} 条岗位")

            # 如果当前页没有数据，通常说明已经翻到末尾或接口返回异常，继续翻页意义不大。
            if not rows:
                break

            time.sleep(self.config.request_delay_seconds)

    def warmup_search_page(self, keyword, city_code):
        """
        先打开前程无忧搜索页，获取接口请求可能需要的 Cookie。

        Args:
            keyword: 岗位关键词。
            city_code: 前程无忧城市编码。
        """
        params = {
            "jobArea": city_code,
            "keyword": keyword,
            "searchType": "2",
            "sortType": "0",
            "metro": "",
            "salary": "",
            "workYear": "",
            "degree": "",
            "companyType": "",
            "companySize": "",
            "jobType": "",
            "issueDate": "",
            "pageNum": "1",
            "requestId": "",
        }

        try:
            self.session.get(
                self.SEARCH_PAGE_URL,
                params=params,
                timeout=self.config.timeout_seconds,
            )
        except requests.RequestException as error:
            # 搜索页预热失败不一定代表接口不能用，所以这里只打印提示，不中断任务。
            print(f"搜索页预热失败，将继续尝试接口请求：{error}")

    def fetch_page(self, keyword, city_code, page_num):
        """
        请求前程无忧岗位搜索接口并返回 JSON 字典。

        Args:
            keyword: 岗位关键词。
            city_code: 前程无忧城市编码。
            page_num: 当前页码。
        """
        params = self.build_api_params(keyword, city_code, page_num)
        url = f"{self.SEARCH_API_URL}?{urlencode(params)}"

        try:
            response = self.session.get(url, timeout=self.config.timeout_seconds)
            response.raise_for_status()
        except requests.RequestException as error:
            print(f"接口请求失败：{error}")
            return None

        try:
            return response.json()
        except json.JSONDecodeError:
            print(f"接口没有返回 JSON，状态码={response.status_code}，前 200 字符={response.text[:200]}")
            return None

    def build_api_params(self, keyword, city_code, page_num):
        """
        构造前程无忧搜索接口参数。

        Args:
            keyword: 岗位关键词。
            city_code: 前程无忧城市编码。
            page_num: 当前页码。
        """
        return {
            "api_key": "51job",
            "timestamp": int(time.time() * 1000),
            "keyword": keyword,
            "searchType": "2",
            "function": "",
            "industry": "",
            "jobArea": city_code,
            "jobArea2": "",
            "landmark": "",
            "metro": "",
            "salary": "",
            "workYear": "",
            "degree": "",
            "companyType": "",
            "companySize": "",
            "jobType": "",
            "issueDate": "",
            "sortType": "0",
            "pageNum": page_num,
            "requestId": "",
            "pageSize": self.config.page_size,
            "source": "1",
            "accountId": "",
            "pageCode": "sou|sou|soulb",
        }

    def extract_job_list(self, payload):
        """
        从接口 JSON 中提取岗位列表，兼容不同层级的返回结构。

        Args:
            payload: 接口返回的 JSON 字典。
        """
        if not isinstance(payload, dict):
            return []

        # 常见结构通常是 data.resultbody.job.items 或 data.jobList；这里优先查常见字段。
        direct_candidates = [
            ("data", "resultbody", "job", "items"),
            ("data", "jobList"),
            ("data", "items"),
            ("resultbody", "job", "items"),
            ("jobList",),
        ]
        for path in direct_candidates:
            value = self.get_nested_value(payload, path)
            if self.looks_like_job_list(value):
                return value

        # 如果接口结构有变化，就递归寻找最像岗位列表的数组，保证第一版更耐用。
        recursive_value = self.find_job_list_recursively(payload)
        if recursive_value:
            return recursive_value

        return []

    def get_nested_value(self, data, path):
        """
        按照路径从嵌套字典里安全取值。

        Args:
            data: 待取值的字典。
            path: 字段路径，例如 ("data", "items")。
        """
        current = data
        for key in path:
            if not isinstance(current, dict) or key not in current:
                return None
            current = current[key]
        return current

    def looks_like_job_list(self, value):
        """
        判断某个列表是否像岗位列表。

        Args:
            value: 任意待检查值。
        """
        if not isinstance(value, list) or not value:
            return False

        first_item = value[0]
        if not isinstance(first_item, dict):
            return False

        # 岗位数据一般会包含岗位名、公司名、薪资、城市等字段，命中任意两个即可认为像岗位列表。
        job_keys = {
            "jobName",
            "job_name",
            "jobTitle",
            "companyName",
            "company_name",
            "provideSalaryString",
            "workAreaString",
            "jobAreaString",
        }
        return len(job_keys.intersection(first_item.keys())) >= 2

    def find_job_list_recursively(self, value):
        """
        递归搜索 JSON 中最像岗位列表的字段。

        Args:
            value: 任意 JSON 节点。
        """
        if self.looks_like_job_list(value):
            return value

        if isinstance(value, dict):
            for child in value.values():
                result = self.find_job_list_recursively(child)
                if result:
                    return result

        if isinstance(value, list):
            for child in value:
                result = self.find_job_list_recursively(child)
                if result:
                    return result

        return []

    def normalize_job(self, job, keyword, city, city_code, page_num):
        """
        把接口岗位字典整理成便于查看的原始表格行。

        Args:
            job: 单条岗位原始字典。
            keyword: 当前采集关键词。
            city: 当前采集城市。
            city_code: 前程无忧城市编码。
            page_num: 当前采集页码。
        """
        collected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 第一版不做深度清洗，只把常见字段平铺出来，同时保留原始 JSON 方便后续补字段。
        return {
            "source_platform": "前程无忧",
            "search_keyword": keyword,
            "city": city,
            "city_code": city_code,
            "page_num": page_num,
            "job_id": self.pick(job, "jobId", "jobid", "id"),
            "job_url": self.pick(job, "jobHref", "jobUrl", "job_href", "url"),
            "job_title_raw": self.pick(job, "jobName", "job_name", "jobTitle", "title"),
            "company_name": self.pick(job, "companyName", "company_name", "company"),
            "location": self.pick(job, "workAreaString", "jobAreaString", "area", "cityString"),
            "salary_text": self.pick(job, "provideSalaryString", "salary", "salaryString"),
            "experience_text": self.pick(job, "workYearString", "workYear", "experience"),
            "education_text": self.pick(job, "degreeString", "degree", "education"),
            "employment_type": self.pick(job, "termStr", "jobType", "employmentType"),
            "industry": self.pick(job, "industryType1Str", "industryType2Str", "industry"),
            "company_size": self.pick(job, "companySizeString", "companySize"),
            "published_at": self.pick(job, "issueDateString", "updateDateTime", "issuedate", "publishTime"),
            "collected_at": collected_at,
            "job_description": self.pick(job, "jobDescribe", "jobDescription", "description", "job_desc"),
            "raw_tags": self.join_if_list(self.pick(job, "jobTags", "welfareTags", "tags", default=[])),
            "raw_json": json.dumps(job, ensure_ascii=False),
        }

    def pick(self, data, *keys, default=""):
        """
        从字典中按候选字段名依次取第一个非空值。

        Args:
            data: 单条岗位原始字典。
            keys: 候选字段名。
            default: 所有字段都为空时返回的默认值。
        """
        for key in keys:
            value = data.get(key)
            if value not in (None, ""):
                return value
        return default

    def join_if_list(self, value):
        """
        把列表字段转换成分号分隔的字符串，普通字段保持原样。

        Args:
            value: 任意字段值。
        """
        if isinstance(value, list):
            return ";".join(str(item) for item in value)
        return value
