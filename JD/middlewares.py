import time
import logging

from scrapy import signals
from scrapy.http import HtmlResponse

logger = logging.getLogger(__name__)
EDGE_ADDRESS = "127.0.0.1:9222"

class DrissionPageMiddleware:
    """ChromiumPage 中间件：自动翻页采集"""

    def __init__(self):
        self.browser = None
        self.current_tab = None

    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls()
        middleware.max_pages = crawler.settings.getint('MAX_PAGES', 100)
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        return middleware

    def _get_browser(self):
        if self.browser is None:
            from DrissionPage import ChromiumPage, ChromiumOptions

            options = ChromiumOptions()
            options.set_address(EDGE_ADDRESS)
            self.browser = ChromiumPage(options)
            logger.info("ChromiumPage 已连接: %s", EDGE_ADDRESS)

            tab = self.browser.latest_tab
            tab.get("https://www.jd.com")
            time.sleep(2)
        return self.browser

    def _new_tab(self, url):
        browser = self._get_browser()
        if self.current_tab:
            try:
                self.current_tab.close()
            except Exception:
                pass
            self.current_tab = None

        tab = browser.new_tab()
        self.current_tab = tab
        tab.get(url)
        time.sleep(5)
        return tab

    def process_request(self, request, spider=None):
        url = request.url
        if "search.jd.com" not in url and "list.jd.com" not in url:
            return None

        logger.info("采集: %s (最多%d页)", url, self.max_pages)
        return self._fetch_with_pagination(request)

    def _fetch_with_pagination(self, request):
        """打开标签页，自动翻页采集，合并HTML返回"""
        tab = self._new_tab(request.url)

        # 验证码检测
        if "risk_handler" in tab.url or "passport.jd.com" in tab.url:
            logger.warning("检测到滑块验证码，等待手动验证...")
            start = time.time()
            while time.time() - start < 120:
                if "search.jd.com" in tab.url and "risk_handler" not in tab.url:
                    logger.info("验证通过")
                    break
                time.sleep(4)
            else:
                logger.error("验证超时")
                return None
            time.sleep(6)

        # 第1页：滚动加载
        self._scroll_to_load(tab)
        all_html = tab.html
        logger.info("第1页采集完成")

        # 翻页采集直到没有下一页或达到最大页数
        page_num = 1
        while True:
            if self.max_pages and page_num >= self.max_pages:
                logger.info("已达到最大页数: %d 页", self.max_pages)
                break

            next_btn = tab.ele('css:div[class*=_pagination_next_]', timeout=5)
            if not next_btn:
                logger.info("没有更多页了")
                break

            next_btn.click()
            time.sleep(5)
            self._scroll_to_load(tab)

            page_num += 1
            page_html = tab.html
            if 'data-sku' not in page_html:
                logger.info("第%d页无商品，停止翻页", page_num)
                break

            all_html += page_html
            logger.info("第%d页采集完成", page_num)

        return HtmlResponse(
            url=request.url,
            body=all_html.encode("utf-8"),
            encoding="utf-8",
            request=request,
        )

    @staticmethod
    def _scroll_to_load(tab):
        prev_count = 0
        stable_rounds = 0
        for i in range(20):
            tab.scroll.down(600)
            time.sleep(0.8)

            count = len(set(
                s for item in tab.eles("css:div[data-sku]", timeout=2)
                if (s := item.attr("data-sku"))
            ))
            if count > prev_count:
                logger.info("滚动第 %d 次: %d 个商品", i + 1, count)
                prev_count = count
                stable_rounds = 0
            else:
                stable_rounds += 1
            if stable_rounds >= 3:
                break

    def spider_closed(self, spider):
        if self.current_tab:
            try:
                self.current_tab.close()
            except Exception:
                pass
        if self.browser:
            logger.info("断开 ChromiumPage 连接")
            self.browser.quit()
            self.browser = None
