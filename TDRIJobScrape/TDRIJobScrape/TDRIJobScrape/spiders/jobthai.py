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
    name        = "jobthai"
    page        = 1
    web_id      = 8

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
        url = "https://www.jobthai.com/home/job_list.php?Type=NormalSearch&l=th&Region=All&ProvinceIIE=All&JobType=All&SubJobType=&IIECode=All&KeyWord=&p={page}"
        formatted_url = url.format(page=self.page).encode('utf-8')

        self.logger.info('[ JobListRequest ] {url}'.format(url=formatted_url))
        
        yield scrapy.Request(url=formatted_url, callback=self.parse_list)
    
    def clean_tag(self,s):
        return ' '.join([x.strip() for x in remove_tags(s).split()])

    def parse_list(self, response):

        if self.killed:
            raise CloseSpider("Spider already died.")

        jobs = [i.replace('..','http://www.jobthai.com') for i in response.xpath('.//div[@style="width:630px;"]/table[@width="625px"]/tr/td/div/span/a/@href').extract()]
        for job_url in jobs:
            if self.use_proxy:
                proxy = choice(self.proxies)
                self.logger.info('[ JobPageRequest ] {url} with proxy {proxy}'.format(url=job_url, proxy=proxy))
                yield scrapy.Request(job_url, callback=self.parse_detail , meta={'proxy': proxy})
            else:
                self.logger.info('[ JobPageRequest ] {url}'.format(url=job_url))
                yield scrapy.Request(job_url, callback=self.parse_detail)

        next_page = response.xpath('.//a[@rel="next"]/@href').extract_first()
        next_url  = 'http://www.jobthai.com' + next_page
            
        if next_page and self.page <= self.max_page:
            self.page += 1
            self.logger.info('[ JobListRequest ] {url}'.format(url=next_url.encode('utf-8')))
            yield scrapy.Request(url=next_url, callback=self.parse_list)
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
                self.logger.info('[ JobPageRetry ] {url} with proxy {proxy}'.format(url=response.url.encode('utf-8'), proxy=proxy))
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

            ret = {}
            head = {}

            row = response.xpath('.//table[@width="610px"]/tr/td[@valign="top"]/table[@style=" word-break: normal; word-wrap: break-word; "]')
            topic = [i.xpath('./tr/td/span/text()').extract_first() for i in row]

            head['desc'] = u'\u0e23\u0e32\u0e22\u0e25\u0e30\u0e40\u0e2d\u0e35\u0e22\u0e14\u0e02\u0e2d\u0e07\u0e07\u0e32\u0e19'
            head['loc']  = u'\u0e2a\u0e16\u0e32\u0e19\u0e17\u0e35\u0e48\u0e1b\u0e0f\u0e34\u0e1a\u0e31\u0e15\u0e34\u0e07\u0e32\u0e19'
            head['amnt'] = u'\u0e2d\u0e31\u0e15\u0e23\u0e32'
            head['qual'] = u'\u0e04\u0e38\u0e13\u0e2a\u0e21\u0e1a\u0e31\u0e15\u0e34\u0e1c\u0e39\u0e49\u0e2a\u0e21\u0e31\u0e04\u0e23'

            ret['pos']     = response.xpath('//span[@class="head5 blue"]/text()').extract_first().encode('utf8').split(' : ')[-1]
            ret['company'] = response.xpath('.//a[@class="searchjob"]/span/text()').extract_first()
            ret['pdate']   = response.xpath('.//table/tr/td[@align="right"]/span/text()').extract_first()
            ret['sal']     = ''
            ret['benef']   = ''
            ret['desc']    = ''
            ret['loc']     = ''
            try:
                ret['sal']   = response.xpath('.//table[@width="610px"]/tr/td[@valign="top"]/table[@style=" word-break: normal; word-wrap: break-word; "]')[2].xpath('./tr')[1].xpath('./td/span/text()')[1].extract()
            except:
                pass
            try:
                ret['benef'] = remove_tags(response.xpath('.//table[@style="margin-top:10px;"]/tr/td/span[@class="head1 blue"]').extract_first())
            except TypeError:
                pass

            for key in head.keys():
                try:
                    idx = topic.index(head[key])
                except ValueError:
                    continue
                ret[key]  = '|'.join([i for i in [ remove_tags(i) for i in row[idx].xpath('./tr')[1:].extract() ] if i ])

            for key in ret.keys():
                if ret[key]:
                    try:
                        ret[key] = ' '.join(ret[key].strip().split()).encode('utf-8')
                    except UnicodeDecodeError: 
                        ret[key] = ' '.join(ret[key].strip().split())

            if ret['pdate'].split()[-1] == "2560":
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
