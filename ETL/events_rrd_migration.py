"""
events_rrd_migration.py
=======================

Script to import service events data from Nagios rrdtool into
Teramatrix Pollers.
"""


import os,json
from datetime import datetime, timedelta
import rrd_migration,rrd_main,mysql_functions,mongo_functions
from configparser import parse_config_obj
				

def get_latest_event_entry(db_type=None, db=None, site=None,table_name=None):
	time = None
    	if db_type == 'mongodb':
        	cur = db.nocout_host_event_log.find({}, {"check_timestamp": 1}).sort("_id", -1).limit(1)
        	for c in cur:
                	entry = c
                	time = entry.get('check_timestamp')
    	elif db_type == 'mysql':
        	query = "SELECT `check_timestamp` FROM `%s` WHERE" % table_name +\
                " `site_name` = '%s' ORDER BY `check_timestamp` DESC LIMIT 1" % (site)
        	cursor = db.cursor()
        	cursor.execute(query)
        	entry = cursor.fetchone()
        	try:
            		time = entry[0]
			return time
        	except TypeError, e:
            		cursor.close()
           		return time

        	cursor.close()

	return time

def service_perf_data_live_query(db,site,log_split):
	if log_split[0] == "CURRENT SERVICE STATE":
		host_ip = log_split[12]
		description=log_split[11]
	elif log_split[0] == "SERVICE ALERT" or log_split[0] == "INITIAL SERVICE STATE":
		host_ip = log_split[12]
		description=log_split[11]
	elif log_split[0] == "SERVICE FLAPPING ALERT":
		host_ip = log_split[11]
		description=log_split[9]
	if 'invent' not in log_split[5]:
		query = "GET services\nColumns: service_perf_data\nFilter: service_description ~ %s\n" %(log_split[5]) 
		perf_data= rrd_main.get_from_socket(site, query)
		perf_data = rrd_migration.get_threshold(perf_data)
		for ds in perf_data.iterkeys():
			cur =perf_data.get(ds).get('cur')
			war =perf_data.get(ds).get('war')
			crit =perf_data.get(ds).get('cric')
			serv_event_dict=dict(sys_timestamp=int(log_split[1]),device_name=log_split[4],severity=log_split[8],
					description=log_split[11],min_value=0,max_value=0,avg_value =0,current_value=cur,
					data_source = ds,warning_threshold=war,
					critical_threshold =crit ,check_timestamp = int(log_split[1]),
					ip_address=host_ip,service_name=log_split[5],site_name=site)
               		mongo_functions.mongo_db_insert(db,serv_event_dict,"serv_event")
	else:
		query = "GET services\nColumns: service_plugin_output\nFilter: service_description ~ %s\n" %(log_split[5]) 
		perf_data= rrd_main.get_from_socket(site, query)
		current_value = perf_data.split('- ')[1].strip('\n')
		serv_event_dict=dict(sys_timestamp=int(log_split[1]),device_name=log_split[4],severity=log_split[8],
                                description=log_split[11],min_value=0,max_value=0,avg_value =0,
				current_value=current_value,
				data_source = log_split[5],warning_threshold=0,
				critical_threshold =0 ,check_timestamp = int(log_split[1]),
				ip_address=host_ip,service_name=log_split[5],site_name=site)
		mongo_functions.mongo_db_insert(db,serv_event_dict,"serv_event")

def network_perf_data_live_query(db,site,log_split):
	if log_split[0] == "CURRENT HOST STATE":
		host_ip = log_split[12]
		description=log_split[11]
		host_perf_data = rrd_migration.get_threshold(log_split[13])
	elif log_split[0] == "HOST ALERT" or log_split[0] == "INITIAL HOST STATE":
		host_ip = log_split[11]
		description=log_split[10]
		host_perf_data = rrd_migration.get_threshold(log_split[12])
	elif log_split[0] == "HOST FLAPPING ALERT":
		host_ip = log_split[9]
		description=log_split[8]
		host_perf_data = rrd_migration.get_threshold(log_split[10])
	for ds in host_perf_data.iterkeys():
		host_cur =host_perf_data.get(ds).get('cur')
		host_war =host_perf_data.get(ds).get('war')
		host_crit =host_perf_data.get(ds).get('cric')
		host_event_dict=dict(sys_timestamp=int(log_split[1]),device_name=log_split[4],severity=log_split[7],
                		description=description,min_value=0,max_value=0,avg_value=0,current_value=host_cur,
				data_source=ds,warning_threshold=host_war,critical_threshold=host_crit,
				check_timestamp=int(log_split[1]),
				ip_address=host_ip,site_name=site,service_name='ping')
                mongo_functions.mongo_db_insert(db,host_event_dict,"host_event")



def extract_nagios_events_live(mongo_host, mongo_db, mongo_port):
	db = None
	perf_data  = {}
        file_path = os.path.dirname(os.path.abspath(__file__))
        path = [path for path in file_path.split('/')]
	war = None
	crit = None
	cur = None
        if 'sites' not in path:
                raise Exception, "File is not in omd specific directory"
        else:
                site = path[path.index('sites')+1]
	
        db = rrd_migration.mongo_conn(
		host=mongo_host,
		port=mongo_port,
		db_name=mongo_db
	)
	utc_time = datetime(1970, 1,1,5,30)
	#start_epoch = get_latest_event_entry(db_type = 'mongodb',db=db)
	#if start_epoch == None:
	start_time = datetime.now() - timedelta(minutes=1)
	start_epoch = int((start_time - utc_time).total_seconds())
        end_time = datetime.now()
        end_epoch = int((end_time - utc_time).total_seconds())
	
        # sustracting 5.30 hours        
        host_event_dict ={}
        serv_event_dict={}
	
	query = "GET log\nColumns: log_type log_time log_state_type log_state  host_name service_description "\
		"options host_address current_service_perf_data\nFilter: log_time > %s\nFilter: class = 0\nFilter: class = 1\n"\
		"Filter: class = 2\nFilter: class = 3\nFilter: class = 4\nFilter: class = 6\nOr: 6\n" %(start_epoch) 
	output= rrd_main.get_from_socket(site, query)

	for log_attr in output.split('\n'):
		log_split = [log_split for log_split in log_attr.split(';')]
		if log_split[0] == "CURRENT SERVICE STATE":
			service_perf_data_live_query(db,site,log_split)
		elif log_split[0] == "SERVICE ALERT" or log_split[0] == "INITIAL SERVICE STATE":
			service_perf_data_live_query(db,site,log_split)
		elif log_split[0] == "SERVICE FLAPPING ALERT":
			service_perf_data_live_query(db,site,log_split)

	query = "GET log\nColumns: log_type log_time log_state_type log_state  host_name service_description "\
		"options host_address current_host_perf_data\nFilter: log_time > %s\nFilter: class = 0\n"\
		"Filter: class = 1\nFilter: class = 2\nFilter: class = 3\nFilter: class = 4\nFilter: class = 6\nOr: 6\n" %(start_epoch) 
	output= rrd_main.get_from_socket(site, query)

	for log_attr in output.split('\n'):
		log_split = [log_split for log_split in log_attr.split(';')]
		if log_split[0] == "CURRENT HOST STATE":
			network_perf_data_live_query(db,site,log_split)	
		elif log_split[0] == "HOST ALERT" or log_split[0] == "INITIAL HOST STATE":
			network_perf_data_live_query(db,site,log_split)	
		elif log_split[0] == "HOST FLAPPING ALERT":
			network_perf_data_live_query(db,site,log_split)	
		
if __name__ == '__main__':
    configs = parse_config_obj()
    for section, options in configs.items():
	extract_nagios_events_live(
			mongo_host=options.get('host'),
			mongo_db=options.get('nosql_db'),
			mongo_port=int(options.get('port'))
	)
