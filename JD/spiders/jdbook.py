"""
京东图书搜索爬虫 — Scrapy + DrissionPage
通过分类API获取类目，用搜索引擎采集商品数据
翻页逻辑由 middleware 处理

用法:
    scrapy crawl jdbook
"""
import re
import json
import scrapy

from JD.items import JdItem

# 京东搜索结果页 CSS 选择器 (React class 哈希值，用 *= 匹配)
SEL_NAME = 'span[title]'                                     # 商品名称(title属性)
SEL_PRICE_CONTAINER = '[class*="_price_65r2s"]'              # 价格容器
SEL_SHOP = '[class*="_limit_1skn4"]'                         # 店铺名
SEL_SALES = '[class*="goods_volume"] span[title]'            # 销量


class JdbookSpider(scrapy.Spider):
    name = "jdbook"
    allowed_domains = ["search.jd.com", "pjapi.jd.com"]

    custom_settings = {
        "CONCURRENT_REQUESTS": 1,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.category_limit = 0

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        spider.category_limit = crawler.settings.getint('CATEGORY_LIMIT', 0)
        return spider

    def start_requests(self):
        yield scrapy.Request(
            url="https://pjapi.jd.com/book/sort?source=bookSort",
            callback=self.parse_categories,
            dont_filter=True,
        )

    def parse_categories(self, response):
        """解析分类API，为每个二级类目生成搜索请求"""
        try:
            data = json.loads(response.text)["data"]
        except (json.JSONDecodeError, KeyError):
            self.logger.error("分类API获取失败")
            return

        count = 0
        for cat1 in data:
            cat1_name = cat1["categoryName"]
            for cat2 in cat1.get("sonList", []):
                cat2_name = cat2["categoryName"]
                url = f"https://search.jd.com/Search?keyword={cat2_name}&enc=utf-8"

                self.logger.info("分类: %s > %s", cat1_name, cat2_name)
                yield scrapy.Request(
                    url=url,
                    callback=self.parse_book_list,
                    meta={"big_category": cat1_name, "small_category": cat2_name},
                )

                count += 1
                if self.category_limit and count >= self.category_limit:
                    self.logger.info("已达到分类限制: %d 个", self.category_limit)
                    return

    def parse_book_list(self, response):
        """解析搜索结果页，提取商品数据"""
        big_cat = response.meta.get("big_category", "")
        small_cat = response.meta.get("small_category", "")

        cards = response.css("div[data-sku]")
        seen = set() #sku列表，后续去重
        count = 0

        for card in cards:
            sku = card.attrib.get("data-sku", "")
            if not sku or sku in seen:
                continue
            seen.add(sku)

            # 商品名称
            name = ""
            for el in card.css(SEL_NAME):
                t = el.attrib.get("title", "")
                if len(t) > 3:
                    name = t
                    break

            # 价格
            price = "询价"
            price_els = card.css(SEL_PRICE_CONTAINER)
            if price_els:
                all_text = "".join(price_els[0].css("::text").getall())
                all_text = all_text.replace("¥", "").replace("￥", "").strip()
                nums = re.findall(r'\d+', all_text)
                if nums:
                    price = nums[0] + "." + nums[1] if len(nums) >= 2 else nums[0]

            # 店铺
            shop_els = card.css(SEL_SHOP + "::text")
            shop = shop_els.get("").strip() if shop_els else ""

            # 销量
            sales_els = card.css(SEL_SALES)
            sales = sales_els.attrib.get("title", "") if sales_els else ""

            if name:
                yield JdItem(
                    sku_id=sku,
                    name=name,
                    price=price,
                    shop=shop,
                    sales=sales,
                    link=f"https://item.jd.com/{sku}.html",
                    big_category=big_cat,
                    small_category=small_cat,
                )
                count += 1

        self.logger.info("[%s > %s] 提取 %d 个商品", big_cat, small_cat, count)
