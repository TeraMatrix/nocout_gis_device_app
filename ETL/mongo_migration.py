import os
import MySQLdb
import pymongo
from datetime import datetime, timedelta
from rrd_migration import mongo_conn, db_port
import subprocess


def main():
    data_values = []
    values_list = []
    docs = []
    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=5)
    #Do os.walk on this dir
    site_dirs = os.listdir('/opt/omd/sites/')

    docs = read_data('site1', start_time, end_time)
    #print "-- docs --"
    #print docs
    for doc in docs:
        values_list = build_data(doc)
        data_values.extend(values_list)
    #print "-- data_values --"
    #print data_values
    field_names = [
        'device_name',
        'service_name',
        'machine_id',
        'site_id',
        'data_source',
        'current_value',
        'min_value',
        'max_value',
        'avg_value',
        'warning_threshold',
        'critical_threshold',
        'sys_timestamp',
        'check_timestamp'
    ]
    insert_data('performance_performancemetric', field_names, data_values)
    print "Data inserted into mysql db"
    

def read_data(site_name, start_time, end_time):
    db = None
    port = None
    docs = []
    end_time = datetime(2014, 6, 14, 14, 20)
    start_time = end_time - timedelta(minutes=10)
    #start_time = datetime(2014, 6, 5, 13, 20)
    #end_time = datetime(2014, 6, 5, 13, 30)
    print "-- start_time, end_time --"
    print start_time, end_time
    port = db_port(site_name=site_name)
    if port:
        db = mongo_conn(
            host='localhost',
            port=int(port),
            db_name='nocout'
        )
    if db:
        cur = db.device_perf.find({
            "local_timestamp": {"$gt": start_time, "$lt": end_time}
        })
        for doc in cur:
            docs.append(doc)
     
    return docs

def build_data(doc):
    values_list = []
    uuid = get_machineid()
    local_time_epoch = get_epoch_time(doc.get('local_timestamp'))
    for ds in doc.get('ds').iterkeys():
        for entry in doc.get('ds').get(ds).get('data'):
            check_time_epoch = get_epoch_time(entry.get('time'))
            t = (
                #uuid,
                doc.get('host'),
                doc.get('service'),
                '2',
                doc.get('site'),
                ds,
                entry.get('value'),
                entry.get('value'),
                entry.get('value'),
                entry.get('value'),
                doc.get('ds').get(ds).get('meta').get('war'),
                doc.get('ds').get(ds).get('meta').get('cric'),
                local_time_epoch,
                check_time_epoch
            )
            values_list.append(t)
            t = ()

    return values_list

def insert_data(table, field_names, data_values):
    db = mysql_conn()
    query = "INSERT INTO `%s` " % table
    query += """
            (device_name, service_name, machine_id, 
            site_id, data_source, current_value, min_value, 
            max_value, avg_value, warning_threshold, 
            critical_threshold, sys_timestamp, check_timestamp) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        return epoch_time
    else:
        return datetime_obj

def mysql_conn(db=None):
    try:
        db = MySQLdb.connect(host='localhost', user='root', passwd='root', db='nocout_dev')
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

if __name__ == '__main__':
    main()