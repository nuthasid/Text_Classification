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
    name        = "jobsugoi"
    page        = 1
    web_id      = 6

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
        url = "https://www.jobsugoi.com/job_search?mode=job_search&hjobsearch_state=&page=1&save_search=&job_tag=&search_job_type=&keyword_search=&salary_start=&salary_end=&jobsearch_education=&age=&job_type="
        job_type  = self.job_type if hasattr(self,'job_type') else ''
        province = self.province if hasattr(self,'province') else ''
        page  = self.page if hasattr(self,'page') else ''

        self.logger.info('[ JobListRequest ] {url}'.format(url=url.encode('utf-8')))

        yield scrapy.Request(url, callback=self.parse_list)
    
    def clean_tag(self,s):
        return ' '.join([x.strip() for x in remove_tags(s).split()])

    def parse_list(self, response):

        if self.killed:
            raise CloseSpider("Spider already died.")

        jobs = response.xpath('//form[@id="formApply"]/div[@class="row jobsearch"]//a[@class="btn btn-more-info"]/@href').extract()

        for job_url in jobs:
            if self.use_proxy:
                proxy = choice(self.proxies)
                self.logger.info('[ JobPageRequest ] {url} with proxy {proxy}'.format(url=job_url, proxy=proxy))
                yield scrapy.Request(job_url, callback=self.parse_detail , meta={'proxy': proxy})
            else:
                self.logger.info('[ JobPageRequest ] {url}'.format(url=job_url))
                yield scrapy.Request(job_url, callback=self.parse_detail)

        next_url = response.xpath('.//a[@class="pagebox pagebox-next"]/@href').extract_first()

        self.page += 1
        next_page_num = response.xpath('//a[@class="jobsearch-next"]/@onclick').extract_first().split("'")[-2]
        next_url = "https://www.jobsugoi.com/job_search?mode=job_search&hjobsearch_state=&page={num}&save_search=&job_tag=&search_job_type=&keyword_search=&salary_start=&salary_end=&jobsearch_education=&age=&job_type=".format(num=next_page_num)

        if next_page_num and self.page <= self.max_page:
            self.logger.info('[ JobListRequest ] {url}'.format(url=next_url))
            yield scrapy.Request(url=next_url, callback=self.parse_list)
        elif next_page_num:
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
                yield scrapy.Request(response.url, callback=self.parse_detail , meta={'proxy': proxy})
                return
            else:
                self.logger.info('[ JobPageRetry ] {url}'.format(url=response.url))
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

            ret['company']  = response.xpath('//div[@class="company-head m-t-10"]/text()').extract_first()
            ret['pos']      = response.xpath('//div[@id="jobinfo"]/div/div[@class="title"]/text()').extract_first()
            ret['desc']     = self.clean_tag(response.xpath('//div[@class="jobinfo-desc m-t-15"]').extract_first())
            ret['nation']   = response.xpath('.//table[@class="qualifi-table"]/tr/td/text()')[0].extract()
            ret['sex']      = response.xpath('.//table[@class="qualifi-table"]/tr/td/text()')[2].extract()
            ret['age']      = ' '.join(response.xpath('.//table[@class="qualifi-table"]/tr/td/text()')[3].extract().strip().split())
            ret['sal']      = ' '.join(response.xpath('.//table[@class="qualifi-table"]/tr/td/text()')[4].extract().strip().split())
            ret['edu']      = response.xpath('.//table[@class="qualifi-table"]/tr/td/text()')[5].extract()
            ret['exp']      = response.xpath('.//table[@class="qualifi-table"]/tr/td/text()')[6].extract()
            ret['loc']      = response.xpath('//div[@class="place"]/text()').extract_first().strip()
            ret['amnt']     = response.xpath('.//table[@class="qualifi-table"]/tr/td/text()')[7].extract()
            ret['etype']    = response.xpath('.//table[@class="qualifi-table"]/tr/td/text()')[8].extract()
            ret['benef']    = self.clean_tag(response.xpath('//div[@class="col-md-9 company-image-box"]/div/div[@class="col-md-12 padding-no m-t-15"]/div[@class="jobinfo-desc"]')[0].extract())
            ret['pdate']    = response.xpath('//div[@class="jobinfo-update"]/text()').extract_first().split(':')[1].strip()

            if ret['pdate'].split('/')[-1] == "2017":
                self.killed += 1
                self.logger.info("[ JobEndReached ] 2017 reached")
                raise CloseSpider("2017 reached")

            for key in ret.keys():
                if ret[key]:
                    ret[key] = ret[key].strip().encode('utf-8')

            _hash = hash_dn(ret['desc'],ret['company'])

            try:
                self.sqllogger.log_crawled_page(
                    hash_code    = _hash,
                    position     = ret['pos'],
                    employer     = ret['company'],
                    exp          = ret['exp'],
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
