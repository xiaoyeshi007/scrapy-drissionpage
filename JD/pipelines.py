"""
商品数据处理管道
"""
import json
import os
import pymysql
import logging

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



class MysqlPipeline:
    """优化版 MySQL Pipeline：批量提交 + 异常处理 + 配置外置"""

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            host=crawler.settings.get('MYSQL_HOST', '127.0.0.1'),
            user=crawler.settings.get('MYSQL_USER', 'root'),
            password=crawler.settings.get('MYSQL_PASSWORD', ''),
            db=crawler.settings.get('MYSQL_DB', 'jd'),
            batch_size=crawler.settings.getint('MYSQL_BATCH_SIZE', 50),
        )

    def __init__(self, host, user, password, db, batch_size):
        self.host = host
        self.user = user
        self.password = password
        self.db = db
        self.batch_size = batch_size
        self.items_buffer = []

    def open_spider(self, spider):
        try:
            self.connection = pymysql.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                db=self.db,
                charset='utf8mb4',
            )
            self.cursor = self.connection.cursor()
            spider.logger.info("MySQL 连接成功: %s/%s", self.host, self.db)
        except pymysql.MySQLError as e:
            spider.logger.error("MySQL 连接失败: %s", e)
            raise

    def process_item(self, item, spider):
        self.items_buffer.append(dict(item))
        if len(self.items_buffer) >= self.batch_size:
            self._flush()
        return item

    def _flush(self):
        if not self.items_buffer:
            return
        try:
            data = self.items_buffer[0]
            keys = ', '.join(data.keys())
            placeholders = ', '.join(['%s'] * len(data))
            sql = f"INSERT INTO book ({keys}) VALUES ({placeholders})"
            self.cursor.executemany(sql, [tuple(d.values()) for d in self.items_buffer])
            self.connection.commit()
            logger.debug("批量插入 %d 条数据", len(self.items_buffer))
        except pymysql.MySQLError as e:
            self.connection.rollback()
            logger.error("批量插入失败，已回滚: %s", e)
        finally:
            self.items_buffer.clear()

    def close_spider(self, spider):
        self._flush()
        self.connection.close()
        logger.info("MySQL 连接已关闭")