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
    name        = "jobant"
    page        = 1
    web_id      = 1

    ## some variables set up by a factory script on run.
    logger      = None
    sqllogger   = None
    html_path   = None
    max_page    = 9999
    use_proxy   = False
    proxies     = []

    ## variables to track repeat / error
    repeat_count     = 0
    repeat_threshold = 3

    error_count      = 0
    error_threshold  = 5

    killed      = 0


    def start_requests(self):
        '''start first request on a job-list page'''
        url = "https://www.jobant.com/jobs-search.php?s_jobtype={job_type}&s_province={province}&page={page}"
        job_type  = self.job_type if hasattr(self,'job_type') else ''
        province = self.province if hasattr(self,'province') else ''
        formatted_url = url.format(page=self.page, job_type=job_type, province=province)

        self.logger.info('[ JobListRequest ] {url}'.format(url=formatted_url.encode('utf-8')))

        yield scrapy.Request(url=formatted_url.encode('utf-8'), callback=self.parse_list)

    
    def clean_tag(self,s):
        return ' '.join([x.strip() for x in remove_tags(s).split()])

    def convert_pdate(self,pdate):
        '''convert website's post date format to standard format ("%Y-%m-%d %H:%M:%S")'''
        return datetime.strptime(pdate,"%d/%m/%Y").strftime("%Y-%m-%d %H:%M:%S")


    def parse_list(self, response):

        if self.killed:
            raise CloseSpider("Spider already died.")

        ### getting job urls from job list page.
        jobs = response.xpath('//div[@class="item"]/div/div/div/a/@href').extract()

        ### for each job page, request for html
        for job_id in jobs:
            url = urljoin("https://www.jobant.com/",job_id) 
            if self.use_proxy:
                proxy = choice(self.proxies)
                self.logger.info('[ JobPageRequest ] {url} with proxy {proxy}'.format(url=url.encode('utf-8'), proxy=proxy))
                yield scrapy.Request(url, callback=self.parse_detail , meta={'proxy': proxy})
            else:
                self.logger.info('[ JobPageRequest ] {url}'.format(url=url.encode('utf-8')))
                yield scrapy.Request(url, callback=self.parse_detail)

        ### getting next job list page url
        next_url = response.xpath('//ul[@class="pagination"]//a/@href').extract()
        if len(next_url) == 2:
            next_url = next_url[-1]
        elif len(next_url) == 1 and self.page <2:
            next_url = next_url[0]
        else:
            next_url = None
            
        ### request next job list, if it exists
        if next_url and self.page <= self.max_page:
            next_page = urljoin("https://www.jobant.com/",next_url)
            self.page += 1
            self.logger.info('[ JobListRequest ] {url}'.format(url=next_page.encode('utf-8')))
            yield scrapy.Request(url=next_page.encode('utf-8'), callback=self.parse_list)
        elif next_url:
            self.logger.info('[ JobEndReached ] Max page reached at # %d' % self.max_page)
        else:
            self.logger.info('[ JobEndReached ] Last page reached at # %d' % self.page)


    def parse_detail(self, response):

        if self.killed:
            raise CloseSpider("Spider already died.")

        ### handle the case when response from web server is empty
        # retry requesting, after 5 failures in a row, log error then continue.
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
                yield scrapy.Request(response.url.encode('utf-8'), callback=self.parse_detail , meta={'proxy': proxy})
                return
            else:
                self.logger.info('[ JobPageRetry ] {url}'.format(url=url.encode('utf-8')))
                yield scrapy.Request(response.url.encode('utf-8'), callback=self.parse_detail)
                return
        self.error_count     = 0
        ###

        ### writing html archive
        try:
            html_path = self.html_path.format(dttm=datetime.now().strftime('%Y%m%d_%H%M%S'))
            with open(html_path, 'w') as f:
                f.write(response.text.encode('utf-8'))
                self.logger.info('[ HTMLArchived ] {url}'.format(url=response.url.encode('utf-8')))
        except Exception as e:
            self.logger.error('[ HTMLArchiveException ] {url}'.format(url=response.url.encode('utf-8')))
        ###

        try:
            ### parsing information
            contents         = response.xpath('.//div[@class="wrapper-preview-list"]/div[contains(@class,"row tr")]/div[contains(@class,"col-sm")]')
            content_str      = [self.clean_tag(content.xpath('./div/div')[1].extract()) for content in contents[:10]]

            pos, company     = [x.strip() for x in response.xpath('//h1[@class="title-section c4 xs-mt5"]/text()').extract_first().split(',',1)]

            ret = {}
            
            ret['company']   = company
            ret['pos']       = pos
            ret['etype']     = content_str[1]
            ret['indus']     = content_str[2]
            ret['amnt']      = content_str[3]
            ret['sal']       = content_str[4]
            ret['exp']       = content_str[5]
            ret['sex']       = content_str[6]
            ret['edu']       = content_str[7]
            ret['loc']       = content_str[8]
            ret['desc']      = '|'.join([x.strip() for x in contents[11].xpath('./text()').extract()])
            ret['pdate']     = self.convert_pdate(response.xpath('//span[@itemprop="datePosted"]/text()').extract_first())

            if ret['pdate'].split()[0].split('-')[0] == "2017":
                self.logger.info("[ JobEndReached ] 2017 reached")
                self.killed  = 1
                raise CloseSpider("2017 reached")

            for key in ret.keys():
                if ret[key]:
                    ret[key] = ret[key].strip().encode('utf-8')
            ###

            # create hash for tracking jobs
            _hash = hash_dn(ret['desc'],ret['company']) 

            ### Stop spider after encountering crawled record 3 times in a row.
            # to prevent spider stopping just from getting a few old records
            # that may happen because of new job updates
            #if self.sqllogger.check_existing(_hash, self.web_id):
            #    if self.repeat_count >= self.repeat_threshold:
            #        self.logger.info("[ JobEndReached ] crawled record reached exceeding threshold")
            #        self.killed = 1
            #        raise CloseSpider("Crawled record reached")
            #    else:
            #        self.repeat_count += 1
            #        self.logger.info("[ JobRepeat ] crawled record found within threshold #%d" % self.repeat_count)
            #        yield None
            #        return
            #self.repeat_count = 0
            ###

            ### log result to MySQL
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
                ### check encountering old record by catching error that mysql will throw
                # if old record is met. (primary key(hash) is repeating)
                # The error code for such error is 1062
                ### Stop spider after encountering crawled record 3 times IN A ROW.
                # to prevent spider stopping just from getting a few old records
                # that may happen because of new job updates
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
                ###
            self.repeat_count = 0
            ###

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
            