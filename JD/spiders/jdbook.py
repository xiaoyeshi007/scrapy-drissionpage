"""
京东图书列表页爬虫 — Scrapy + DrissionPage
通过 Edge 浏览器渲染 React 列表页，提取商品数据

用法:
    scrapy crawl jdbook                       # 全部分类
    scrapy crawl jdbook -a limit=3            # 只爬前 3 个分类
    scrapy crawl jdbook -a cat=1713,3258,3297 # 指定分类
"""
import scrapy
import json

from JD.items import JdItem

# 京东列表页 React CSS 选择器 (class 名含哈希值，用 *= 匹配前缀)
SEL_TEXT = '[class*="_text_1k2fi"]'                   # 商品名称
SEL_PRICE = '[class*="_price_1agky"]'                 # 价格
SEL_SHOP = '[class*="_limit_1phiu"]'                  # 店铺
SEL_SALES = '[class*="goods_volume"] span[title]'     # 销量
SEL_LIKES = '[class*="_tml_1xkku"]'                   # 种草数
SEL_IMG = 'img[class*="_img"][data-src]'              # 图片


class JdbookSpider(scrapy.Spider):
    name = "jdbook"
    allowed_domains = ["pjapi.jd.com", "list.jd.com"]

    # 命令行参数: -a limit=5  -a cat=1713,3258,3297
    custom_settings = {
        "CONCURRENT_REQUESTS": 1,
    }
    #初始化与参数支持
    def __init__(self, *args, limit=None, cat=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.limit = int(limit) if limit else None
        self.single_cat = cat  # 指定单个分类

    def start_requests(self):
        if self.single_cat:
            # 直接爬指定分类
            url = f"https://list.jd.com/list.html?cat={self.single_cat}"
            yield scrapy.Request(
                url=url,
                callback=self.parse_book_list,
                meta={"big_category": "指定分类", "small_category": self.single_cat},
            )
        else:
            # 从分类 API 获取类目
            yield scrapy.Request(
                url="https://pjapi.jd.com/book/sort?source=bookSort",
                callback=self.parse_categories,
                dont_filter=True,
            )

    def parse_categories(self, response):
        """解析分类 API，为每个二级类目生成列表页请求"""
        try:
            data = json.loads(response.text)["data"]
        except (json.JSONDecodeError, KeyError):
            self.logger.error("API获取失败")
            return

        def build_url(*ids):
            cat_str = ",".join(str(int(i)) for i in ids)
            return f"https://list.jd.com/list.html?cat={cat_str}"

        count = 0
        for cat1 in data:
            cat1_id = cat1["categoryId"]
            cat1_name = cat1["categoryName"]

            for cat2 in cat1.get("sonList", []):
                cat2_id = cat2["categoryId"]
                cat2_name = cat2["categoryName"]
                url = build_url(cat1_id, cat2_id)

                self.logger.info("Category: %s > %s", cat1_name, cat2_name)
                yield scrapy.Request(
                    url=url,
                    callback=self.parse_book_list,
                    meta={
                        "big_category": cat1_name,
                        "small_category": cat2_name,
                    },
                )

                count += 1
                if self.limit and count >= self.limit:
                    self.logger.info("Reached limit of %d categories", self.limit)
                    return

    def parse_book_list(self, response):
        """解析列表页 HTML，提取商品数据"""
        big_cat = response.meta.get("big_category", "")
        small_cat = response.meta.get("small_category", "")

        items = response.css("div[data-sku]")
        seen = set()
        count = 0

        for item in items:
            sku = item.attrib.get("data-sku", "")
            if not sku or sku in seen:
                continue
            seen.add(sku)

            def safe_text(sel):
                els = item.css(sel)
                if not els:
                    return ""
                return "".join(els[0].css("::text").getall()).replace("\n", "").strip()

            def safe_attr(sel, attr):
                els = item.css(sel)
                return els[0].attrib.get(attr, "") if els else ""

            name = safe_text(SEL_TEXT)
            price = safe_text(SEL_PRICE).replace("\n", "") or "询价"
            shop = safe_text(SEL_SHOP)
            sales = safe_attr(SEL_SALES, "title")
            likes = safe_attr(SEL_LIKES, "title")

            image = safe_attr(SEL_IMG, "data-src")
            if not image:
                image = safe_attr(SEL_IMG, "src")
            if image.startswith("//"):
                image = "https:" + image

            if name:
                yield JdItem(
                    sku_id=sku,
                    name=name,
                    price=price,
                    shop=shop,
                    sales=sales,
                    likes=likes,
                    image=image,
                    link=f"https://item.jd.com/{sku}.html",
                    big_category=big_cat,
                    small_category=small_cat,
                )
                count += 1

        self.logger.info(
            "Extracted %d products from %s > %s",
            count, big_cat, small_cat,
        )
