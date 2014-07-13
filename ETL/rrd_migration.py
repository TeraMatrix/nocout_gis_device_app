"""
rrd_migration.py
================

Script to import services and network performance data from Nagios rrdtool into
Teramatrix Pollers.
"""


import os
import demjson
import re
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET
import subprocess
import pymongo
import rrd_main
import mongo_functions

def build_export(site, host, ip, mongo_host, mongo_db, mongo_port):
	_folder = '/opt/omd/sites/%s/var/pnp4nagios/perfdata/%s/' % (site,host)
	xml_file_list = []
	#tmp_service =service
	#service = service.replace(' ','_')
	params = []
	perf_data =None
	m = 0
	ds_index =None
	file_paths = []
	temp_dict = {}
	data_dict = {
		"host": host,
		"service": None,
		"ds": {},
		"ip_address": ip

	}
    	perf_db = None
	threshold_values = {}
	db = mongo_conn(
	    host=mongo_host,
	    port=int(mongo_port),
	    db_name=mongo_db
	)
	for perf_file in os.listdir(_folder):
		if perf_file.endswith(".xml"):
			xml_file_list.append(perf_file)		
	for xml_file in xml_file_list:
		try:
			tree = ET.parse(_folder + xml_file)
			root = tree.getroot()
		except IOError, e:
			raise IOError ,e

		perf_data = root.find("NAGIOS_PERFDATA").text.strip()
		serv_disc = root.find("NAGIOS_SERVICEDESC").text.strip()
		if serv_disc == '_HOST_':
			data_dict['service'] = 'ping'
		else:
			data_dict['service'] = serv_disc
		if serv_disc.endswith('_status'):
			continue			
		threshold_values = get_threshold(perf_data)
		for ds in root.findall('DATASOURCE'):
			params.append(ds.find('NAME').text)
			file_paths.append(ds.find('RRDFILE').text)
		for path in file_paths:
			m = -1
		
			data_series = do_export(site, path,params[file_paths.index(path)], db, data_dict['service'])
			data_dict.update({
				"check_time": data_series.get('check_time'),
				"local_timestamp": data_series.get('local_timestamp'),
				"site": data_series.get('site')
				})
			ds_index = params[file_paths.index(path)]
			data_dict.get('ds')[ds_index] = {"meta": {}, "data": []}
			
			ds_values = data_series['data'][:-1]
			for d in ds_values:
					m += 1
					temp_dict = dict(
						time=data_series.get('check_time') + timedelta(minutes=m),
						value=d[-1]
					)
					data_dict.get('ds').get(ds_index).get('data').append(temp_dict)
			data_dict.get('ds').get(ds_index)['meta'] = threshold_values.get(ds_index)
		if xml_file == '_HOST_.xml':
			mongo_functions.mongo_db_insert(db,data_dict,"network_perf_data")
		else:
			mongo_functions.mongo_db_insert(db,data_dict,"serv_perf_data")

		#status = insert_data(data_dict)

		params = []
		file_paths = []
		data_dict = {
				"host": host,
				"service": None,
				"ds": {},
				"ip_address": ip
		}


def do_export(site, file_name,data_source, db, serv):
    data_series = {}
    cmd_output ={}
    CF = 'AVERAGE'
    resolution = '-300sec';

    # Data will be exported from last inserted entry in mongodb uptill current time
    start_time = mongo_functions.get_latest_entry(db_type='mongodb', db=db,table_name=None, serv=serv, ds=data_source)
    # Get India times (GMT+5.30)
    utc_time = datetime(1970, 1,1, 5, 30)
    end_time = datetime.now()

    year, month, day = end_time.year, end_time.month, end_time.day
    hour, minute = end_time.hour, end_time.minute
    #Tag : Subtracting 1 min as rrd doesn't write the current data, instantly
    end_time = datetime(year, month, day, hour, minute-1)

    if start_time is None:
        start_time = end_time - timedelta(minutes=5)

    #end_time = datetime.now() - timedelta(minutes=10)
    #start_time = end_time - timedelta(minutes=5)
    start_epoch = int((start_time - utc_time).total_seconds())
    end_epoch = int((end_time - utc_time).total_seconds())

    #Subtracting 5:30 Hrs to epoch times, to get IST
    #start_epoch -= 19800
    #end_epoch -= 19800

    cmd = '/omd/sites/%s/bin/rrdtool xport --json --daemon unix:/omd/sites/%s/tmp/run/rrdcached.sock -s %s -e %s '\
        %(site,site, str(start_epoch), str(end_epoch))
    RRAs = ['MIN','MAX','AVERAGE']

    for RRA in RRAs:
    	cmd += 'DEF:%s_%s=%s:%d:%s XPORT:%s_%s:%s_%s '\
            %(data_source, RRA, file_name, 1, RRA, data_source,
                RRA, data_source, RRA)

    p=subprocess.Popen(cmd,stdout=subprocess.PIPE, shell=True)
    cmd_output, err = p.communicate()

    try:
        cmd_output = demjson.decode(cmd_output)
    except demjson.JSONDecodeError, e:
        raise demjson.JSONDecodeError, e

    legend = cmd_output.get('meta').get('legend')
    start_check = cmd_output['meta']['start']
    end_check = start_check+300
    start_check = datetime.fromtimestamp(start_check)
    end_check = datetime.fromtimestamp(end_check)
    local_timestamp = pivot_timestamp(start_check)

    data_series.update({
        "site": site,
        "legend": legend,
        "data" :cmd_output['data'],
        "start_time": start_check,
        "end_time": end_check,
        "check_time": start_check,
        "local_timestamp": local_timestamp
    })
    return data_series


def get_threshold(perf_data):
    threshold_values = {}

    #if len(perf_data) == 1:
     #   return threshold_values
    for param in perf_data.split(" "):
	param = param.strip("['\n', ' ']")
	if param.partition('=')[2]:
        	if ';' in param.split("=")[1]:
            		threshold_values[param.split("=")[0]] = {
                	"war": re.sub('[ms]', '', param.split("=")[1].split(";")[1]),
                	"cric": re.sub('[ms]', '', param.split("=")[1].split(";")[2]),
                	"cur": re.sub('[ms]', '', param.split("=")[1].split(";")[0])
            		}
        	else:
            		threshold_values[param.split("=")[0]] = {
                	"war": None,
                	"cric": None,
                	"cur": re.sub('[ms]', '', param.split("=")[1].strip("\n"))
            		}
	else:
		threshold_values[param.split("=")[0]] = {
			"war": None,
			"cric": None,
			"cur": None
                        }

    return threshold_values


def pivot_timestamp(timestamp):
    t_stmp = timestamp + timedelta(minutes=-(timestamp.minute % 5))

    return t_stmp


def db_port(site_name=None):
    port = None
    if site_name:
        site = site_name
    else:
        file_path = os.path.dirname(os.path.abspath(__file__))
        path = [path for path in file_path.split('/')]

        if len(path) <= 4 or 'sites' not in path:
            raise Exception, "Place the file in appropriate omd site"
        else:
            site = path[path.index('sites') + 1]
    
    port_conf_file = '/opt/omd/sites/%s/etc/mongodb/mongod.d/port.conf' % site
    try:
        with open(port_conf_file, 'r') as portfile:
            port = portfile.readline().split('=')[1].strip()
    except IOError, e:
        raise IOError, e

    return port


def mongo_conn(**kwargs):
    """
    Mongodb connection object
    """
    DB = None
    try:
        CONN = pymongo.Connection(
            host=kwargs.get('host'),
            port=kwargs.get('port')
        )
        DB = CONN[kwargs.get('db_name')]
    except pymongo.errors.PyMongoError, e:
        raise pymongo.errors.PyMongoError, e
    return DB


def insert_data(data_dict):
    port = None
    db  = None
    #Get the port for mongodb process, specific to this multisite instance
    port = db_port()

    #Get the mongodb connection object
    db = mongo_conn(
        host='localhost',
        port=int(port),
        db_name='nocout'
    )

    if db:
        db.device_perf.insert(data_dict)
        return "Data Inserted into Mongodb"
    else:
        return "Data couldn't be inserted into Mongodb"


def rrd_migration_main(site,host,services,ip, mongo_host, mongo_db, mongo_port):
	build_export(site, host, ip, mongo_host, mongo_db, mongo_port)
        #for service in services[0]:

"""if __name__ == '__main__':
    build_export('BT','AM-400','PING')
"""

