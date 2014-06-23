import os,socket,json
import rrd_main, mongo_functions
import time
def inventory_perf_data(site,hostlist):

	invent_check_list = []
	invent_service_dict = {}
	db = mongo_functions.mongo_db_conn(site,"nocout")
	print hostlist
	for host in hostlist[0]:
		print host
		query = "GET hosts\nColumns: host_services\nFilter: host_name = %s\n" %(host)
		query_output = rrd_main.get_from_socket(site,query).strip()
		print query_output
		service_list = [service_name for service_name in query_output.split(',')]
		for service in service_list:
			if service.endswith('_invent'):
				invent_check_list.append(service)

		for service in invent_check_list:
			query_string = "GET services\nColumns: service_state plugin_output\nFilter: " + \
			"service_description = %s\nFilter: host_name = %s\nOutputFormat: json\n" 	 	% (service,host)
			query_output = json.loads(rrd_main.get_from_socket(site,query_string).strip())
			plugin_output = str(query_output[0][1].split('- ')[1])
			service_state = str(query_output[0][0])
			current_time = int(time.time())
			invent_service_dict = dict (time=current_time,host_name=str(host),service=service,plugin_value=plugin_output,service_state=service_state)
			print invent_service_dict	
			mongo_functions.mongo_db_insert(db,invent_service_dict,"inventory_services")
			invent_service_dict = {}

def inventory_perf_data_main():
	try:
		query = "GET hosts\nColumns: host_name\nOutputFormat: json\n"
		output = json.loads(rrd_main.get_from_socket('nms1',query))
		inventory_perf_data('nms1',output)
	except SyntaxError, e:
		raise MKGeneralException(_("Can not get performance data: %s") % (e))
	except socket.error, msg:
		raise MKGeneralException(_("Failed to create socket. Error code %s Error Message %s:") % (str(msg[0]), msg[1]))
if __name__ == '__main__':
	inventory_perf_data_main()	
		
				
