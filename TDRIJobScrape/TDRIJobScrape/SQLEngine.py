from sqlalchemy import create_engine
from sqlalchemy import exc

class RDBCrawlerLogger(object):
    def __init__(self, host, user, password, db, port=3306):
        # mysql+mysqldb://TDRIAdmin:Y38m93D7qa@tdrijobanalysis.crsgthko0cwg.us-east-2.rds.amazonaws.com:3306/TDRIJobDB
        con_string  = "mysql+mysqldb://{user}:{password}@{host}:{port}/{db}?charset=utf8".format(
            user=user,
            password=password,
            host=host,
            port=port,
            db=db
            )
        engine      = create_engine(con_string,pool_recycle=280)
        self.conn   = engine.connect()
        #query       = "CREATE TABLE IF NOT EXISTS CrawlRecord (hash_code VARCHAR(11), crawl_time DATETIME, post_time DATETIME, web_id INTEGER, PRIMARY KEY (hash_code)); " +\
        #              "CREATE INDEX by_hash ON CrawlRecord (hash_code, web_id);" +\
        #              "CREATE TABLE IF NOT EXISTS CrawlRecordDetail (hash_code VARCHAR(11), position VARCHAR(1000), employer VARCHAR(1000), " +\
        #                    "exp INTEGER, salary VARCHAR(100), location VARCHAR(100), url VARCHAR(2000),  meta VARCHAR(2000), job_status VARCHAR(20), " +\
        #                    "error_message VARCHAR(200), PRIMARY KEY (hash_code));" +\
        #              "CREATE INDEX by_hash ON CrawlRecordDetail (hash_code);"

        #self.conn.execute(query)

    def log_crawled_page(self,hash_code,position,employer,exp,salary,location,web_id,url,meta,html_path,crawl_time,post_time,job_status,error_message):

        query = 'INSERT INTO CrawlRecord VALUES ("{hash_code}","{crawl_time}","{post_time}","{web_id}");'
        query = query.format(
            hash_code     = hash_code,
            web_id        = web_id,
            crawl_time    = crawl_time,
            post_time     = post_time,
            ).replace('%','%%')
        self.conn.execute(query)

        query = 'INSERT INTO CrawlRecordDetail VALUES ("{hash_code}","{position}","{employer}","{exp}","{salary}",' +\
                    '"{location}","{url}","{meta}","{html_path}","{job_status}","{error_message}");'
        query = query.format(
            hash_code     = hash_code,
            position      = position,
            employer      = employer,
            exp           = exp,
            salary        = salary,
            location      = location,
            url           = url,
            meta          = meta,
            html_path     = html_path,
            job_status    = job_status,
            error_message = error_message
            ).replace('%','%%')
        self.conn.execute(query)

    def log_error_page(self,hash_code,web_id,url,meta,html_path,crawl_time,job_status,error_message):
        query = 'INSERT INTO CrawlRecord VALUES ("{hash_code}","{crawl_time}","0000-00-00 00:00:00","{web_id}");'
        query = query.format(
            hash_code     = hash_code,
            web_id        = web_id,
            crawl_time    = crawl_time,
            ).replace('%','%%')
        self.conn.execute(query)

        query = 'INSERT INTO CrawlRecordDetail VALUES ("{hash_code}","","","","","","{url}","{meta}","{html_path}","{job_status}","{error_message}");'
        query = query.format(
            hash_code     = hash_code,
            url           = url,
            meta          = meta,
            html_path     = html_path,
            job_status    = job_status,
            error_message = error_message
            ).replace('%','%%')
        self.conn.execute(query)


    def check_existing(self, hash_code, web_id):
        query = 'SELECT * FROM CrawlRecord where web_id = "{web_id}" and hash_code = "{hash_code}";'
        query = query.format(web_id=web_id, hash_code=hash_code)
        result = [i for i in self.conn.execute(query)]

        if result:
            return True
        else:
            return False