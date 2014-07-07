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


def extract_nagios_events_live(mongo_host, mongo_db, mongo_port):
	db = None
	perf_data  = None
        file_path = os.path.dirname(os.path.abspath(__file__))
        path = [path for path in file_path.split('/')]

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
	print start_epoch
        end_time = datetime.now()
        end_epoch = int((end_time - utc_time).total_seconds())
	
        # sustracting 5.30 hours        
        host_event_dict ={}
        serv_event_dict={}
	
	query = "GET log\nColumns: log_type log_time log_state_type log_state  host_name service_description options host_address current_service_perf_data\nFilter: log_time > %s\nFilter: class = 0\nFilter: class = 1\nFilter: class = 2\nFilter: class = 3\nFilter: class = 4\nFilter: class = 6\nOr: 6\n" %(start_epoch) 
	output= rrd_main.get_from_socket(site, query)

	for log_attr in output.split('\n'):
		log_split = [log_split for log_split in log_attr.split(';')]
		if log_split[0] == "CURRENT SERVICE STATE":
			host_ip = log_split[12]

			#state_type = log_split[2]
			#event_type_name=log_split[0]
                        serv_event_dict=dict(sys_timestamp=int(log_split[1]),device_name=log_split[4],severity=log_split[8],
                                                        description=log_split[11],min_value=0,max_value=0,avg_value=0,
							current_value=0,data_source=log_split[5],
							warning_threshold=0,critical_threshold=0,check_timestamp=int(log_split[1]),
                                                        ip_address=host_ip,service_name=log_split[5],site_name=site)
                        #print serv_event_dict
                        mongo_functions.mongo_db_insert(db,serv_event_dict,"serv_event")
		elif log_split[0] == "SERVICE ALERT" or log_split[0] == "INITIAL SERVICE STATE":
			
			host_ip = log_split[12]
		#	query = "GET services\nColumns: service_perf_data\nFilter: service_description ~ %s\n" %(log_split[5]) 
		#	perf_data= rrd_main.get_from_socket(site, query)
		#	perf_data = rrd_migration.get_threshold(perf_data)
		#	print perf_data
			#state_type = log_split[2]
			#event_type_name=log_split[0]
			serv_event_dict=dict(sys_timestamp=int(log_split[1]),device_name=log_split[4],severity=log_split[8],
                                                        description=log_split[11],min_value=0,max_value=0,avg_value =0,current_value=0,
							data_source = log_split[5],warning_threshold=0,
							critical_threshold =0 ,check_timestamp = int(log_split[1]),
                                                        ip_address=host_ip,service_name=log_split[5],site_name=site)
			print serv_event_dict
               		mongo_functions.mongo_db_insert(db,serv_event_dict,"serv_event")
		elif log_split[0] == "SERVICE FLAPPING ALERT":
			host_ip = log_split[11]
			#perf_data = rrd_migration.get_threshold(log_split[12])
			serv_event_dict=dict(sys_timestamp=int(log_split[1]),device_name=log_split[4],severity=log_split[8],
                                                        description=log_split[9],min_value=0,max_value=0,avg_value=0,current_value=0,
							data_source=log_split[5],warning_threshold=0,
							critical_threshold=0,check_timestamp=int(log_split[1]),
                                                        ip_address=host_ip,event_name=log_split[5],site_name=site)
			mongo_functions.mongo_db_insert(db,serv_event_dict,"serv_event")

	query = "GET log\nColumns: log_type log_time log_state_type log_state  host_name service_description options host_address current_host_perf_data\nFilter: log_time > %s\nFilter: class = 0\nFilter: class = 1\nFilter: class = 2\nFilter: class = 3\nFilter: class = 4\nFilter: class = 6\nOr: 6\n" %(start_epoch) 
	output= rrd_main.get_from_socket(site, query)

	for log_attr in output.split('\n'):
		log_split = [log_split for log_split in log_attr.split(';')]
		if log_split[0] == "CURRENT HOST STATE":
			host_ip = log_split[11]
                        host_event_dict=dict(sys_timestamp=int(log_split[1]),device_name=log_split[4],severity=log_split[7],
                                                        description=log_split[11],min_value=0,max_value=0,avg_value=0,current_value=0,
							data_source='PING',warning_threshold=0,critical_threshold=0,
							check_timestamp=int(log_split[1],service_name = 'PING'),
                                                        ip_address=host_ip,site_name=site)
		
               		mongo_functions.mongo_db_insert(db,host_event_dict,"host_event")
	

		elif log_split[0] == "HOST ALERT" or log_split[0] == "INITIAL HOST STATE":
			
			host_ip = log_split[11]
			#perf_data = rrd_migration.get_threshold(log_split[12])
			#print perf_data
			#state_type = log_split[2]
			#event_type_name=log_split[0]
			host_event_dict=dict(sys_timestamp=int(log_split[1]),device_name=log_split[4],severity=log_split[7],
                                                        description=log_split[10],min_value=0,max_value=0,avg_value=0,current_value=0,
							data_source='PING',warning_threshold=0,critical_threshold=0,
							check_timestamp=int(log_split[1]),
                                                        ip_address=host_ip,site_name=site,service_name='PING')
                	#print host_event_dict
               		mongo_functions.mongo_db_insert(db,host_event_dict,"host_event")
		elif log_split[0] == "HOST FLAPPING ALERT":
			host_ip = log_split[9]
			#event_type_name=log_split[0]
			host_event_dict=dict(sys_timestamp=int(log_split[1]),device_name=log_split[4],severity=log_split[7],
                                                        description=log_split[8],min_value=0,max_value=0,avg_value=0,current_value=0,
							data_source='PING',warning_threshold=0,critical_threshold=0,
							check_timestamp=int(log_split[1]),
                                                        ip_address=host_ip,site_name=site,service_name='PING')
			mongo_functions.mongo_db_insert(db,host_event_dict,"host_event")

"""
		elif log_split[0] == "HOST NOTIFICATION":
			host_ip = log_split[11]
                        #host_ip = log_split[10].split(':')[0]
                        #host_ip = host_ip.split('-')[1]
                        host_event_dict=dict(time=int(log_split[1]),host_name=log_split[4],status=log_split[7],
                                                        state_type=log_split[2],discription=log_split[10],
                                                        ip_address=host_ip,event_type_name=log_split[0],site_id=site)
                        #print host_event_dict
                        mongo_functions.mongo_db_insert(db,host_event_dict,"host_event")

		elif log_split[0] == "SERVICE NOTIFICATION":

                        host_ip = log_split[12]

                        #host_ip = log_split[11].split(':')[0]
                        #host_ip = host_ip.split('-')[1]
                        serv_event_dict=dict(time=int(log_split[1]),host_name=log_split[4],status=log_split[9],
                                                        state_type=log_split[2],discription=log_split[11],
                                                        ip_address=host_ip,event_type_name=log_split[0],event_name=log_split[5],site_id=site)
                        #print serv_event_dict
                        mongo_functions.mongo_db_insert(db,serv_event_dict,"serv_event")
"""	
		
if __name__ == '__main__':
    configs = parse_config_obj()
    for section, options in configs.items():
	extract_nagios_events_live(
			mongo_host=options.get('host'),
			mongo_db=options.get('nosql_db'),
			mongo_port=int(options.get('port'))
	)
