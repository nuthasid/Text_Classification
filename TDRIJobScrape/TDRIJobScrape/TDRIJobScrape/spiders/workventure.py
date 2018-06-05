import scrapy, json, urllib, collections
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
    name        = "workventure"
    page        = 1
    web_id      = 13

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

    cdttm       = {}
    header      = None

    def start_requests(self):
        frmdata = {"keyword":''}
        url = "https://wvapi.com/jobs?include=company,district,province,functions&industry=&company=&job_function=&education=&keyword=&district=1&province=1&foreigner=0&salary_min=null&salary_max=null&no_salary=0&page={num}"
        self.header = {"Accept":"application/vnd.wvapi.v1+json",
                      "Accept-Encoding":"gzip, defiate, br",
                      "Accept-Language":"en-US,en;q=0.5",
                      "Conection":"keep-alive",
                      "Host":"wvapi.com",
                      "Origin":"https://www.workventure.com",
                      "Referer":"https://www.workventure.com/jobs",
                      "User-Agent":"tutorial",
                      "X-Client-Language":"th"} 
        jobtype = self.jobtype if hasattr(self,'jobtype') else ''
        city = self.city if hasattr(self,'city') else ''
        key = self.key if hasattr(self,'key') else ''
        
        yield scrapy.Request(url=url.format(num=self.page), headers=self.header, callback=self.parse_list)
    
    def clean_tag(self,s):
        return ' '.join([x.strip() for x in remove_tags(s).split()])

    def parse_list(self, response):
#        js = json.loads(remove_tags(response.xpath('/*').extract_first()))
        js = json.loads(response.text)
        jobs = js['data']

        if not jobs:
            self.logger.info("[ JobEndReached ] All jobs have been crawled.")
            raise CloseSpider("all jobs have been crawled")

        companies = [data for data in js['included'] if data['type'] == "company"]
        goal_reach = False
        for job in jobs:
            pdatetime = job['attributes']['created_at']
            if datetime.strptime(pdatetime, '%Y-%m-%d %H:%M:%S').year == 2017:
                goal_reach = True
                continue
                
            jobnm     = job['attributes']['slug']
            try:
                jobnm = jobnm.encode('utf-8')
                jobnm = urllib.quote(jobnm)
            except UnicodeDecodeError:
                jobnm = urllib.quote(jobnm)
            jobid     = str(job['attributes']['jobid'])
            try:
                jobid = jobid.encode('utf-8')
                jobid = urllib.quote(jobid)
            except UnicodeDecodeError:
                jobid = urllib.quote(jobid)
            companyid = job['relationships']['company']['data']['id']
            comp_obj  = [cp for cp in companies if cp['id'] == companyid][0]
            company   = comp_obj['attributes']['slug']
            try:
                company = company.encode('utf-8')
                company = urllib.quote(company)
            except UnicodeDecodeError:
                company = urllib.quote(company)

            #print 'info::', jobnm, jobid, company
            
            self.cdttm[(companyid,jobid)] = pdatetime
            referer   = "https://www.workventure.com/company/{company}/job/{jobnm}/{jobid}".format(company=company, jobnm=jobnm, jobid=jobid)
            header    = {'Accept': 'application/vnd.wvapi.v1+json',
                         'Accept-Encoding': 'gzip, deflate, br',
                         'Accept-Language': 'en-US,en;q=0.5',
                         'Authorization': 'Bearer null',
                         'Connection': 'keep-alive',
                         'Host': 'wvapi.com',
                         'Origin': 'https://www.workventure.com',
                         'Referer': referer,
                         'User-Agent': 'tutorial',
                         'x-Client-Language': 'th'}
            job_url   = "https://wvapi.com/jobs/{jobid}?include=skills.category,company.industry,location,educations,type,functions,experience,district".format(jobid=jobid)

            if self.use_proxy:
                proxy = choice(self.proxies)
                self.logger.info('[ JobPageRequest ] {url} with proxy {proxy}'.format(url=job_url, proxy=proxy))
                yield scrapy.Request(job_url, callback=self.parse_detail, headers=header, meta={'proxy': proxy})
            else:
                self.logger.info('[ JobPageRequest ] {url}'.format(url=job_url))
                yield scrapy.Request(job_url, headers=header, callback=self.parse_detail)

        if goal_reach :
            self.logger.info("[ JobEndReached ] 2017 reached")
            raise CloseSpider("2017 reached")

        self.page += 1
        next_url = "https://wvapi.com/jobs?include=company,district,province,functions&industry=&company=&job_function=&education=&keyword=&district=1&province=1&foreigner=0&salary_min=null&salary_max=null&no_salary=0&page={num}"
        next_url = next_url.format(num=self.page)

        if next_url and self.page <= self.max_page:
            self.logger.info('[ JobListRequest ] {url}'.format(url=next_url.encode('utf-8')))
            yield scrapy.Request(url=next_url, headers=self.header, callback=self.parse_list)
        elif next_url:
            self.logger.info('[ JobEndReached ] Max page reached at # %d' % self.max_page)
            raise CloseSpider("Max page reached")
        else:
            self.logger.info('[ JobEndReached ] Last page reached at # %d' % self.page)
            raise CloseSpider("Last page reached")

    def parse_detail(self, response):

        if not response.body:
            self.error_count += 1

            if self.error_count == 5:
                self.logger.error('[ JobPageRequestException ] {url}'.format(url=response.url))
                self.sqllogger.log_error_page(
                    hash_code    = hash_dn(response.url.encode('utf-8'),datetime.now().strftime('%Y%m%d%H%M%S')),
                    web_id       = self.web_id,
                    url          = response.url.encode('utf-8'),
                    meta         = response.header,
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
                self.logger.info('[ JobPageRetry ] {url}'.format(url=url))
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

            def convert_utf8(data):
                if isinstance(data, basestring):
                    return data.encode('utf-8')
                elif isinstance(data, collections.Mapping):
                    return dict(map(convert_utf8, data.iteritems()))
                elif isinstance(data, collections.Iterable):
                    return type(data)(map(convert_utf8, data))
                else:
                    return data

            ret = {}
            js        = json.loads(remove_tags(response.xpath('/*').extract_first()))
            js        = convert_utf8(js)
            jobid     = js['data']['attributes']['jobid']
            companyid = js['data']['relationships']['company']['data']['id']
            cdttm     = self.cdttm[(companyid,str(jobid))]
            if datetime.strptime(cdttm, '%Y-%m-%d %H:%M:%S').year == 2017:
                self.logger.info("[ JobEndReached ] 2017 reached")
                raise CloseSpider("2017 reached")

            ret['pdate'] = cdttm.encode('utf-8')

            if js['data']['attributes'].has_key('position') and js['data']['attributes']['position'] is not None:
                ret['pos']   = js['data']['attributes']['position']
            if js['data']['attributes'].has_key('position_th') and js['data']['attributes']['position_th'] is not None:
                ret['posth'] = js['data']['attributes']['position_th']
            if js['data']['attributes'].has_key('qualifications') and js['data']['attributes']['qualifications'] is not None:
                ret['qual']  = [x for x in js['data']['attributes']['qualifications']]
            if js['data']['attributes'].has_key('description') and js['data']['attributes']['description'] is not None:
                ret['desc']  = js['data']['attributes']['description']
            if js['data']['attributes'].has_key('responsibilities') and js['data']['attributes']['responsibilities'] is not None:
                ret['resp']  = [x for x in js['data']['attributes']['responsibilities']]

            ret['skill_req']  = [x['attributes'] for x in js['included'] if x['type'] == 'skillsRequired']
            ret['skill_pref'] = [x['attributes'] for x in js['included'] if x['type'] == 'skillsPreferred']
            ret['exp_pref']   = [x['attributes'] for x in js['included'] if x['type'] == 'experiencePreferred']
            ret['exp_req']    = [x['attributes'] for x in js['included'] if x['type'] == 'experienceRequired']
            ret['edu']        = [x['attributes'] for x in js['included'] if x['type'] == 'educations'][:]
            ret['company']    = [x['attributes']['name'] for x in js['included'] if x['type'] == "company"][0]

            location          = []
            try:
                province        = [x for x in js['included'] if x['type'] == 'province'][0]['attributes']['name']
                location.append(province)
                ret['province'] = province
            except:
                pass
            try:
                district        = [x for x in js['included'] if x['type'] == 'district'][0]['attributes']['name']
                location.append(district)
                ret['district'] = district
            except:
                pass

            ret['location'] = ','.join(location)

            if (not 'desc' in ret) and (not 'resp' in ret):
                ret['desc']   = ret['company'] + str(ret['skill_req'])
            elif (not 'desc' in ret) and ('resp' in ret):
                ret['desc']   = ret['resp']

#            for key in ret.keys():
#                val = ret[key]
#                if val and isinstance(val, list):
#                    ret[key] = unicode(','.join(ret[key]),encoding='utf-8').strip().encode('utf-8')
#                else:
#                    ret[key] = unicode(ret[key],encoding='utf-8').strip().encode('utf-8')

            _hash = hash_dn(ret['desc'],ret['company'])

            #log result to MySQL
            try:
                self.sqllogger.log_crawled_page(
                    hash_code    = _hash,
                    position     = '%s' % ret['pos'],
                    employer     = '%s' % ret['company'],
                    exp          = '%s' % ret['exp_req'],
                    salary       = '',
                    location     = ' '.join(ret['location']),
                    web_id       = self.web_id,
                    url          = response.url.encode('utf-8'),
                    meta         = response.headers,
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
                meta         = response.headers,
                html_path    = html_path,
                crawl_time   = datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                job_status   = 'FAILED',
                error_message= e
            )
