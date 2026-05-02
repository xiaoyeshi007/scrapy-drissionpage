"""
DrissionPage 下载中间件
ChromiumPage 多标签页模式采集数据，每个关键词独立标签页
支持 search.jd.com 搜索结果页和翻页操作
"""
import time
import logging

from scrapy import signals
from scrapy.http import HtmlResponse

logger = logging.getLogger(__name__)

# Edge 浏览器调试地址
EDGE_ADDRESS = "127.0.0.1:9222"


class DrissionPageMiddleware:
    """ChromiumPage 中间件：多标签页采集 + 翻页"""

    def __init__(self):
        self.browser = None
        self.current_tab = None  # 当前工作的标签页

    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls()
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        return middleware

    def _get_browser(self):
        """懒加载 ChromiumPage"""
        if self.browser is None:
            from DrissionPage import ChromiumPage, ChromiumOptions

            options = ChromiumOptions()
            options.set_address(EDGE_ADDRESS)
            self.browser = ChromiumPage(options)
            logger.info("ChromiumPage 已连接: %s", EDGE_ADDRESS)

            # 热身访问主页
            tab = self.browser.latest_tab
            tab.get("https://www.jd.com")
            time.sleep(2)
            logger.info("ChromiumPage 加载完成")
        return self.browser

    def _new_tab(self, url):
        """新建标签页并访问URL"""
        browser = self._get_browser()
        # 关闭上一个工作标签页（保留首页标签页）
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

    def _get_tab(self):
        """获取当前工作标签页"""
        if self.current_tab is None:
            browser = self._get_browser()
            self.current_tab = browser.latest_tab
        return self.current_tab

    def process_request(self, request, spider=None):
        """拦截 search.jd.com 和 list.jd.com 请求"""
        url = request.url
        if "search.jd.com" not in url and "list.jd.com" not in url:
            return None

        click_next = request.meta.get("click_next_page", False)
        if click_next:
            logger.info("翻页: 点击下一页")
            return self._click_next_page(request)

        logger.info("新标签页采集: %s", url)
        return self._fetch_in_new_tab(request)

    def _fetch_in_new_tab(self, request):
        """新建标签页采集搜索结果"""
        tab = self._new_tab(request.url)

        # 反爬---滑块验证
        if "risk_handler" in tab.url or "passport.jd.com" in tab.url:
            logger.warning("检测到滑块验证码，等待手动验证...")
            start = time.time()
            while time.time() - start < 120:
                if ("search.jd.com" in tab.url or "list.jd.com" in tab.url) and "risk_handler" not in tab.url:
                    logger.info("验证通过")
                    break
                time.sleep(4)
            else:
                logger.error("验证超时")
                return None
            time.sleep(6)

        # 滚动加载商品
        self._scroll_to_load(tab)
        logger.info("标签页加载完成")

        body = tab.html.encode("utf-8")
        return HtmlResponse(
            url=request.url,
            body=body,
            encoding="utf-8",
            request=request,
        )

    def _click_next_page(self, request):
        """在同一标签页点击下一页"""
        tab = self._get_tab()

        next_btn = tab.ele('css:div[class*=_pagination_next_]', timeout=5)
        if not next_btn:
            logger.warning("未找到下一页按钮")
            body = tab.html.encode("utf-8")
            return HtmlResponse(url=request.url, body=body, encoding="utf-8", request=request)

        next_btn.click()
        time.sleep(5)

        self._scroll_to_load(tab)

        active = tab.ele('css:div[class*=_pagination_item_][class*=_active_]', timeout=3)
        if active:
            logger.info("已翻到第 %s 页", active.text.strip())

        body = tab.html.encode("utf-8")
        return HtmlResponse(
            url=request.url,
            body=body,
            encoding="utf-8",
            request=request,
        )

    @staticmethod
    def _scroll_to_load(tab):
        """滚动页面加载懒加载商品"""
        prev_count = 0
        stable_rounds = 0
        for i in range(20):
            tab.scroll.down(600)
            time.sleep(0.8)

            skus = set()
            for item in tab.eles("css:div[data-sku]", timeout=2):
                s = item.attr("data-sku")
                if s:
                    skus.add(s)

            count = len(skus)
            if count > prev_count:
                logger.info("滚动第 %d 次: %d 个商品", i + 1, count)
                prev_count = count
                stable_rounds = 0
            else:
                stable_rounds += 1
            if stable_rounds >= 3:
                break

    def spider_closed(self, spider):
        """爬虫关闭时关闭所有连接"""
        if self.current_tab:
            try:
                self.current_tab.close()
            except Exception:
                pass
            self.current_tab = None
        if self.browser:
            logger.info("断开 ChromiumPage 连接")
            self.browser.quit()
            self.browser = None
