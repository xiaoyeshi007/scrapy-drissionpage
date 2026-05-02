"""
DrissionPage 下载中间件
SessionPage 模式采集数据，遇到验证码切换 ChromiumPage 模式人工操作
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
    """WebPage 中间件：SessionPage 采集 + ChromiumPage 处理验证码 + 翻页"""

    def __init__(self):
        self.session_page = None
        self.chromium_page = None

    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls()
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        return middleware

    def _get_session_page(self):
        """懒加载 SessionPage"""
        if self.session_page is None:
            from DrissionPage import WebPage

            self.session_page = WebPage(mode='s')
            logger.info("SessionPage 已创建")
        return self.session_page

    def _get_chromium_page(self):
        """懒加载 ChromiumPage"""
        if self.chromium_page is None:
            from DrissionPage import ChromiumPage, ChromiumOptions

            options = ChromiumOptions()
            options.set_address(EDGE_ADDRESS)
            self.chromium_page = ChromiumPage(options)
            logger.info("ChromiumPage 已连接: %s", EDGE_ADDRESS)

            # 热身访问主页
            tab = self.chromium_page.latest_tab
            tab.get("https://www.jd.com")
            time.sleep(2)
            logger.info("ChromiumPage 加载完成")
        return self.chromium_page

    def process_request(self, request, spider=None):
        """拦截 search.jd.com 和 list.jd.com 请求"""
        url = request.url
        if "search.jd.com" not in url and "list.jd.com" not in url:
            return None  # 非搜索/列表页，交给默认下载器

        # 是否需要点击下一页
        click_next = request.meta.get("click_next_page", False)
        if click_next:
            logger.info("翻页: 点击下一页")
            return self._click_next_page(request)

        logger.info("SessionPage 采集: %s", url)
        return self._fetch_by_session(request)

    def _fetch_by_session(self, request):
        """SessionPage 模式采集"""
        page = self._get_session_page()
        page.get(request.url)
        time.sleep(3)

        # 检测验证码 --> 切换 ChromiumPage
        if self._is_captcha(page):
            logger.warning("SessionPage 检测到验证码，切换 ChromiumPage 模式")
            return self._fetch_by_chromium(request)

        # 检测页面是否加载了商品数据，无数据则降级到 ChromiumPage
        body = page.html
        if 'data-sku' not in body:
            logger.info("SessionPage 未获取到商品数据，降级到 ChromiumPage 模式")
            return self._fetch_by_chromium(request)

        # SessionPage 采集页面内容
        return HtmlResponse(
            url=request.url,
            body=body.encode("utf-8"),
            encoding="utf-8",
            request=request,
        )

    def _fetch_by_chromium(self, request):
        """ChromiumPage 模式：人工处理验证码 + 滚动加载"""
        browser = self._get_chromium_page()
        tab = browser.latest_tab

        tab.get(request.url)
        time.sleep(5)

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

        # 滚动加载更多商品
        self._scroll_to_load(tab)

        logger.info("ChromiumPage 加载完成")

        # 返回渲染后的 HTML
        body = tab.html.encode("utf-8")
        return HtmlResponse(
            url=request.url,
            body=body,
            encoding="utf-8",
            request=request,
        )

    def _click_next_page(self, request):
        """点击下一页按钮加载新数据"""
        browser = self._get_chromium_page()
        tab = browser.latest_tab

        # 点击下一页按钮
        next_btn = tab.ele('css:div[class*=_pagination_next_]', timeout=5)
        if not next_btn:
            logger.warning("未找到下一页按钮")
            # 返回当前页内容
            body = tab.html.encode("utf-8")
            return HtmlResponse(
                url=request.url,
                body=body,
                encoding="utf-8",
                request=request,
            )

        next_btn.click()
        time.sleep(5)

        # 等待新内容加载
        self._scroll_to_load(tab)

        # 检查当前页码
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

    @staticmethod
    def _is_captcha(page):
        """检测是否遇到验证码"""
        url = getattr(page, 'url', '') or ''
        return "risk_handler" in url or "passport.jd.com" in url

    def spider_closed(self, spider):
        """爬虫关闭时断开所有连接"""
        if self.session_page:
            logger.info("关闭 SessionPage")
            self.session_page.close()
            self.session_page = None
        if self.chromium_page:
            logger.info("断开 ChromiumPage 连接")
            self.chromium_page.quit()
            self.chromium_page = None
