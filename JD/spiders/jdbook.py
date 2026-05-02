"""
京东图书搜索爬虫 — Scrapy + DrissionPage
通过 Edge 浏览器渲染搜索结果页，提取商品数据，支持翻页

用法:
    scrapy crawl jdbook                             # 全部分类
    scrapy crawl jdbook -a limit=3                  # 只爬前 3 个分类
    scrapy crawl jdbook -a keyword=小说             # 搜索指定关键词
    scrapy crawl jdbook -a keyword=小说 -a pages=3  # 搜索关键词并爬3页
"""
import scrapy

from JD.items import JdItem

# 京东搜索结果页 CSS 选择器 (React class 哈希值，用 *= 匹配)
SEL_NAME = 'span[title]'                                     # 商品名称(title属性)
SEL_PRICE_CONTAINER = '[class*="_price_65r2s"]'              # 价格容器
SEL_SHOP = '[class*="_limit_1skn4"]'                         # 店铺名
SEL_SALES = '[class*="goods_volume"] span[title]'            # 销量
SEL_IMG = 'img[class*="_img"][data-src]'                     # 商品图片

# 图书搜索关键词列表
BOOK_KEYWORDS = [
    "小说", "文学", "青春文学", "中国当代小说", "外国小说",
    "侦探推理", "科幻", "武侠", "言情", "历史小说",
    "童书", "绘本", "教育", "哲学", "心理学",
    "经济管理", "计算机", "科普", "传记", "艺术",
]


class JdbookSpider(scrapy.Spider):
    name = "jdbook"
    allowed_domains = ["search.jd.com", "pjapi.jd.com"]

    custom_settings = {
        "CONCURRENT_REQUESTS": 1,
    }

    def __init__(self, *args, keyword=None, limit=None, pages=10, **kwargs):
        super().__init__(*args, **kwargs)
        self.keyword = keyword           # 指定搜索关键词
        self.limit = int(limit) if limit else None  # 限制关键词数
        self.max_pages = int(pages)      # 每个关键词最大翻页数

    def start_requests(self):
        if self.keyword:
            # 搜索指定关键词
            url = self._build_search_url(self.keyword)
            yield scrapy.Request(
                url=url,
                callback=self.parse_book_list,
                meta={"keyword": self.keyword, "page": 1,
                      "big_category": "搜索", "small_category": self.keyword},
            )
        else:
            # 用预设关键词列表搜索
            keywords = BOOK_KEYWORDS[:self.limit] if self.limit else BOOK_KEYWORDS
            for kw in keywords:
                url = self._build_search_url(kw)
                self.logger.info("搜索关键词: %s", kw)
                yield scrapy.Request(
                    url=url,
                    callback=self.parse_book_list,
                    meta={"keyword": kw, "page": 1,
                          "big_category": "图书", "small_category": kw},
                )

    @staticmethod
    def _build_search_url(keyword):
        return f"https://search.jd.com/Search?keyword={keyword}&enc=utf-8"

    def parse_book_list(self, response):
        """解析搜索结果页 HTML，提取商品数据"""
        keyword = response.meta.get("keyword", "")
        page_num = response.meta.get("page", 1)
        big_cat = response.meta.get("big_category", "")
        small_cat = response.meta.get("small_category", "")

        cards = response.css("div[data-sku]")
        seen = set()
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

            # 价格：从价格容器中提取所有文本，解析整数和小数
            price = "询价"
            price_els = card.css(SEL_PRICE_CONTAINER)
            if price_els:
                all_text = "".join(price_els[0].css("::text").getall())
                all_text = all_text.replace("¥", "").replace("￥", "").strip()
                # 提取数字部分
                import re
                nums = re.findall(r'\d+', all_text)
                if nums:
                    if len(nums) >= 2:
                        price = nums[0] + "." + nums[1]
                    else:
                        price = nums[0]

            # 店铺
            shop_els = card.css(SEL_SHOP + "::text")
            shop = shop_els.get("").strip() if shop_els else ""

            # 销量
            sales_els = card.css(SEL_SALES)
            sales = sales_els.attrib.get("title", "") if sales_els else ""

            # 图片
            img_els = card.css(SEL_IMG)
            image = ""
            if img_els:
                image = img_els.attrib.get("data-src", "") or img_els.attrib.get("src", "")
            if image and image.startswith("//"):
                image = "https:" + image

            if name:
                yield JdItem(
                    sku_id=sku,
                    name=name,
                    price=price,
                    shop=shop,
                    sales=sales,
                    likes="",
                    image=image,
                    link=f"https://item.jd.com/{sku}.html",
                    big_category=big_cat,
                    small_category=small_cat,
                )
                count += 1

        self.logger.info(
            "第%d页 [%s] 提取 %d 个商品",
            page_num, keyword or small_cat, count,
        )

        # 翻页：有商品且未达到最大页数则继续
        if count > 0 and page_num < self.max_pages:
            yield scrapy.Request(
                url=response.url,
                callback=self.parse_book_list,
                meta={
                    "keyword": keyword,
                    "page": page_num + 1,
                    "big_category": big_cat,
                    "small_category": small_cat,
                    "click_next_page": True,
                },
                dont_filter=True,
            )
