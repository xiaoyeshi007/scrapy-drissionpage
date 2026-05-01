import scrapy


class JdItem(scrapy.Item):
    sku_id = scrapy.Field()           # SKU ID
    name = scrapy.Field()             # 商品名称
    price = scrapy.Field()            # 价格
    shop = scrapy.Field()             # 店铺
    sales = scrapy.Field()            # 销量
    likes = scrapy.Field()            # 种草数
    image = scrapy.Field()            # 图片链接
    link = scrapy.Field()             # 商品链接
    big_category = scrapy.Field()     # 大分类
    small_category = scrapy.Field()   # 小分类
