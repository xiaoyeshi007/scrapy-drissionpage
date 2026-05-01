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
    "Referer": "https://list.jd.com/",
}

# 下载中间件 — 启用 DrissionPage
DOWNLOADER_MIDDLEWARES = {
    "JD.middlewares.DrissionPageMiddleware": 543,
}

# 管道
ITEM_PIPELINES = {
    "JD.pipelines.JdPipeline": 200,         # 去重 + 清洗
    "JD.pipelines.MYSQLExportPipeline": 300,  # MYSQL 导出
    #""  #导入mMYSQL数据库
}

# 编码
FEED_EXPORT_ENCODING = "utf-8"

# 日志级别
LOG_LEVEL = "INFO"
