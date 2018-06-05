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
    name        = "jobsdb"
    page        = 1
    web_id      = 5

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
        url = "https://th.jobsdb.com/TH/TH/Search/FindJobs?KeyOpt=COMPLEX&JSRV=1&RLRSF=1&JobCat=1&JSSRC=HPSS&page={page}"
        formatted_url = url.format(page=self.page).encode('utf-8')

        self.logger.info('[ JobListRequest ] {url}'.format(url=formatted_url))
        
        yield scrapy.Request(url=formatted_url, callback=self.parse_list)
    
    def clean_tag(self,s):
        return ' '.join([x.strip() for x in remove_tags(s).split()])

    def parse_list(self, response):

        if self.killed:
            raise CloseSpider("Spider already died.")

        jobs = response.xpath('.//div[contains(@class,"result-sherlock-cell")]//a[@class="posLink "]/@href').extract()

        for job_url in jobs:
            if self.use_proxy:
                proxy = choice(self.proxies)
                self.logger.info('[ JobPageRequest ] {url} with proxy {proxy}'.format(url=job_url, proxy=proxy))
                yield scrapy.Request(job_url, callback=self.parse_detail , meta={'proxy': proxy})
            else:
                self.logger.info('[ JobPageRequest ] {url}'.format(url=job_url))
                yield scrapy.Request(job_url, callback=self.parse_detail)

        next_url = response.xpath('.//a[@class="pagebox pagebox-next"]/@href').extract_first()

        if next_url and self.page <= self.max_page:
            self.page += 1
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

        pattern_type = 1

        ret = {}

        try:
            ret['company'] = remove_tags(response.xpath('.//div[@class="primary-comprofile"]/h2').extract_first())
        except :
            pattern_type = 0
            ret['company'] = remove_tags(response.xpath('.//h2[@class="jobad-header-company ad-y-auto-txt1"]/text()').extract_first())

        try:
            if pattern_type:
                ret['pos']   = response.xpath('.//h1[@class="general-pos ad-y-auto-txt"]/text()').extract_first()
                ret['desc']  = remove_tags(response.xpath('.//div[@class="jobad-primary-details col-xs-9"]').extract_first())
                ret['loc']   = response.xpath('.//span[@itemprop="addressRegion"]/a[@class="loc-link"]/text()').extract_first()
                ret['indus'] = response.xpath('.//p[@itemprop="industry"]/a/text()').extract_first()
                func  = response.xpath('.//div[@class="primary-meta-box row meta-jobfunction"]/p/a/text()').extract()
                ret['func']  = '\n'.join([' > '.join(i) for i in zip(func[::2],func[1::2])])
                ret['edu']   = response.xpath('.//span[@itemprop="educationRequirements"]/text()').extract_first()
                ret['sal']   = response.xpath('.//p[@itemprop="baseSalary"]/span/text()').extract_first()
                ret['etype'] = response.xpath('.//p[@itemprop="employmentType"]/span/b/text()').extract_first()
                ret['benef'] = '|'.join(response.xpath('.//div[@class="primary-meta-box row meta-benefit"]/div/p/span/text()').extract())
                ret['other'] = response.xpath('.//div[@class="primary-meta-item row meta-fresh"]/p/text()').extract_first()
                ret['pdate'] = ''.join([ i.strip() for i in response.xpath('.//p[@class="data-timestamp"]/text()').extract()])
            else:
                ret['pos']   = response.xpath('.//h1[@class="general-pos ad-y-auto-txt2"]/text()').extract_first()
                ret['desc']  = remove_tags(response.xpath('.//div[@itemprop="responsibilities"]').extract_first())
                ret['loc']   = response.xpath('.//span[@itemprop="addressRegion"]/a[@class="loc-link"]/text()').extract_first()
                ret['indus'] = response.xpath('.//p[@itemprop="industry"]/a/text()').extract_first()
                func  = response.xpath('.//div[@class="primary-meta-box row meta-jobfunction"]/p/a/text()').extract()
                ret['func']  = '\n'.join([' > '.join(i) for i in zip(func[::2],func[1::2])])
                ret['edu']   = response.xpath('.//span[@itemprop="educationRequirements"]/text()').extract_first()
                ret['sal']   = response.xpath('.//p[@itemprop="baseSalary"]/span/text()').extract_first()
                ret['etype'] = response.xpath('.//div[@class="primary-meta-box row meta-employmenttype"]/p/text()').extract_first()
                ret['benef'] = '|'.join(response.xpath('.//div[@class="primary-meta-box row meta-benefit"]/div/p/span/text()').extract())
                ret['other'] = response.xpath('.//div[@class="primary-meta-item row meta-fresh"]/p/text()').extract_first()
                ret['pdate'] = ''.join([ i.strip() for i in response.xpath('.//p[@class="data-timestamp"]/text()').extract()])

            if ret['pdate'].split('-')[-1] == "17":
                self.killed = 1
                self.logger.info("[ JobEndReached ] 2017 reached")
                raise CloseSpider("2017-03-10 reached")

            for key in ret.keys():
                if ret[key]:
                    ret[key] = ret[key].strip().encode('utf-8')

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
