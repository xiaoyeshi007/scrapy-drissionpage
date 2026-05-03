# Scrapy settings for JD project

BOT_NAME = "JD"

SPIDER_MODULES = ["JD.spiders"]
NEWSPIDER_MODULE = "JD.spiders"

# 不遵守 robots.txt
ROBOTSTXT_OBEY = False

# 并发设为 1
CONCURRENT_REQUESTS = 1
CONCURRENT_REQUESTS_PER_DOMAIN = 1
# 请求间隔，避免触发滑块验证
DOWNLOAD_DELAY = 2

# 请求头
DEFAULT_REQUEST_HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://search.jd.com/",
}

# 下载中间件 — 启用 DrissionPage
DOWNLOADER_MIDDLEWARES = {
    "JD.middlewares.DrissionPageMiddleware": 543,
}

# 管道
ITEM_PIPELINES = {
    "JD.pipelines.JdPipeline": 200,         # 去重 + 清洗
    "JD.pipelines.MysqlPipeline": 300,      # 导入MYSQL
}
                                            #数据库连接设置
MYSQL_HOST = '127.0.0.1'
MYSQL_USER = 'root'
MYSQL_PASSWORD = '914915'
MYSQL_DB = 'book'
MYSQL_BATCH_SIZE = 50
# 爬取控制
CATEGORY_LIMIT = 0     # 爬取分类数，0 = 全部分类
MAX_PAGES = 100        # 每个分类最大翻页数，0 = 不限

# 编码
FEED_EXPORT_ENCODING = "utf-8"

# 日志级别
LOG_LEVEL = "INFO"
