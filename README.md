# JD Book Spider

> **免责声明：本项目仅供学习交流使用，请勿用于任何商业或非法用途。使用本项目产生的一切后果由使用者自行承担。**

基于 Scrapy + DrissionPage 的京东图书数据采集系统，通过浏览器自动化方式采集京东图书分类下的商品信息，支持自动翻页、验证码处理，并将数据持久化到 MySQL。

## 项目结构

```
JD/
├── scrapy.cfg                  # Scrapy 部署配置
├── jd_products.json            # 采集结果示例
└── JD/
    ├── settings.py             # 全局配置
    ├── items.py                # 数据模型
    ├── middlewares.py          # DrissionPage 浏览器中间件
    ├── pipelines.py            # 去重 + MySQL 写入管道
    └── spiders/
        └── jdbook.py           # 爬虫主逻辑
```

## 技术架构

```
Spider (jdbook)
  -> 通过分类API获取类目，生成搜索请求
Downloader Middleware (DrissionPageMiddleware)
  -> 拦截搜索请求，用浏览器渲染页面
  -> 自动滚动加载 + 自动翻页
  -> 提取 body 内容，合并多页 HTML
Spider Callback (parse_book_list)
  -> CSS 选择器提取商品数据
Pipeline
  -> JdPipeline:   SKU 内存去重
  -> MysqlPipeline: 批量写入 MySQL
```

## 环境依赖

- Python 3.10+
- Scrapy
- DrissionPage 4.x
- lxml
- pymysql
- Microsoft Edge（需开启远程调试模式）

## 使用方法

### 1. 启动 Edge 调试模式

```bash
msedge.exe --remote-debugging-port=9222
```

### 2. 运行爬虫

```bash
scrapy crawl jdbook
```

### 3. 查看数据

采集结果会自动写入 MySQL `book` 表。同时项目根目录会生成 `jd_products.json` 备份文件。

## 配置说明（settings.py）

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `CATEGORY_LIMIT` | 爬取分类数，0=全部 | 0 |
| `MAX_PAGES` | 每个分类最大翻页数，0=不限 | 100 |
| `DOWNLOAD_DELAY` | 请求间隔（秒） | 2 |
| `MYSQL_HOST` | MySQL 主机 | 127.0.0.1 |
| `MYSQL_DB` | 数据库名 | book |
| `MYSQL_BATCH_SIZE` | 批量插入条数 | 30 |

## 多实例并行采集

通过启动多个 Edge 调试端口实例，配合多个 Scrapy 进程并行采集不同分类，可以显著提高采集效率。

### 1. 启动多个 Edge 实例（不同调试端口）

```bash
# 实例1 - 端口 9222
msedge.exe --remote-debugging-port=9222 --user-data-dir="C:\edge_profile_1"

# 实例2 - 端口 9223
msedge.exe --remote-debugging-port=9223 --user-data-dir="C:\edge_profile_2"
```

每个实例需要独立的 `--user-data-dir`，否则端口会冲突。

### 2. 修改中间件地址配置

`middlewares.py` 中的 `EDGE_ADDRESS` 控制连接的浏览器地址，不同实例使用不同端口：

```python
EDGE_ADDRESS = "127.0.0.1:9222"  # 实例1
EDGE_ADDRESS = "127.0.0.1:9223"  # 实例2
```

### 3. 按分类拆分任务运行

通过 `CATEGORY_LIMIT` 控制每个进程采集的分类范围，将全量分类均匀分配给多个实例：

```bash
# 终端1 - 采集前 10 个分类
scrapy crawl jdbook

# 终端2 - 采集后续分类
scrapy crawl jdbook
```

也可以通过自定义参数传入：

```bash
scrapy crawl jdbook -a start_category=0 -a end_category=10
scrapy crawl jdbook -a start_category=10 -a end_category=20
```

> **注意：** 多实例并行时，建议每个实例使用独立的 MySQL 表或数据库，避免写入冲突。采集完成后再合并数据。
