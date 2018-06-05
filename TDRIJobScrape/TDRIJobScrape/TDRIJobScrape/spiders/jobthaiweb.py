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
        'HTTPPROXY_ENABLED': True ,
        'USER_AGENT':"Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:58.0) Gecko/20100101 Firefox/58.0"
    }
    name        = "jobthaiweb"
    page        = 1
    web_id      = 9

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

        url = "http://jobthaiweb.com/joblist_new.php?typejob=&jobcity=&jobarea=&key=&page={page}"
        formatted_url = url.format(page=self.page).encode('utf-8')

        self.logger.info('[ JobListRequest ] {url}'.format(url=formatted_url))

        yield scrapy.Request(url=formatted_url, callback=self.parse_list)
    
    def clean_tag(self,s):
        return ' '.join([x.strip() for x in remove_tags(s).split()])

    def parse_list(self, response):

        if self.killed:
            raise CloseSpider("Spider already died.")

        jobs = [url.replace('..','http://jobthaiweb.com') for url in response.xpath('.//table[@style="border-collapse: collapse;margin-top:5px;"]/tr/td[@valign="middle"]/div[@id="block1"]/a/@href').extract()[::3]]
        
        if not jobs:
            self.logger.info("[ JobEndReached ] All jobs have been crawled.")
            raise CloseSpider("all jobs have been crawled")

        for job_url in jobs:
            if self.use_proxy:
                proxy = choice(self.proxies)
                self.logger.info('[ JobPageRequest ] {url} with proxy {proxy}'.format(url=job_url, proxy=proxy))
                yield scrapy.Request(job_url, callback=self.parse_detail , meta={'proxy': proxy})
            else:
                self.logger.info('[ JobPageRequest ] {url}'.format(url=job_url))
                yield scrapy.Request(job_url, callback=self.parse_detail)

        self.page += 1
        next_page = "http://jobthaiweb.com/joblist_new.php?typejob=&jobcity=&jobarea=&key=&page={page}".format(page=self.page)

        if next_page and self.page <= self.max_page:
            self.logger.info('[ JobListRequest ] {url}'.format(url=next_page))
            yield scrapy.Request(url=next_page, callback=self.parse_list)
        elif next_page:
            self.logger.info('[ JobEndReached ] Max page reached at # %d' % self.max_page)
        else:
            self.logger.info('[ JobEndReached ] Last page reached at # %d' % self.page)

    def parse_detail(self, response):

        if self.killed:
            raise CloseSpider("Spider already died.")

        if not response.body:
            self.error_count += 1

            if self.error_count >= self.error_threshold:
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
                self.logger.info('[ JobPageRetry ] {url} with proxy {proxy}'.format(url=response.url, proxy=proxy))
                yield scrapy.Request(response.url.encode('utf-8'), callback=self.parse_detail , meta={'proxy': proxy})
                return
            else:
                self.logger.info('[ JobPageRetry ] {url}'.format(url=response.url.encode('utf-8')))
                yield scrapy.Request(response.url.encode('utf-8'), callback=self.parse_detail)
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
            row = response.xpath('.//table[@style="border-spacing: 15px;border-collapse: separate;"]/tr')
            topic = [i.xpath('./td/b/text()').extract_first() for i in row]

            head = {}
            head['pdate']   = u'\u0e1b\u0e23\u0e31\u0e1a\u0e1b\u0e23\u0e38\u0e07\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e40\u0e21\u0e37\u0e48\u0e2d'
            head['amnt']    = u'\u0e08\u0e33\u0e19\u0e27\u0e19 '
            head['sal']     = u'\u0e23\u0e30\u0e14\u0e31\u0e1a\u0e40\u0e07\u0e34\u0e19\u0e40\u0e14\u0e37\u0e2d\u0e19'
            head['desc']    = u'\u0e25\u0e31\u0e01\u0e29\u0e13\u0e30\u0e01\u0e32\u0e23\u0e17\u0e33\u0e07\u0e32\u0e19'
            head['qual']    = u'\u0e04\u0e38\u0e13\u0e2a\u0e21\u0e1a\u0e31\u0e15\u0e34\u0e1c\u0e39\u0e49\u0e2a\u0e21\u0e31\u0e04\u0e23'
            head['loc']     = u'\u0e08\u0e31\u0e07\u0e2b\u0e27\u0e31\u0e14\u0e17\u0e35\u0e48\u0e1b\u0e0f\u0e34\u0e1a\u0e31\u0e15\u0e34\u0e07\u0e32\u0e19 '
            head['loc_det'] = u'\u0e40\u0e02\u0e15\u0e1e\u0e37\u0e49\u0e19\u0e17\u0e35\u0e48\u0e1b\u0e0f\u0e34\u0e1a\u0e31\u0e15\u0e34\u0e07\u0e32\u0e19 '
            head['benef']   = u'\u0e2a\u0e27\u0e31\u0e2a\u0e14\u0e34\u0e01\u0e32\u0e23 / \u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e40\u0e1e\u0e34\u0e48\u0e21\u0e40\u0e15\u0e34\u0e21'

            ret = {}
            ret['company'] = response.xpath('.//span[@class="head_topic_black"]/text()').extract_first()
            ret['pos']     = response.xpath('.//span[@class="head_topic_white"]/center/b/text()').extract_first()
            ret['sal']     = ''
            ret['loc']     = ''

            for key in head.keys():
                try:
                    idx = topic.index(head[key])
                except ValueError:
                    continue
                ret[key]  = '|'.join([i for i in [ i.strip() for i in row[idx].xpath('./td/text()').extract() ] if i ])

            for key in ret.keys():
                if ret[key]:
                    ret[key] = ret[key].strip().encode('utf-8')

            if ret['pdate'].split()[-1] == "2560":
                self.killed = 1
                self.logger.info("[ JobEndReached ] 2017 reached")
                raise CloseSpider("2017 reached")

            _hash = hash_dn(ret['desc'],ret['company'])

            try:
                self.sqllogger.log_crawled_page(
                    hash_code    = _hash,
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

            for key in ret.keys():
                if not ret[key]:
                    del ret[key]

            yield ret
            
        except CloseSpider as e:
            raise CloseSpider(e.message)

        except:
            self.logger.error('[ JobDetailException ] {url} {html_path} {e}'.format(url=response.url.encode('utf-8'),html_path=html_path.encode('utf-8'),e=e))
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


