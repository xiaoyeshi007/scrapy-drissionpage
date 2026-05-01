"""
商品数据处理管道
"""
import json
import os

from itemadapter import ItemAdapter


class JdPipeline:
    """去重 + 数据清洗"""

    seen_skus = set()

    def process_item(self, item, spider=None):
        adapter = ItemAdapter(item)

        # 去重
        sku = adapter.get("sku_id", "")
        if sku in self.seen_skus:
            from scrapy.exceptions import DropItem
            raise DropItem(f"Duplicate SKU: {sku}")
        self.seen_skus.add(sku)

        # 清洗价格：去掉 ¥ 符号，保留纯数字
        price = adapter.get("price", "")
        if price and price != "询价":
            cleaned = price.replace("¥", "").replace("￥", "").strip()
            adapter["price"] = cleaned if cleaned else price

        return item


class MYSQLExportPipeline:
    """导入MYSQL数据库"""

    def open_spider(self, spider=None):
        self.items = []

    def process_item(self, item, spider=None):
        self.items.append(ItemAdapter(item).asdict())
        return item

    def close_spider(self, spider=None):
        output_dir = os.path.dirname(os.path.dirname(__file__))
        output_path = os.path.join(output_dir, "jd_products.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.items, f, ensure_ascii=False, indent=2)
        count = len(self.items)
        if spider:
            spider.logger.info("Saved %d products to %s", count, output_path)
