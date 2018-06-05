from scrapy import spiderloader, signals
from scrapy.utils import project
from scrapy.crawler import CrawlerProcess

'''Get Proxy IP from a free-proxy website'''

proxies = []
class ProxyPipeline(object):
    def process_item(self, item, spider):
        proxies.append(item)

settings = project.get_project_settings()
spider_loader = spiderloader.SpiderLoader.from_settings(settings)


results = []
def spider_closed(spider):
    print results

# get proxy IPs
def get_proxy():
    settings.overrides['ITEM_PIPELINES'] = {'get_proxy.ProxyPipeline':1}
    crawler_process = CrawlerProcess(settings)
    proxy_spider = spider_loader.load("proxy")
    crawler_process.crawl(proxy_spider)
    for crawler in crawler_process.crawlers:
        crawler.signals.connect(spider_closed, signal=signals.spider_closed)

    crawler_process.start()

    return proxies