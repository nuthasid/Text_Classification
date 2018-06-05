import scrapy
from datetime import datetime
from scrapy.utils.markup import remove_tags
from scrapy.http import FormRequest
from urlparse import urljoin
from scrapy.exceptions import CloseSpider
from hasher import hash_dn
from sqlalchemy import exc

class TDRISpider(scrapy.Spider):

    custom_settings = {
        'HTTPPROXY_ENABLED': True 
    }
    name        = "thaibestjobs"
    page        = 1
    web_id      = 12

    logger      = None
    sqllogger   = None
    html_path   = None
    max_page    = 9999
    use_proxy   = False
    proxies     = []

    repeat_count     = 0
    repeat_threshold = 3

    error_count      = 0
    error_threshold  = 5

    killed      = 0

    def start_requests(self):
        url = "http://www.thaibestjobs.com/job/{page}/"

        formatted_url = url.format(page=self.page)
        
        yield scrapy.Request(url=formatted_url, callback=self.parse_list)
    
    def clean_tag(self,s):
        return ' '.join([x.strip() for x in remove_tags(s).split()])

    def parse_list(self, response):

        if self.killed:
            raise CloseSpider("Spider already died.")

        jobs = response.xpath('.//div[@id="content-frame"]/div/div[@class="box-left"]/table[@style="width:640px;"]/tr/td/b/a/@href').extract()

        if not jobs:
            self.logger.info("[ JobEndReached ] All jobs have been crawled.")
            CloseSpider("all jobs have been crawled")

        for job_url in jobs:
            if self.use_proxy:
                proxy = choice(self.proxies)
                self.logger.info('[ JobPageRequest ] {url} with proxy {proxy}'.format(url=job_url.encode('utf-8'), proxy=proxy))
                yield scrapy.Request(job_url, callback=self.parse_detail , meta={'proxy': proxy})
            else:
                self.logger.info('[ JobPageRequest ] {url}'.format(url=job_url.encode('utf-8')))
                yield scrapy.Request(job_url, callback=self.parse_detail)

        next_url = response.xpath(u'.//a[@class="linkpage" and text()="\u203a"]/@href').extract_first()

        if next_url and self.page <= self.max_page:
            self.page += 1
            self.logger.info('[ JobListRequest ] {url}'.format(url=next_url.encode('utf-8')))
            yield scrapy.Request(url=next_url, callback=self.parse_list)
        elif next_url:
            self.logger.info('[ JobEndReached ] Max page reached at # %d' % self.max_page)
        else:
            self.logger.info('[ JobEndReached ] Last page reached at # %d' % self.page)


    def parse_detail(self, response):

        if self.killed:
            raise CloseSpider("Spider already died.")

        if not response.body:
            self.error_count += 1

            if self.error_count == 5:
                self.logger.error('[ JobPageRequestException ] {url}'.format(url=response.url.encode('utf-8')))
                self.sqllogger.log_error_page(
                    hash_code    = hash_dn(response.url.encode('utf-8'),datetime.now().strftime('%Y%m%d%H%M%S')),
                    web_id       = self.web_id,
                    url          = response.url.encode('utf-8'),
                    meta         = response.meta,
                    html_path    = html_path,
                    crawl_time   = datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    job_status   = 'FAILED',
                    error_message= "Empty request's response"
                )
                yield None
                return
            if self.use_proxy:
                proxy = choice(self.proxies)
                self.logger.info('[ JobPageRetry ] {url} with proxy {proxy}'.format(url=response.url.encode('utf-8'), proxy=proxy))
                yield scrapy.Request(response.url, callback=self.parse_detail , meta={'proxy': proxy})
                return
            else:
                self.logger.info('[ JobPageRetry ] {url}'.format(url=response.url.encode('utf-8')))
                yield scrapy.Request(response.url, callback=self.parse_detail)
                return
        self.error_count = 0

        try:
            html_path = self.html_path.format(dttm=datetime.now().strftime('%Y%m%d_%H%M%S'))
            with open(html_path, 'w') as f:
                f.write(response.text.encode('utf-8'))
                self.logger.info('[ HTMLArchived ] {url}'.format(url=response.url.encode('utf-8')))
        except Exception as e:
            self.logger.error('[ HTMLArchiveException ] {url}'.format(url=response.url.encode('utf-8')))

        try:
            ret = {}

            ret['company'] = response.xpath('.//div[@id="content-frame"]/div[@id="content-frame-2col-1"]/h3/text()').extract_first()
            ret['pos']     = response.xpath('.//div[@id="content-frame"]/div[@id="content-frame-2col-1"]/div')[1].xpath('./table/tr')[0].xpath('./td/strong/font/text()').extract_first()
            ret['amnt']    = response.xpath('.//div[@id="content-frame"]/div[@id="content-frame-2col-1"]/div')[1].xpath('./table/tr')[1].xpath('./td/text()')[1].extract()
            ret['sal']     = response.xpath('.//div[@id="content-frame"]/div[@id="content-frame-2col-1"]/div')[1].xpath('./table/tr')[2].xpath('./td/text()')[1].extract()
            ret['desc']    = '|'.join([i.strip() for i in response.xpath('.//div[@id="content-frame"]/div[@id="content-frame-2col-1"]/div')[1].xpath('./table/tr')[3].xpath('./td/text()').extract()][1:])
            ret['qual']    = '|'.join([i.strip() for i in response.xpath('.//div[@id="content-frame"]/div[@id="content-frame-2col-1"]/div')[1].xpath('./table/tr')[4].xpath('./td/text()').extract()][1:])
            ret['benef']   = '|'.join([i.strip() for i in response.xpath('.//div[@id="content-frame"]/div[@id="content-frame-2col-1"]/div')[1].xpath('./table/tr')[5].xpath('./td/text()').extract()][1:])
            ret['loc']     = '|'.join([i.strip() for i in response.xpath('.//div[@id="content-frame"]/div[@id="content-frame-2col-1"]/div')[1].xpath('./table/tr')[7].xpath('./td/text()').extract()][1:])
            ret['loc_det'] = '|'.join([i.strip() for i in response.xpath('.//div[@id="content-frame"]/div[@id="content-frame-2col-1"]/div')[1].xpath('./table/tr')[6].xpath('./td/text()').extract()][1:])
            ret['pdate']   = response.xpath('.//div[@id="content-frame"]/div[@id="content-frame-2col-1"]/div')[1].xpath('./table/tr')[10].xpath('./td/font/text()').extract_first()

            for key in ret.keys():
                if ret[key]:
                    ret[key] = ret[key].strip().encode('utf-8')

            if ret['pdate'].split()[0].split('-')[0] == "2017":
                self.logger.info("[ JobEndReached ] 2017 reached")
                raise CloseSpider("2017 reached")

            _hash = hash_dn(ret['desc'],ret['company'])

            try:
                self.sqllogger.log_crawled_page(
                    hash_code    = hash_dn(ret['desc'],ret['company']),
                    position     = ret['pos'],
                    employer     = ret['company'],
                    exp          = '',
                    salary       = ret['sal'],
                    location     = ret['loc'],
                    web_id       = self.web_id,
                    url          = response.url.encode('utf-8'),
                    meta         = response.meta,
                    html_path    = html_path,
                    crawl_time   = datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    post_time    = ret['pdate'],
                    job_status   = 'SUCCESS',
                    error_message= ''
                )
                self.logger.info('[ RDSLogged ] {url}'.format(url=response.url.encode('utf-8')))
            except exc.IntegrityError as e:
                if e.orig.args[0] == 1062 and self.repeat_count >= self.repeat_threshold:
                    self.logger.info("[ JobEndReached ] crawled record reached exceeding threshold")
                    self.killed = 1
                    raise CloseSpider("Crawled record reached")
                elif e.orig.args[0] == 1062 and self.repeat_count < self.repeat_threshold:
                    self.repeat_count += 1
                    self.logger.info("[ JobRepeat ] crawled record found within threshold #%d" % self.repeat_count)
                    yield None
                    return
                else:
                    raise e
            self.repeat_count = 0


            yield ret
            
        except CloseSpider as e:
            raise CloseSpider(e.message)

        except Exception as e:
            self.logger.error('[ JobDetailException ] {url} {html_path} {e}'.format(url=response.url.encode('utf-8'),html_path=html_path.encode('utf-8'), e=e))
            self.sqllogger.log_error_page(
                hash_code    = hash_dn(response.url.encode('utf-8'),datetime.now().strftime('%Y%m%d%H%M%S')),
                web_id       = self.web_id,
                url          = response.url.encode('utf-8'),
                meta         = response.meta,
                html_path    = html_path,
                crawl_time   = datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                job_status   = 'FAILED',
                error_message= e
            )
