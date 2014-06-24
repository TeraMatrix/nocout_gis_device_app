import os
import MySQLdb
import pymongo
from datetime import datetime, timedelta
from rrd_migration import mongo_conn, db_port
import subprocess
import mongo_functions

def main(site):
    data_values = []
    values_list = []
    docs = []
    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=5)
    start_time = get_epoch_time(start_time)
    end_time = get_epoch_time(end_time)

    docs = read_data(site, start_time, end_time)
    for doc in docs:
        values_list = build_data(doc)
        data_values.extend(values_list)
    field_names = [
        'host_name',
        'service',
        'host_address',
        'site_id',
        'value',
        'war',
        'crit',
	'service_state',
        'time',
    ]
    insert_data('nocout_invent_perf_log', field_names, data_values)

def read_data(site_name, start_time, end_time):
    db = None
    port = None
    docs = []
    db=mongo_functions.mongo_db_conn(site_name,"nocout")
    if db:
        cur = db.nocout_inventory_service_perf_data.find({
            "time": {"$gt": start_time, "$lt": end_time}
        })
        for doc in cur:
            docs.append(doc)
     
    return docs

def build_data(doc):
	values_list = []
	time = doc.get('time')
	t = (
        doc.get('host_name'),
        doc.get('service'),
        time,
        doc.get('plugin_value'),
        doc.get('war'),
        doc.get('crit'),
        doc.get('site_id'),
	doc.get('host_address'),
	doc.get('service_state'),
	)
	values_list.append(t)
	t = ()
	return values_list

def insert_data(table, field_names, data_values):
	db = mysql_conn()
	query = 'INSERT INTO `%s` ' % table
	query += """
		(host, service, time,value, war,
		crit, site_id,ip_address,state)VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s)
    		"""
	cursor = db.cursor()
    	try:
        	cursor.executemany(query, data_values)
    	except MySQLdb.Error, e:
        	raise MySQLdb.Error, e
    	db.commit()
    	cursor.close()

def get_epoch_time(datetime_obj):
	utc_time = datetime(1970, 1,1)
	if isinstance(datetime_obj, datetime):
		epoch_time = int((datetime_obj - utc_time).total_seconds())
		epoch_time -= 19800
		return epoch_time
	else:
		return datetime_obj

def mysql_conn(db=None):
    try:
        db = MySQLdb.connect(host='localhost', user='root', passwd='lnmiit', db='nocout_inventory_perf_data')
    except MySQLdb.Error, e:
        raise MySQLdb.Error, e

    return db

if __name__ == '__main__':
    main('nms1')
