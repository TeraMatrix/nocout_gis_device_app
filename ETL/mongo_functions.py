import pymongo
from datetime import datetime
import rrd_migration
from operator import itemgetter


def mongo_conn(**kwargs):
	"""
    	Mongodb connection object
    	"""
    	DB = None
    	try:
        	CONN = pymongo.Connection(
            	host=kwargs.get('host'),
            	port=kwargs.get('port')
        	)
        	DB = CONN[kwargs.get('db_name')]
    	except pymongo.errors.PyMongoError, e:
       		raise pymongo.errors.PyMongoError, e
	return DB


def mongo_db_conn(site_name,db_name):
	db =None
        port = rrd_migration.db_port(site_name)

        #Get the mongodb connection object
        db = mongo_conn(
                host='localhost',
                port=int(port),
                db_name=db_name
         )
        return db

def mongo_db_insert(db,event_dict,flag):
        success = 0
        failure = 1
        if db:
                if flag == "serv_event":
                        db.nocout_service_event_log.insert(event_dict)
                elif flag == "host_event":
                        db.nocout_host_event_log.insert(event_dict)
                elif flag == "snmp_alarm_event":
                        db.nocout_snmp_trap_log.insert(event_dict)
		elif flag == "notification_event":
			db.nocout_notification_log.insert(event_dict)
		elif flag == "inventory_services":
			db.nocout_inventory_service_perf_data.insert(event_dict)
		elif flag == "serv_perf_data":
			db.service_perf.insert(event_dict)
		elif flag == "network_perf_data":
			db.network_perf.insert(event_dict)
		elif flag == "status_services":
			db.status_perf.insert(event_dict)
                return success
        else:
                print "Mongo_db insertion failed"
                return failure


def get_latest_entry(db_type=None, db=None, site=None,table_name=None, serv='_HOST_', ds='rta'):
    latest_time = None
    if db_type == 'mongodb':
        if serv == "_HOST_":
            cur = db.network_perf.find({"service": serv}, {"check_time": 1, "ds": 1}).sort("_id", -1).limit(1)
            for c in cur:
                	entry = c
                	data = entry.get('ds').get(ds).get('data')
                	data = sorted(data, key=itemgetter('time'), reverse=True)
                	try:
                    		latest_time = data[0].get('time')
                    	except IndexError, e:
                    		return latest_time
        else:
            cur = db.service_perf.find({"service": serv}, {"check_time": 1, "ds": 1}).sort("_id", -1).limit(1)
            for c in cur:
			entry = c
                    	data = entry.get('ds').get(ds).get('data')
                    	data = sorted(data, key=itemgetter('time'), reverse=True)
                    	try:
                        	latest_time = data[0].get('time')
                    	except IndexError, e:
                        	return latest_time
    elif db_type == 'mysql':
        query = "SELECT `check_timestamp` FROM `%s` WHERE" % table_name +\
            " `site_name` = '%s' ORDER BY `id` DESC LIMIT 1" % (site)
        cursor = db.cursor()
        cursor.execute(query)
        entry = cursor.fetchone()
        try:
            latest_time = entry[0]
            latest_time = datetime.fromtimestamp(latest_time)
        except TypeError, e:
            cursor.close()
            return latest_time

        cursor.close()

    return latest_time

