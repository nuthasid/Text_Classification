import scrapy
from datetime import datetime
from scrapy.utils.markup import remove_tags
from scrapy.http import FormRequest
from scrapy.exceptions import CloseSpider
from hasher import hash_dn
from sqlalchemy import exc

class TDRISpider(scrapy.Spider):

    custom_settings = {
        'HTTPPROXY_ENABLED': True 
    }
    name        = "jobtopgun"
    page        = 1
    web_id      = 10

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
        frmdata = {"keyword":''}
        url = "https://www.jobtopgun.com/AjaxServ?pg={num}"
        formatted_url = url.format(num=self.page)
        
        yield FormRequest(url=formatted_url, formdata=frmdata, callback=self.parse_list)
    
    def clean_tag(self,s):
        return ' '.join([x.strip() for x in remove_tags(s).split()])

    def parse_list(self, response):

        if self.killed:
            raise CloseSpider("Spider already died.")

        jobs = response.xpath('//div[attribute::class="row jobPostList jobPostListCss"]')

        if not jobs:
            self.logger.info("[ JobEndReached ] All jobs have been crawled.")
            CloseSpider("all jobs have been crawled")

        for job in jobs:
            page = job.xpath('.//div[attribute::class="jobListPositionName"]/span/a/@href').extract_first()
            url = "http://www.jobtopgun.com" + page
            idEmp, idPos = url.split('/')[-2:]
            fd = {'hr':'0','idEmp':idEmp,'idPosition':idPos}
            job_url = "https://www.jobtopgun.com/view/jobPost/jobPostJobList.jsp"

            if self.use_proxy:
                proxy = choice(self.proxies)
                self.logger.info('[ JobPageRequest ] {url} {form} with proxy {proxy}'.format(url=job_url, form=fd, proxy=proxy))
                yield FormRequest(url=job_url, formdata=fd, callback=self.parse_detail , meta={'proxy': proxy,'formdata':fd})
            else:
                self.logger.info('[ JobPageRequest ] {url} {form}'.format(url=response.url, form=fd))
                yield FormRequest(url=job_url, formdata=fd, callback=self.parse_detail, meta={'formdata':fd})

        self.page += 1
        next_page = "https://www.jobtopgun.com/AjaxServ?pg={num}".format(num=self.page)
        
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
                self.logger.error('[ JobPageRequestException ] {url} {form}'.format(url=response.url, form=response.meta['formdata']))
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
                self.logger.info('[ JobPageRetry ] {url} {form} with proxy {proxy}'.format(url=response.url, form=response.meta['formdata'], proxy=proxy))
                yield FormRequest(response.url, formdata=response.meta['formdata'], callback=self.parse_detail , meta={'proxy': proxy,'formdata':fd})
                return
            else:
                self.logger.info('[ JobPageRetry ] {url} {form}'.format(url=response.url, form=response.meta['formdata']))
                yield FormRequest(response.url, formdata=response.meta['formdata'], callback=self.parse_detail, meta={'formdata':fd})
                return
        self.error_count = 0

        try:
            html_path = self.html_path.format(dttm=datetime.now().strftime('%Y%m%d_%H%M%S'))
            with open(html_path, 'w') as f:
                f.write(response.text.encode('utf-8'))
                self.logger.info('[ HTMLArchived ] {url} {form}'.format(url=response.url, form=response.meta['formdata']))
        except Exception as e:
            self.logger.error('[ HTMLArchiveException ] {url} {form}'.format(url=response.url, form=response.meta['formdata']))
        
        try:

            ret = {}

            ret['pos']   = response.xpath('//div[attribute::class="logoCompany"]/div/text()').extract_first()
            ret['pos2']  = response.xpath('//div[attribute::class="logoCompany"]/div/text()').extract_first()
            ret['company']   = self.clean_tag(response.xpath('.//div[contains(@class,"companyName")]').extract_first())
            ret['desc']  = self.clean_tag(response.xpath('.//div[@id="jobDescription"]/table/tr/td').extract_first())
            ret['req']   = self.clean_tag(response.xpath('.//div[@id="qualification"]').extract_first())

            contents     = [self.clean_tag(i) for i in response.xpath('.//div[@id="basic_require"]/div[not(@class="seperator")]').extract()]

            ret['etype'] = contents[0].split(':')[-1]
            ret['amnt']  = contents[1].split(':')[-1]
            ret['sex']   = contents[2].split(':')[-1]
            ret['sal']   = contents[3].split(':')[-1]
            ret['exp']   = contents[4].split(':')[-1]
            ret['loc']   = contents[5].split(':')[-1]
            ret['edu']   = '|'.join(contents[6].split(':')[1:])
            ret['pdate'] = response.xpath('.//div[@clas="dateAndShare"]/p/text()').extract_first()

            for key in ret.keys():
                if ret[key]:
                    ret[key] = ret[key].strip().encode('utf-8')

            if ret['pdate'].split('/')[-1] == "2560":
                self.logger.info("[ JobEndReached ] 2017 reached")
                self.killed = 1
                raise CloseSpider("2017 reached")

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
            self.logger.error('[ JobDetailException ] {url} {form} {html} {e}'.format(url=response.url.encode('utf-8'), form=response.meta['formdata'],html=html_path,e=e))
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
