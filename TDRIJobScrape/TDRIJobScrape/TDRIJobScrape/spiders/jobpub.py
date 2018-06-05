import scrapy, urllib
from datetime import datetime
from scrapy.utils.markup import remove_tags
from scrapy.http import FormRequest
from scrapy.exceptions import CloseSpider
from urlparse import urljoin
from random import choice
from hasher import hash_dn
from sqlalchemy import exc

class TDRISpider(scrapy.Spider):

    custom_settings = {
        'HTTPPROXY_ENABLED': True 
    }
    name        = "jobpub"
    page        = 1
    web_id      = 3

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

    cdttm = {}
    comnm = {}

    def start_requests(self):
        url = 'http://job.jobpub.com/search_job_tmp.asp?no={num}&keyword={keyword}&Job_Group={job_grp}&Region={region}&Province={province}'
        job_grp = self.job_grp if hasattr(self, 'job_grp') else ''
        province = self.province if hasattr(self, 'province') else ''
        region = self.region if hasattr(self, 'region') else ''
        keyword = self.keyword if hasattr(self, 'keyword') else ''

        formatted_url = url.format(keyword=keyword, job_grp=job_grp, region=region, province=province, num=self.page).encode('utf-8')

        self.logger.info('[ JobListRequest ] {url}'.format(url=formatted_url))
        
        yield scrapy.Request(url=formatted_url, callback=self.parse_list)

    def clean_tag(self, s):
        return ' '.join([ x.strip() for x in remove_tags(s).split() ])

    def parse_list(self, response):

        if self.killed:
            raise CloseSpider("Spider already died.")

        jobs  = [ link[20:26] for link in response.xpath('//table[@id="AutoNumber16"]/tr/td[@style="padding-left: 4; padding-right: 4"]/div/table/tr/td/b/font/a/@href').extract() ]
        dates = response.xpath('//tr/td[@height="23" and @width="21%"]/p[@align="center"]/font[@color="#4682b4"]/text()').extract()
        comp  = response.xpath('//span[@lang="en-us"]/a[@title="view all available jobs from this company"]/font/text()').extract()
        for i in range(len(jobs)):
            job_url = 'http://www.jobpub.com/job_files/{job_id}.htm'.format(job_id=jobs[i])
            self.cdttm[job_url] = dates[i]
            self.comnm[job_url] = comp[i]

            if self.use_proxy:
                proxy = choice(self.proxies)
                self.logger.info('[ JobPageRequest ] {url} with proxy {proxy}'.format(url=job_url, proxy=proxy))
                yield scrapy.Request(job_url, callback=self.parse_detail , meta={'proxy': proxy})
            else:
                self.logger.info('[ JobPageRequest ] {url}'.format(url=job_url))
                yield scrapy.Request(job_url, callback=self.parse_detail)

        next_page = response.xpath('.//a[img[contains(@src,"next")]]/@href').extract_first()

        if next_page and self.page <= self.max_page:
            next_page = "http://job.jobpub.com/search_job_tmp.asp" + next_page
            self.page += 1
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
                self.logger.error('[ JobPageRequestException ] {url}'.format(url=response.url))
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
                self.logger.info('[ JobPageRetry ] {url}'.format(url=response.url))
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
            contents = response.xpath('//form[@method="GET"]/table[@id="AutoNumber1"]/tr/td/font[@size="2"]/text()').extract()
            ret = {}
            ret['company']   = urllib.unquote(repr(self.comnm[response.url])[2:-1].replace('\\x','%')).decode('tis-620')
            ret['pos']       = response.xpath('//form[@method="GET"]/b/font/text()').extract_first()
            ret['sal']       = contents[1]
            ret['amnt']      = contents[2]
            ret['desc']      = response.xpath('//form[@method="GET"]/table[@id="AutoNumber1"]/tr/td/font[@style="font-size: 11pt"]/text()').extract_first()
            ret['loc']       = response.xpath('//form[@method="GET"]/table[@id="AutoNumber1"]/tr/td/font[@size="2"]/span/text()').extract_first()
            ret['pdate']     = urllib.unquote(repr(self.cdttm[response.url])[2:-1].replace('\\x','%')).decode('tis-620')
            del self.cdttm[response.url]

            if ret['pdate'].split()[-1] == "2560":
                self.logger.info("[ JobEndReached ] 2017 reached")
                raise CloseSpider("2017 reached")

            for key in ret.keys():
                if ret[key]:
                    ret[key] = ret[key].strip().encode('utf-8')

            _hash = hash_dn(ret['desc'],ret['company'])

            #log result to MySQL
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
