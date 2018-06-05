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
    name        = "jobth"
    page        = 1
    web_id      = 7

    logger      = None
    sqllogger   = None
    html_path   = None
    max_page    = 9999
    use_proxy   = False
    proxies     = []
    cdate       = {}
    comnm       = {}

    repeat_count     = 0
    repeat_threshold = 3

    error_count      = 0
    error_threshold  = 5

    killed      = 0

    def start_requests(self):
        url = "http://www.jobth.com/searchjob2.php?typejob={jobtype}&city={city}&keyword={key}&page={num}"
        jobtype = self.jobtype if hasattr(self,'jobtype') else ''
        city = self.city if hasattr(self,'city') else ''
        key = self.key if hasattr(self,'key') else ''
        formatted_url = url.format(jobtype=jobtype, city=city, key=key, num=self.page).encode('utf-8')

        self.logger.info('[ JobListRequest ] {url}'.format(url=formatted_url))
        
        yield scrapy.Request(url=formatted_url, callback=self.parse_list)
    
    def clean_tag(self,s):
        return ' '.join([x.strip() for x in remove_tags(s).split()])

    def parse_list(self, response):

        if self.killed:
            raise CloseSpider("Spider already died.")

        jobs = response.xpath('//div[@class="w3-hover-shadow w3-border w3-bottombar w3-round-large"]')

        for job in jobs:
            jobid = job.xpath('./div/a/@href').extract_first()
            job_url = urljoin('http://www.jobth.com/',jobid).strip()
            self.cdate[job_url] = job.xpath('./div/div/font[@class="w3-text-gray"]/text()').extract_first()
            self.comnm[job_url] = job.xpath('.//div[@class="w3-light-gray w3-padding w3-leftbar w3-border w3-medium w3-round"]/a[contains(@href,"gid")]/text()').extract_first()

            if self.use_proxy:
                proxy = choice(self.proxies)
                self.logger.info('[ JobPageRequest ] {url} with proxy {proxy}'.format(url=job_url, proxy=proxy))
                yield scrapy.Request(job_url, callback=self.parse_detail , meta={'proxy': proxy})
            else:
                self.logger.info('[ JobPageRequest ] {url}'.format(url=job_url))
                yield scrapy.Request(job_url, callback=self.parse_detail)

        self.page += 1
        next_url  = "http://www.jobth.com/searchjob2.php?typejob={jobtype}&city={city}&keyword={key}&page={num}"
        jobtype   = self.jobtype if hasattr(self,'jobtype') else ''
        city      = self.city if hasattr(self,'city') else ''
        key       = self.key if hasattr(self,'key') else ''

        next_url  = next_url.format(jobtype=jobtype, city=city, key=key, num=self.page)

        if next_url and self.page <= self.max_page:
            self.logger.info('[ JobListRequest ] {url}'.format(url=next_url))
            yield scrapy.Request(url=next_url.encode('utf-8'), callback=self.parse_list)
        elif next_url:
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
            ret   = {}

            head  = {}

            row   = response.xpath('//div[@class="w3-container w3-left-align w3-medium w3-theme-l5"]/p|//div[@class="w3-container w3-left-align w3-medium w3-theme-l5"]/ul')[1:]
            topic = response.xpath('//div[@class="w3-container w3-left-align w3-medium w3-theme-l5"]//b/u/text()').extract()
            head['amnt']    = u'\u0e2d\u0e31\u0e15\u0e23\u0e32'
            head['sal']     = u'\u0e40\u0e07\u0e34\u0e19\u0e40\u0e14\u0e37\u0e2d\u0e19'
            head['benef']   = u'\u0e2a\u0e27\u0e31\u0e2a\u0e14\u0e34\u0e01\u0e32\u0e23'
            head['req']     = u'\u0e04\u0e38\u0e13\u0e2a\u0e21\u0e1a\u0e31\u0e15\u0e34\u0e1c\u0e39\u0e49\u0e2a\u0e21\u0e31\u0e04\u0e23'
            head['loc_det'] = u'\u0e2a\u0e16\u0e32\u0e19\u0e17\u0e35\u0e48\u0e1b\u0e0f\u0e34\u0e1a\u0e31\u0e15\u0e34\u0e07\u0e32\u0e19'
            head['loc']     = u'\u0e08\u0e31\u0e07\u0e2b\u0e27\u0e31\u0e14'

            ret['pos'], ret['desc'] = [self.clean_tag(x) for x in response.xpath('//div[@class="w3-theme-l4"]/div').extract()]
            ret['pdate']            = self.cdate[response.url]
            ret['company']          = self.comnm[response.url]
            del self.cdate[response.url]
            del self.comnm[response.url]
            ret['loc']      = ''
            ret['sal']      = ''

            for key in head.keys():
                try:
                    idx = topic.index(head[key])
                except ValueError:
                    continue
                ret[key]  = '|'.join([i for i in [ remove_tags(i) for i in row[idx].xpath('./text()|./li').extract() ] if i ])

            if ret['pdate'].split()[-1] == "2560":
                self.killed += 1
                raise CloseSpider("2017 reached")

            for key in ret.keys():
                if ret[key]:
                    ret[key] = ' '.join(ret[key].strip().split()).encode('utf-8')

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

        except Exception as e:
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
