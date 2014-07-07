import rrd_migration
import socket
import json
import os
from configparser import parse_config_obj


class MKGeneralException(Exception):
    def __init__(self, reason):
        self.reason = reason
    def __str__(self):
        return self.reason


def get_host_services_name(site_name=None, mongo_host=None, mongo_db=None, mongo_port=None):
        try:
            query = "GET hosts\nColumns: host_name\nOutputFormat: json\n"
                
            output = json.loads(get_from_socket(site_name, query))
            for host_name in output:
                modified_query = "GET hosts\nColumns: host_services host_address\n" +\
                    "Filter: host_name = %s\nOutputFormat: json\n" % (host_name[0])
                output= json.loads(get_from_socket(site_name, modified_query))
                rrd_migration.rrd_migration_main(
                    site_name,
                    host_name[0],
                    output[0],
                    output[0][1],
                    mongo_host,
                    mongo_db,
                    mongo_port
                )
        except SyntaxError, e:
            raise MKGeneralException(("Can not get performance data: %s") % (e))
        except socket.error, msg:
            raise MKGeneralException(("Failed to create socket. Error code %s Error Message %s:") % (str(msg[0]), msg[1]))

def get_from_socket(site_name, query):
    socket_path = "/opt/omd/sites/%s/tmp/run/live" % site_name
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(socket_path)
    s.send(query)
    s.shutdown(socket.SHUT_WR)
    output = s.recv(100000000)
    output.strip("\n")
    return output


    
if __name__ == '__main__':
    configs = parse_config_obj()
    for section, options in configs.items():
        site = options.get('site')
        get_host_services_name(
            site_name=site,
            mongo_host=options.get('host'),
            mongo_db=options.get('nosql_db'),
            mongo_port=options.get('port')
        )
    
