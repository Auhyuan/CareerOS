import time
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

from .city_codes import resolve_city_code
from .spider import QcwySpider


class QcwyBrowserSpider(QcwySpider):
    """使用真实浏览器页面采集前程无忧岗位数据。"""

    def run(self):
        """启动浏览器，按关键词和城市组合采集岗位数据，并保存结果。"""
        self.config.browser_user_data_dir.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as playwright:
            launch_options = {
                "headless": self.config.browser_headless,
                "args": ["--disable-blink-features=AutomationControlled"],
            }
            if self.config.browser_disable_no_sandbox:
                launch_options["ignore_default_args"] = ["--no-sandbox"]
            if self.config.browser_executable_path:
                launch_options["executable_path"] = self.config.browser_executable_path

            # 使用持久化浏览器目录，保留 Cookie 和登录态，降低每次运行都重新验证的概率。
            context = playwright.chromium.launch_persistent_context(
                str(self.config.browser_user_data_dir),
                **launch_options,
            )
            page = context.pages[0] if context.pages else context.new_page()

            try:
                for keyword in self.config.keywords:
                    for city in self.config.cities:
                        self.fetch_keyword_city_with_browser(page, keyword, city)
            finally:
                context.close()

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

    def fetch_keyword_city_with_browser(self, page, keyword, city):
        """
        通过浏览器访问某个关键词和城市组合，并捕获岗位接口响应。

        Args:
            page: Playwright 页面对象。
            keyword: 岗位关键词。
            city: 城市名称或前程无忧城市编码。
        """
        city_code = resolve_city_code(city)
        print(f"开始浏览器采集：关键词={keyword}，城市={city}，城市编码={city_code}")

        for page_num in range(1, self.config.max_pages + 1):
            payload = self.fetch_page_with_browser(page, keyword, city_code, page_num)
            if payload is None:
                print(f"第 {page_num} 页没有捕获到岗位 JSON，停止当前组合")
                break

            if self.config.save_raw_json:
                self.writer.save_raw_page(keyword, city, page_num, payload)

            jobs = self.extract_job_list(payload)
            rows = [self.normalize_job(job, keyword, city, city_code, page_num) for job in jobs]
            self.collected_rows.extend(rows)

            print(f"第 {page_num} 页完成，解析到 {len(rows)} 条岗位")
            if not rows:
                break

            time.sleep(self.config.request_delay_seconds)

    def fetch_page_with_browser(self, page, keyword, city_code, page_num):
        """
        打开搜索页并等待页面自己的岗位接口返回 JSON。

        Args:
            page: Playwright 页面对象。
            keyword: 岗位关键词。
            city_code: 前程无忧城市编码。
            page_num: 当前页码。
        """
        search_url = self.build_search_page_url(keyword, city_code, page_num)
        deadline = time.time() + self.config.browser_wait_seconds
        captured_payload = {"value": None}
        last_non_json_response = {"text": ""}

        def handle_response(response):
            """
            监听岗位接口响应，忽略 WAF HTML，直到拿到真正包含岗位列表的 JSON。

            Args:
                response: Playwright 网络响应对象。
            """
            if "/api/job/search-pc" not in response.url:
                return

            try:
                payload = response.json()
            except Exception:
                try:
                    last_non_json_response["text"] = response.text()
                except Exception:
                    last_non_json_response["text"] = ""
                return

            # 有些异常 JSON 不一定包含岗位列表，所以这里确认能提取列表再接受。
            if self.extract_job_list(payload):
                captured_payload["value"] = payload

        page.on("response", handle_response)

        try:
            page.goto(
                search_url,
                wait_until="domcontentloaded",
                timeout=self.config.browser_wait_seconds * 1000,
            )

            # 等待页面后续异步请求。如果先出现 WAF HTML，再出现 JSON，也能捕获到后者。
            while time.time() < deadline:
                if captured_payload["value"] is not None:
                    return captured_payload["value"]
                page.wait_for_timeout(500)

            # 接口没有拿到 JSON 时，尝试从页面可见内容中提取岗位卡片作为兜底。
            fallback_jobs = self.extract_jobs_from_visible_page(page)
            if fallback_jobs:
                return {"data": {"items": fallback_jobs}, "source": "visible_page_fallback"}

            self.save_debug_page(page, keyword, city_code, page_num, last_non_json_response["text"])
            print("没有等到可用岗位 JSON，也没有从页面提取到岗位卡片；已保存 debug 文件。")
            return None
        except Exception as error:
            print(f"浏览器采集失败：{error}")
            return None
        finally:
            page.remove_listener("response", handle_response)

    def build_search_page_url(self, keyword, city_code, page_num):
        """
        构造前程无忧浏览器搜索页 URL。

        Args:
            keyword: 岗位关键词。
            city_code: 前程无忧城市编码。
            page_num: 当前页码。
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
            "pageNum": page_num,
            "requestId": "",
            "pageSize": self.config.page_size,
        }
        return f"{self.SEARCH_PAGE_URL}?{urlencode(params)}"

    def extract_jobs_from_visible_page(self, page):
        """
        接口不可用时，从当前页面可见链接和文本中兜底提取岗位信息。

        Args:
            page: Playwright 页面对象。
        """
        return page.evaluate(
            """() => {
                const anchors = Array.from(document.querySelectorAll('a[href]'));
                const seen = new Set();
                const jobs = [];

                for (const anchor of anchors) {
                    const href = anchor.href || '';
                    const title = (anchor.innerText || anchor.textContent || '').trim();
                    const looksLikeJobLink =
                        href.includes('jobs.51job.com') ||
                        href.includes('/pc/job') ||
                        href.includes('jobid=') ||
                        href.includes('jobId=');

                    if (!looksLikeJobLink || !title || title.length > 80 || seen.has(href)) {
                        continue;
                    }

                    let card = anchor;
                    for (let i = 0; i < 5 && card.parentElement; i += 1) {
                        card = card.parentElement;
                        const text = (card.innerText || '').trim();
                        if (text.includes('薪') || text.includes('经验') || text.includes('学历')) {
                            break;
                        }
                    }

                    const cardText = (card.innerText || '').trim();
                    if (!cardText || cardText.length < title.length) {
                        continue;
                    }

                    seen.add(href);
                    jobs.push({
                        jobName: title,
                        jobHref: href,
                        rawVisibleText: cardText
                    });
                }

                return jobs.slice(0, 100);
            }"""
        )

    def save_debug_page(self, page, keyword, city_code, page_num, response_text):
        """
        保存失败时的页面现场，帮助判断是验证页、空页面还是选择器变化。

        Args:
            page: Playwright 页面对象。
            keyword: 岗位关键词。
            city_code: 前程无忧城市编码。
            page_num: 当前页码。
            response_text: 最近一次非 JSON 响应文本。
        """
        self.writer.save_debug_text(keyword, city_code, page_num, "api_response", response_text)

        try:
            self.writer.save_debug_text(keyword, city_code, page_num, "page_html", page.content())
        except Exception:
            pass

        try:
            visible_text = page.locator("body").inner_text(timeout=3000)
            self.writer.save_debug_text(keyword, city_code, page_num, "visible_text", visible_text)
        except Exception:
            pass
