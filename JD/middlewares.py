"""
DrissionPage 下载中间件
拦截url的请求，通过 Edge 浏览器渲染后返回 HTML
"""
import time
import logging

from scrapy import signals
from scrapy.http import HtmlResponse

logger = logging.getLogger(__name__)

# Edge 浏览器调试地址
EDGE_ADDRESS = "127.0.0.1:9222"


class DrissionPageMiddleware:
    """用 DrissionPage 连接 Edge 浏览器，渲染京东列表页"""

    def __init__(self):
        self.browser = None

    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls()
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        return middleware

    def _get_browser(self):
        """懒加载浏览器连接 避免消耗内存和CPU
        """
        if self.browser is None:
            from DrissionPage import ChromiumPage, ChromiumOptions    #ChromiumPage可以切换WebPage模式

            options = ChromiumOptions()
            options.set_address(EDGE_ADDRESS)
            self.browser = ChromiumPage(options)
            logger.info("Connected to Edge browser at %s", EDGE_ADDRESS)

            # 热身访问主页
            tab = self.browser.latest_tab
            tab.get("https://www.jd.com")
            time.sleep(2)
            logger.info("浏览器加载完成")
        return self.browser

    def process_request(self, request, spider=None):
        """拦截 list.jd.com 请求，用浏览器渲染"""
        if "list.jd.com" not in request.url:
            return None  # 非列表页，交给默认下载器

        browser = self._get_browser()
        tab = browser.latest_tab

        logger.info("DrissionPage fetching: %s", request.url)
        tab.get(request.url)
        time.sleep(5)

        # 反爬---滑块验证
        if "risk_handler" in tab.url or "passport.jd.com" in tab.url:
            logger.warning("检测到滑块验证码，等待手动验证...")
            start = time.time()
            while time.time() - start < 120:
                if "list.jd.com" in tab.url and "risk_handler" not in tab.url:
                    logger.info("验证通过")
                    break
                time.sleep(4)
            else:
                logger.error("验证超时")
                return None
            time.sleep(6)
        # 滚动加载更多商品
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

        logger.info("页面加载完成，商品数: %d", prev_count)

        # 返回渲染后的 HTML 作为 Response
        body = tab.html.encode("utf-8")
        return HtmlResponse(
            url=request.url,
            body=body,
            encoding="utf-8",
            request=request,
        )

    def spider_closed(self, spider):
        """爬虫关闭时断开浏览器"""
        if self.browser:
            logger.info("断开浏览器连接")
            self.browser.quit()
            self.browser = None
