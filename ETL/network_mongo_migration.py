"""
network_mongo_migration.py
==========================

Script to bulk insert data from Teramatrix Pollers into
central mysql db, for ping network services.
"""


import os
import MySQLdb
import pymongo
from datetime import datetime, timedelta
from rrd_migration import mongo_conn, db_port
from mongo_functions import get_latest_entry
import subprocess
import socket


def main(**configs):
    data_values = []
    values_list = []
    docs = []
    db = mysql_conn(configs=configs)
    # Get the time for latest entry in mysql
    start_time = get_latest_entry(
		    db_type='mysql', 
		    db=db,
		    site=configs.get('site'),
		    table_name=configs.get('table_name')
    )

    end_time = datetime.now()

    docs = read_data(start_time, end_time, configs=configs)
    for doc in docs:
        values_list = build_data(doc)
        data_values.extend(values_list)
    field_names = [
        'device_name',
        'service_name',
        'machine_name',
        'site_name',
        'data_source',
        'current_value',
        'min_value',
        'max_value',
        'avg_value',
        'warning_threshold',
        'critical_threshold',
        'sys_timestamp',
        'check_timestamp',
	'ip_address'
    ]
    insert_data(configs.get('table_name'), data_values, configs=configs)
    print "Data inserted into mysql db"
    

def read_data(start_time, end_time, **kwargs):

    db = None
    port = None
    docs = []
    #end_time = datetime(2014, 6, 26, 18, 30)
    #start_time = end_time - timedelta(minutes=10)
    
    db = mongo_conn(
        host=kwargs.get('configs').get('host'),
        port=int(kwargs.get('configs').get('port')),
        db_name=kwargs.get('configs').get('nosql_db')
    )
    if db:
    	if start_time is None:
            cur = db.network_perf.find()
	else:
        	cur = db.network_perf.find({
            	"check_time": {"$gt": start_time, "$lt": end_time}
        	})
        for doc in cur:
            docs.append(doc)
     
    return docs

def build_data(doc):
    values_list = []
    #uuid = get_machineid()
    machine_name = get_machine_name()
    local_time_epoch = get_epoch_time(doc.get('local_timestamp'))
    for ds in doc.get('ds').iterkeys():
	if ds == 'rtmin' or ds == 'rtmax':
		continue
        for entry in doc.get('ds').get(ds).get('data'):
            check_time_epoch = get_epoch_time(entry.get('time'))
            t = (
                #uuid,
                doc.get('host'),
                doc.get('service'),
                machine_name,
                doc.get('site'),
                ds,
                entry.get('value'),
                entry.get('value'),
                entry.get('value'),
                entry.get('value'),
                doc.get('ds').get(ds).get('meta').get('war'),
                doc.get('ds').get(ds).get('meta').get('cric'),
                local_time_epoch,
                check_time_epoch,
		doc.get('ip_address')
            )
            values_list.append(t)
            t = ()

    return values_list

def insert_data(table, data_values, **kwargs):
    db = mysql_conn(configs=kwargs.get('configs'))
    query = "INSERT INTO `%s` " % table
    query += """
            (device_name, service_name, machine_name, 
            site_name, data_source, current_value, min_value, 
            max_value, avg_value, warning_threshold, 
            critical_threshold, sys_timestamp, check_timestamp,ip_address) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,%s)
            """
    cursor = db.cursor()
    try:
        cursor.executemany(query, data_values)
    except MySQLdb.Error, e:
        raise MySQLdb.Error, e
    db.commit()
    cursor.close()

def get_epoch_time(datetime_obj):
    # Get India times (GMT+5.30)
    utc_time = datetime(1970, 1,1, 5, 30)
    if isinstance(datetime_obj, datetime):
        epoch_time = int((datetime_obj - utc_time).total_seconds())
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

def get_machineid():
    uuid = None
    proc = subprocess.Popen(
        'sudo -S dmidecode | grep -i uuid',
        stdout=subprocess.PIPE,
        shell=True
    )
    cmd_output, err = proc.communicate()
    if not err:
        uuid = cmd_output.split(':')[1].strip()
    else:
        uuid = err

    return uuid


def get_machine_name(machine_name=None):
    try:
        machine_name = socket.gethostname()
    except Exception, e:
        raise Exception(e)

    return machine_name


if __name__ == '__main__':
    main()
