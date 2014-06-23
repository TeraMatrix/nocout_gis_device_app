import rrd_migration
import socket

def get_host_services_name():
        #query = "GET services"
        #result = html.live.query_summed_stats(query)
        try:
                query = "GET hosts\nColumns: host_name\nOutputFormat: json"
                
		output = get_from_socket(query)	
		print output		
		for host_name in output:
			modified_query = "GET hosts\nColumns: host_services\nFilter: host = %s\nOutputFormat: json\n" % (host_name)
			output= get_from_socket(modified_query)
			rrd_migration.rrd_migration_main("nms1",host_name,output)	
        except SyntaxError, e:
            raise MKGeneralException(_("Can not get performance data: %s") % (e))
        except socket.error, msg:
            raise MKGeneralException(_("Failed to create socket. Error code %s Error Message %s:") % (str(msg[0]), msg[1]))

def get_from_socket(query):
	socket_path = "/opt/omd/sites/nms1/tmp/run/live"
	s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(socket_path)
	s.send(query)
	output = s.recv(100000000)
	print 'nt'
        s.shutdown(socket.SHUT_WR)
        output.strip("\n")
	print output
	return output


	
if __name__ == '__main__':
    get_host_services_name()
	
