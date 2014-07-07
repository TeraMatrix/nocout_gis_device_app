import os
import MySQLdb
import pymongo
from datetime import datetime, timedelta
from rrd_migration import mongo_conn, db_port
from events_rrd_migration import get_latest_event_entry
import subprocess
import mongo_functions
import socket


def main(**configs):
    data_values = []
    values_list = []
    docs = []
    end_time = datetime.now()
    db = mysql_conn(configs=configs)
    start_time = get_latest_event_entry(
            db_type='mysql',
            db=db,
            site=configs.get('site'),
            table_name=configs.get('table_name')
    )
    #start_time = end_time - timedelta(minutes=5)
    start_time = get_epoch_time(start_time)
    end_time = get_epoch_time(end_time)
    
    docs = read_data(start_time, end_time, configs=configs)
    for doc in docs:
        values_list = build_data(doc)
        data_values.extend(values_list)
    insert_data(configs.get('table_name'), data_values,configs=configs)

def read_data(start_time, end_time, **kwargs):
    db = None
    port = None
    docs = []
    db = mongo_conn(
        host=kwargs.get('configs').get('host'),
        port=int(kwargs.get('configs').get('port')),
        db_name=kwargs.get('configs').get('nosql_db')
    )
    if db:
        if start_time is None:
            cur = db.nocout_service_event_log.find()
        else:
            cur = db.nocout_service_event_log.find({
                "check_timestamp": {"$gt": start_time, "$lt": end_time}
            })
        for doc in cur:
            docs.append(doc)
    return docs

def build_data(doc):
	values_list = []
	machine_name = get_machine_name()
	t = (
        doc.get('device_name'),
        doc.get('service_name'),
        doc.get('sys_timestamp'),
	doc.get('check_timestamp'),
        doc.get('description'),
        doc.get('severity'),
	doc.get('current_value'),
	doc.get('min_value'),
	doc.get('max_value'),
	doc.get('avg_value'),
	doc.get('warning_threshold'),
	doc.get('critical_threshold'),
        doc.get('site_name'),
	doc.get('data_source'),
	doc.get('ip_address'),
	machine_name
	)
	values_list.append(t)
	t = ()
	return values_list

def insert_data(table,data_values,**kwargs):
	db = mysql_conn(configs=kwargs.get('configs'))
	query = 'INSERT INTO `%s` ' % table
	query += """
		(device_name,service_name,sys_timestamp,check_timestamp,
		description,severity,current_value,min_value,max_value,avg_value
		,warning_threshold,critical_threshold,site_name,data_source,
		ip_address,machine_name)
		VALUES(%s, %s, %s, %s, %s, %s, %s,%s ,%s,%s,%s,%s,%s,%s,%s,%s)
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

def mysql_conn(db=None, **kwargs):
    try:
        db = MySQLdb.connect(
			host=kwargs.get('configs').get('host'),
			user=kwargs.get('configs').get('user'),
            		passwd=kwargs.get('configs').get('sql_passwd'),
			db=kwargs.get('configs').get('sql_db')
    	)
    except MySQLdb.Error, e:
        raise MySQLdb.Error, e

    return db

def get_machine_name(machine_name=None):
    try:
        machine_name = socket.gethostname()
    except Exception, e:
        raise Exception(e)

    return machine_name



if __name__ == '__main__':
    main()
