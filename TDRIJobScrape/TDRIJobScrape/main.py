from datetime import datetime
import os, json, sys, logging
from scrapy import spiderloader #, signals
from scrapy.utils import project
from multiprocessing import Process, Queue, Manager, pool
from scrapy.crawler import CrawlerRunner
from twisted.internet import reactor
from SQLEngine import RDBCrawlerLogger

# take input as config file location

st_time         = datetime.now()

config_path = sys.argv[1]
use_proxy   = False
inp_targets = sys.argv[2:]

config = {}
with open(config_path,'r') as f:
    for line in f:
        try:
            key, val = [i.strip() for i in line.split('=')]
            config[key] = val
        except ValueError:
            continue

### prepare common log path
output_base_dir = config['OUTPUT_BASE_DIR'] # /home/ec2-user/TDRI/output/{ymd}/{spider}/{spider}.json
html_base_dir   = config['HTML_BASE_DIR'] # /home/ec2-user/TDRI/html/{ymd}/{spider}
log_base_dir    = config['LOG_BASE_DIR']

spider_log_dir  = os.path.join(log_base_dir,'{spider}')

log_name        = st_time.strftime('log_%Y%m%d_%H%M%S.log')
log_path        = os.path.join(spider_log_dir, log_name)

err_log_name    = st_time.strftime('error_%Y%m%d_%H%M%S.log')
err_log_path    = os.path.join(spider_log_dir, err_log_name)

### prepare SQL logger
host            = config['RDSHost']
user            = config['RDSUser']
password        = config['RDSPassword']
db              = config['RDSDB']
port            = config['RDSPort']
sqllogger       = RDBCrawlerLogger(host, user, password, db, port)


manager = Manager()
proxies = manager.list()

# make Process and Pool non-daemonic, so multiple spiders can run at once
class NonDemonicProcess(Process):
    def _get_daemon(self):
        return False
    def _set_daemon(self, value):
        pass
    daemon = property(_get_daemon,_set_daemon)

class NonDaemonicPool(pool.Pool):
    Process = NonDemonicProcess


# Pipeline for Proxy spider, so proxy servers are kept in a list to be used
class ProxyPipeline(object):
    def process_item(self, item, spider):
        proxies.append(item)

# Pipeline for spiders, writing parsed output to json
class STDOUTPipeline(object):
    def process_item(self, item, spider):
        if not item:
            return None
        path_detail = '{ymd}/{spider}/{spider}.json'.format(ymd=st_time.strftime('%Y%m%d'), spider=spider.name)
        output_path = os.path.join(output_base_dir,path_detail)
        try:
            os.makedirs(os.path.dirname(output_path))
        except OSError:
            pass
        with open(output_path,'a') as f:
            f.write(json.dumps(dict(item), ensure_ascii=False)+'\n')
        #print dict(item)

# to deal with "twisted.internet.error.ReactorNotRestartable" error
# function to execute a spider, this allow multiple spiders to run one after the other.
# this is possible becuase it force a spider to be run as a separate forked process
# https://stackoverflow.com/questions/41495052/scrapy-reactor-not-restartable
def run_spider((spider_name, pipeline)):
    def f(q):
        try:
            print "running...", spider_name

            ### setting up output directory for the spider.
            detail_path      = '{ymd}/{spider}'.format(ymd=st_time.strftime('%Y%m%d'),
                                                        spider=spider_name)
            html_path        = os.path.join(html_base_dir, detail_path)

            html_path        = os.path.join(html_path, '{dttm}.html')
            if not os.path.exists(os.path.dirname(html_path)): 
                os.makedirs(os.path.dirname(html_path))

            ### setting up log directory for the spider
            sp_log_path      = log_path.format(spider=spider_name)
            sp_err_log_path  = err_log_path.format(spider=spider_name)

            if not os.path.exists(os.path.dirname(sp_log_path)): 
                os.makedirs(os.path.dirname(sp_log_path))
            if not os.path.exists(os.path.dirname(sp_err_log_path)): 
                os.makedirs(os.path.dirname(sp_err_log_path))

            ### setting up logger for the spider
            logger           = logging.getLogger(spider_name+'_logger')
            logger.setLevel(logging.DEBUG)

            debug_handler    = logging.FileHandler(sp_log_path)
            error_handler    = logging.FileHandler(sp_err_log_path)
            debug_handler.setLevel(logging.DEBUG)
            error_handler.setLevel(logging.WARNING)
            formatter        = logging.Formatter('%(asctime)s:%(module)s - %(message)s')
            debug_handler.setFormatter(formatter)
            error_handler.setFormatter(formatter)
            
            logger.addHandler(debug_handler)
            logger.addHandler(error_handler)
            
            logger.info('logger created')

            ### preparing spider object.
            settings         = project.get_project_settings()
            settings.set('ITEM_PIPELINES', {pipeline:1}, priority='cmdline')
            spider_loader    = spiderloader.SpiderLoader.from_settings(settings)

            spider           = spider_loader.load(spider_name)
            spider.html_path = html_path
            spider.proxies   = proxies
            spider.use_proxy = use_proxy
            spider.logger    = logger
            spider.sqllogger = sqllogger

            spider.repeat_count     = 0
            spider.repeat_threshold = 10
            spider.error_count      = 0
            spider.error_threshold  = 5

            ### starting spider queue and spider
            crawler_runner   = CrawlerRunner(settings)   #from Scrapy docs

            deferred         = crawler_runner.crawl(spider)
            deferred.addBoth(lambda _: reactor.stop())
            reactor.run()
            q.put(None)

        except Exception as e:
            q.put(e)

    q = Queue()
    p = Process(target=f, args=(q,))
    p.start()
    result = q.get()
    p.join()

    if result is not None:
        raise result

results = []
def spider_closed(spider):
    print results

run_spider(('proxy', '__main__.ProxyPipeline'))
proxies = [i['http'] for i in proxies]
print 'proxy:', len(proxies)

#for target in inp_targets:
#    run_spider((target, '__main__.STDOUTPipeline'))

p = NonDaemonicPool(5)
p.map(run_spider,[(target,'__main__.STDOUTPipeline') for target in inp_targets])



