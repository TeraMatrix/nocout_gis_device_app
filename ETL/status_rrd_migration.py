import os,socket,json
import rrd_main, mongo_functions,rrd_migration
import time
from configparser import parse_config_obj


class MKGeneralException(Exception):
    def __init__(self, reason):
        self.reason = reason
    def __str__(self):
        return self.reason

def status_perf_data(site,hostlist):

	status_check_list = []
	status_service_dict = {}
	db = mongo_functions.mongo_db_conn(site,"nocout")
	for host in hostlist[0]:
		query = "GET hosts\nColumns: host_services\nFilter: host_name = %s\n" %(host)
		query_output = rrd_main.get_from_socket(site,query).strip()
		service_list = [service_name for service_name in query_output.split(',')]
		for service in service_list:
			if service.endswith('_status'):
				status_check_list.append(service)

		for service in status_check_list:
			query_string = "GET services\nColumns: service_state service_perf_data host_address\nFilter: " + \
			"service_description = %s\nFilter: host_name = %s\nOutputFormat: json\n" 	 	% (service,host)
			query_output = json.loads(rrd_main.get_from_socket(site,query_string).strip())
			perf_data_output = str(query_output[0][1])
			service_state = (query_output[0][0])
			host_ip = str(query_output[0][2])
                        current_time = int(time.time())
			if service_state == 0:
				service_state = "OK"
			elif service_state == 1:
				service_state = "WARNING"
			elif service_state == 2:
				service_state = "CRITICAL"
			elif service_state == 3:
				service_state = "UNKNOWN"
                	perf_data = rrd_migration.get_threshold(perf_data_output)
                	for ds in perf_data.iterkeys():
                        	cur =perf_data.get(ds).get('cur')
                        	war =perf_data.get(ds).get('war')
                        	crit =perf_data.get(ds).get('cric')
				status_service_dict = dict (sys_timestamp=current_time,check_timestamp=current_time,device_name=str(host),
                                                service_name=service,current_value=cur,min_value=0,max_value=0,avg_value=0,
                                                data_source=ds,severity=service_state,site_name=site,warning_threshold=war,
                                                critical_threshold=crit,ip_address=host_ip)
                        	mongo_functions.mongo_db_insert(db,status_service_dict,"status_services")

			query_output = json.loads(rrd_main.get_from_socket(site,query_string).strip())
		status_service_dict = {}

def status_perf_data_main():
	try:
		configs = parse_config_obj()
		for section, options in configs.items():
			site = options.get('site')
			query = "GET hosts\nColumns: host_name\nOutputFormat: json\n"
			output = json.loads(rrd_main.get_from_socket(site,query))
			status_perf_data(site,output)
	except SyntaxError, e:
		raise MKGeneralException(("Can not get performance data: %s") % (e))
	except socket.error, msg:
		raise MKGeneralException(("Failed to create socket. Error code %s Error Message %s:") % (str(msg[0]), msg[1]))
if __name__ == '__main__':
	status_perf_data_main()	
		
				
