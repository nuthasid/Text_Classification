import scrapy
from datetime import datetime
from scrapy.utils.markup import remove_tags
from scrapy.http import FormRequest
from scrapy.exceptions import CloseSpider
from urlparse import urljoin
from hasher import hash_dn
from sqlalchemy import exc

class TDRISpider(scrapy.Spider):

    custom_settings = {
        'HTTPPROXY_ENABLED': True 
    }
    name        = "nationejob"
    page        = 1
    web_id      = 11

    logger      = None
    sqllogger   = None
    html_path   = None
    max_page    = 9999
    use_proxy   = False
    proxies     = []
    location    = {}

    repeat_count     = 0
    repeat_threshold = 3

    error_count      = 0
    error_threshold  = 5

    killed      = 0

    def start_requests(self):
        url = "http://www.nationejobs.com/search/search_thai.php?page={num}&key={key}"
        key = self.key if hasattr(self,'key') else ''

        formatted_url = url.format(key=key, num=self.page)
        
        yield scrapy.Request(url=formatted_url, callback=self.parse_list)
    
    def clean_tag(self,s):
        return ' '.join([x.strip() for x in remove_tags(s).split()])

    def parse_list(self, response):

        if self.killed:
            raise CloseSpider("Spider already died.")

        jobs = response.xpath('//table[@class="table1"]/tr[not(@class)]')
        for job in jobs:
            job_url = job.xpath('./td[not(@class)]/a/@href')[0].extract()[2:]
            job_url = urljoin('http://www.nationejobs.com',job_url)
            self.location[job_url] = job.xpath('./td[@class]/text()').extract()[-2].encode('utf8')
            if self.use_proxy:
                proxy = choice(self.proxies)
                self.logger.info('[ JobPageRequest ] {url} with proxy {proxy}'.format(url=job_url, proxy=proxy))
                yield scrapy.Request(job_url, callback=self.parse_detail , meta={'proxy': proxy})
            else:
                self.logger.info('[ JobPageRequest ] {url}'.format(url=job_url))
                yield scrapy.Request(job_url, callback=self.parse_detail)

        last_page = max([int(i) for i in response.xpath('.//div[@class="align_center"]/a/text()').extract()])
        selected  = int(response.xpath('.//div[@class="align_center"]/a[@class="selected"]/text()').extract_first())
        self.page = selected + 1
        if self.page > last_page:
            next_url = ''
        else:
            next_url = "http://www.nationejobs.com/search/search_thai.php?page={num}&key=".format(num=self.page)

        if next_url and self.page <= self.max_page:
            self.logger.info('[ JobListRequest ] {url}'.format(url=next_url))
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
                self.logger.error('[ JobPageRequestException ] {url}'.format(url=response.url))
            if self.use_proxy:
                proxy = choice(self.proxies)
                self.logger.info('[ JobPageRetry ] {url} with proxy {proxy}'.format(url=response.url, proxy=proxy))
                yield scrapy.Request(response.url, callback=self.parse_detail , meta={'proxy': proxy})
            else:
                self.logger.info('[ JobPageRetry ] {url}'.format(url=response.url))
                yield scrapy.Request(response.url, callback=self.parse_detail)

        self.error_count = 0

        try:
            html_path = self.html_path.format(dttm=datetime.now().strftime('%Y%m%d_%H%M%S'))
            with open(html_path, 'w') as f:
                f.write(response.text.encode('utf-8'))
                self.logger.info('[ HTMLArchived ] {url}'.format(url=response.url))
        except Exception as e:
            self.logger.error('[ HTMLArchiveException ] {url}'.format(url=response.url))

        try:
            ret = {}
            ret['pos']       = response.xpath('//th[@class="qualification_positionname align_left"]/a/text()').extract_first()
            ret['company']   = response.xpath('//table[@class="table_qualification"]/tr[@class="header"]/th[@class="corner"]/div/div/div/text()').extract_first()
            ret['pdate']     = response.xpath('//th[@class="qualification_postdate align_right"]/text()').extract_first()
            #contents         = response.xpath('//table[@class="table_qualification"]/tr[not(@class)]/td[@class="line_left line_right"]')[1].xpath('./ul')
            #ret['desc']      = '|'.join(contents[0].xpath('./li//text()').extract())
            #ret['req']       = '|'.join(contents[1].xpath('./li//text()').extract())
            ret['desc']      = self.clean_tag(response.xpath('//table[@class="table_qualification"]/tr[not(@class)]/td[@class="line_left line_right"]')[1].extract())
            ret['loc']       = self.location[response.url]
            
            del self.location[response.url]

            for key in ret.keys():
                if ret[key]:
                    try:
                        ret[key] = ret[key].strip().encode('utf-8')
                    except:
                        ret[key] = ret[key].strip()

            if ret['pdate'].split()[-1] == "17":
                    self.logger.info("[ JobEndReached ] 2017 reached")
                    raise CloseSpider("2017 reached")

            _hash = hash_dn(ret['desc'],ret['company'])

            try:
                self.sqllogger.log_crawled_page(
                    hash_code    = _hash,
                    position     = ret['pos'],
                    employer     = ret['company'],
                    exp          = '',
                    salary       = '',
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
            self.logger.error('[ JobDetailException ] {url} {html_path} {e}'.format(url=response.url.encode('utf-8'),html_path=html_path.encode('utf-8'),e=e))
            self.sqllogger.log_error_page(
                hash_code     = hash_dn(response.url.encode('utf-8'),datetime.now().strftime('%Y%m%d%H%M%S')),
                web_id        = self.web_id,
                url           = response.url.encode('utf-8'),
                meta          = response.meta,
                html_path     = html_path,
                crawl_time    = datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                job_status    = 'FAILED',
                error_message = e
            )
