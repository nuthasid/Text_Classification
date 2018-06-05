import scrapy
from datetime import datetime
from scrapy.utils.markup import remove_tags
from scrapy.http import FormRequest
from urlparse import urljoin
from scrapy.exceptions import CloseSpider

class TDRISpider(scrapy.Spider):
    name = "proxy"

    def start_requests(self):
        url = "https://free-proxy-list.net"

        yield scrapy.Request(url=url, callback=self.parse_list)
    
    def clean_tag(self,s):
        return ' '.join([x.strip() for x in remove_tags(s).split()])

    def parse_list(self, response):

        ip_sets = [i.xpath('./td/text()')[:3].extract() for i in response.xpath('.//table[@id="proxylisttable"]/tbody/tr')]
        ips = [ "%s:%s" % (i[0],i[1]) for i in ip_sets if i[2] == 'TH']
        proxies = [{'http':'http://' + ip, 'https':'https://' + ip} for ip in ips]
        
        for proxy in  proxies:
            yield proxy
