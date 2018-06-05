import scrapy
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
    name        = "jobsawasdee"
    page        = 1
    web_id      = 4

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
        se_keyword = ''
        se_company = ''
        id_jtm_main = ''
        se_province = ''
        se_salary = ''
        se_exp = '0'
        sort = 'date'
        form = {"se_keyword":se_keyword,
                "se_company":se_company,
                "id_jtm_main":id_jtm_main,
                "se_province":se_province,
                "se_salary":se_salary,
                "se_exp":se_exp,
                "sort":sort}
        url = "http://www.jobsawasdee.com/joblist.php"

        self.logger.info('[ JobListRequest ] {url}'.format(url=url.encode('utf-8')))

        yield FormRequest(url=url, formdata=form, callback=self.parse_list)


    def clean_tag(self,s):
        return ' '.join([x.strip() for x in remove_tags(s).split()])


    def parse_list(self, response):

        if self.killed:
            raise CloseSpider("Spider already died.")

        jobs = response.xpath('.//ul[@id="listdisplay"]/li/div[@class="col-xs-10"]/div[@class="title"]/a/@href').extract()
        
        for job in jobs:
            job_url = urljoin("http://www.jobsawasdee.com/",job)
            if self.use_proxy:
                proxy = choice(self.proxies)
                self.logger.info('[ JobPageRequest ] {url} with proxy {proxy}'.format(url=job_url, proxy=proxy))
                yield scrapy.Request(job_url, callback=self.parse_detail , meta={'proxy': proxy})
            else:
                self.logger.info('[ JobPageRequest ] {url}'.format(url=job_url))
                yield scrapy.Request(job_url, callback=self.parse_detail)

        next_page = response.xpath('//nav/ul[@class="pagination"]/li/a/@href')[-2].extract()
        next_url = urljoin("http://www.jobsawasdee.com/joblist.php",next_page)

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

        try:
            ret = {}
            ret['pos'], ret['amnt'] = response.xpath('.//div[@id="wrapper"]/div/div/strong/span/text()').extract_first().split(':')
            ret['company']  = response.xpath('.//strong[@class="text_BB"]/text()').extract()[0]

            values        = response.xpath('.//table[@class="table text"]')[1].xpath('./tr/td')[1::2]

            ret['desc']     = '|'.join([i.strip() for i in values[0].xpath('./text()').extract()])
            ret['benef']    = ' '.join(values[1].xpath('./text()').extract_first().strip().split())
            ret['sal']      = values[2].xpath('./text()').extract_first()
            ret['sex']      = ' '.join(values[3].xpath('./text()').extract_first().split())
            ret['edu']      = ' '.join(values[4].xpath('./text()').extract_first().split())
            ret['exp']      = ' '.join(values[5].xpath('./text()').extract_first().split())
            ret['req']      = '|'.join([i.strip() for i in values[6].xpath('.//tr/td/span/text()').extract()][1::2])
            ret['loc']      = values[7].xpath('./text()').extract_first()
            ret['com_loc']  = response.xpath('.//table[@class="table text"]')[3].xpath('./tr/td/text()')[1::2][5].extract()
            ret['pdate']    = response.xpath('//div[@class="text-blue"]/text()').extract()[0].split(':')[-1]

            if ret['pdate'].split()[-1] == "60":
                self.logger.info("[ JobEndReached ] 2017 reached")
                self.killed  = 1
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
