"""nocout_gis Device App web services to C/U/D a host/service into Nagios
monitoring core through check_mk APIs.
"""

from wato import *
import requests
import json
import pprint
import os


hosts_file = root_dir + "hosts.mk"
rules_file = root_dir + "rules.mk"

g_host_vars = {
    "FOLDER_PATH": "",
    "ALL_HOSTS": ALL_HOSTS, # [ '@all' ]
    "all_hosts": [],
    "clusters": {},
    "ipaddresses": {},
    "extra_host_conf": { "alias" : [] },
    "extra_service_conf": { "_WATO" : [] },
    "host_attributes": {},
    "host_contactgroups": [],
    "_lock": False,
}


def main():
    action = html.var('mode')
    host = html.var('device_name')
    #f = (lambda x: x)
    #f(addhost)()
    try:
        # Calling the appropriate function based on action
        response = globals()[action]()
    except KeyError, e:
        html.write("No function implemented for this mode")

    html.write(pprint.pformat(response))


def addhost():
    global g_host_vars
    response = {
        "success": 1,
        "device_name": html.var('device_name'),
        "message": "Device added successfully",
        "error_code": None,
        "error_message": None
    }
    payload = {}
    payload = {
        "host": html.var("device_name"),
        "attr_alias": html.var("device_alias"),
        "attr_ipaddress": html.var("ip_address"),
        "site": html.var("site"),
        "agent_tag": html.var("agent_tag")
    }
    for key, attr in payload.items():
        if not attr:
            response.update({
                "success": 0,
                "message": None,
                "error_code": 2,
                "error_message": payload.get('host') + " " + key + " is missing"
            })
            return response
    give_permissions(hosts_file)
    load_file(hosts_file)
    if len(g_host_vars['all_hosts']) > 1000:
        response.update({
                "success": 0,
                "message": None,
                "error_code": 3,
                "error_message": "Multisite instance couldn't accept more devices"
        })
        return response
    new_host = nocout_find_host(payload.get('host'))
    
    if new_host:
        nocout_add_host_attributes(payload)
    else:
        response.update({
                "success": 0,
                "message": None,
                "error_code": 1,
                "error_message": payload['host'] + " is already present in some other " +\
                   "multisite instance" 
        })
        return response
            

    flag = save_host(hosts_file)
    if not flag:
        response.update({
                "success": 0,
                "message": None,
                "error_code": 4,
                "error_message": "hosts.mk is locked or some other message"
        })
        return response

    return response


def addservice():
    pass


def edithost():
    response = {
        "success": 1,
        "device_name": html.var('device_name'),
        "message": "Device edited successfully",
        "error_code": None,
        "error_message": None
    }
    payload = {
        "host": html.var("device_name"),
        "attr_alias": html.var("device_alias"),
        "attr_ipaddress": html.var("ip_address"),
        "site": html.var("site"),
        "agent_tag": html.var("agent_tag")
    }
    load_file(hosts_file)
    new_host = nocout_find_host(payload.get('host'))
    if not new_host:
        for i, v in enumerate(g_host_vars['all_hosts']):
            if payload.get('host') in v:
                g_host_vars['all_hosts'].pop(i)

        nocout_add_host_attributes(payload)

        flag = save_host(hosts_file)
        if not flag:
            response.update({
                    "success": 0,
                    "message": None,
                    "error_code": 2,
                    "error_message": "rules.mk is locked or some other message"
            })
            return response
    else:
        response.update({
            "success": 0,
            "message": None,
            "error_code": 1,
            "error_message": payload.get('host') + " not found"
        })
        return response

    return response

    

def load_file(file_path):
    global g_host_vars
    #Reset the global vars
    g_host_vars = {
        "FOLDER_PATH": "",
        "ALL_HOSTS": ALL_HOSTS, # [ '@all' ]
        "all_hosts": [],
        "clusters": {},
        "ipaddresses": {},
        "extra_host_conf": { "alias" : [] },
        "extra_service_conf": { "_WATO" : [] },
        "host_attributes": {},
        "host_contactgroups": [],
        "_lock": False,
    }
    try:
        execfile(file_path, g_host_vars, g_host_vars)
        del g_host_vars['__builtins__']
    except IOError, e:
        raise IOError, e


def save_host(file_path):
    global g_host_vars
    try:
        f = os.open(file_path, os.O_RDWR)
    except OSError, e:
        raise OSError, e
        return False
    fcntl.flock(f, fcntl.LOCK_EX)
    os.write(f, "# encoding: utf-8\n\n")

    os.write(f, "\nhost_contactgroups += [\n")
    for host_contactgroup in g_host_vars.get('host_contactgroups'):
        os.write(f, pprint.pformat(host_contactgroup))
        os.write(f, ",\n")
    os.write(f, "]\n\n")

    os.write(f, "all_hosts += [\n")

    for host in g_host_vars.get('all_hosts'):
        os.write(f, pprint.pformat(host))
        os.write(f, ",\n")
    os.write(f, "]\n")

    os.write(f, "\n# Explicit IP addresses\n")
    os.write(f, "ipaddresses.update(")
    os.write(f, pprint.pformat(g_host_vars.get('ipaddresses')))
    os.write(f, ")")
    os.write(f, "\n\n")

    os.write(f, "host_attributes.update(\n%s)\n" 
        % pprint.pformat(g_host_vars.get('host_attributes'))
    )
    os.close(f)

    return True


def nocout_add_host_attributes(host_attrs):
    host_tags = {
        "snmp": "snmp-only|snmp",
        "cmk_agent": "cmk-agent|tcp",
        "snmp_v1": "snmp-v1|snmp",
        "dual": "snmp-tcp|snmp|tcp",
        "ping": "ping"
    }
    host_entry = "%s|lan|prod|%s|site:%s|wato|//" % (
    host_attrs.get('host'), host_tags.get(html.var('agent_tag')), host_attrs.get('site'))
    g_host_vars['all_hosts'].append(host_entry)

    g_host_vars['ipaddresses'].update({
        host_attrs.get('host'): host_attrs.get('attr_ipaddress')
    })
    g_host_vars['host_attributes'].update({
        host_attrs.get('host'): {
            'alias': host_attrs.get('attr_alias'),
            'contactgroups': (True, ['all']),
            'ipaddress': host_attrs.get('attr_ipaddress'),
            'site': host_attrs.get('site'),
            'tag_agent': host_attrs.get(html.var('agent_tag'))
        }
    })


def nocout_find_host(host):
    new_host = True
    global g_host_vars
    for entry in g_host_vars['all_hosts']:
        if host in entry:
            new_host = False
            break

    return new_host


def give_permissions(file_path):
    import grp
    fd = os.open(file_path, os.O_RDWR | os.O_CREAT)
    # Give file permissions to apache user group
    #gid = grp.getgrnam('www-data').gr_gid
    os.chmod(file_path, 0775)
    os.close(fd)


################################################################################
##### Adding and activating the hosts
##### Url based approach


def activate_host():
    activate_host_url = "http://omdadmin:omd@localhost/BT/check_mk/wato.py?" +\
        "folder=&mode=changelog&_action=activate&_transid=-1"

    r = requests.get(activate_host_url)
    #wato.ajax_activation()
    #if is_distributed() is True
    wato.ajax_replication()

    if r.status_code == 200:
        return True
    else:
        return False

def add_host_obsolete():
    payload ={}
    host_tags = {
        "snmp": "snmp-only|snmp",
        "cmk_agent": "cmk-agent|tcp",
        "snmp_v1": "snmp-v1|snmp",
        "dual": "snmp-tcp|snmp|tcp",
        "ping": "ping"
    }

    try:
        payload = {
            "host": html.var("device_name"),
            "attr_alias": html.var("device_alias"),
            "attr_ipaddress": html.var("ip_address"),
            "site": html.var("site"),
            "mode": "newhost",
            "folder": "",
            "_change_ipaddress": "on",
            "attr_tag_agent": host_tags.get(html.var("agent_tag")),
            "attr_tag_networking": "lan", #To be edited
            "attr_tag_criticality": "prod",
            "_transid": "-1",
            "_change_site": "on",
            "_change_tag_agent": "on",
            "_change_contactgroups": "on",
            "_change_tag_networking": "on",
            "_change_alias": "on",
            "save": "Save & Finish"
        }
    except AttributeError, e:
        return "Unable To Add Host"
    url = "http://omdadmin:omd@localhost/BT/check_mk/wato.py"

    r = requests.get(url, params=payload)

    #return r.status_code

    html.write("Host Added To Multisite\n")
    html.write(json.dumps(payload))
    #Activate the changes
    activate_host()
    html.write("Host Activated For Monitoring\n")

def add_multisite_instance():
    payload = {}

    try:
        payload = {
            "id": html.var("name"),
            "alias": html.var("alias"),
            "_transid": "-1",
            "filled_in": "site",
            "folder": "",
            "method_1_0": html.var("site_ip"),
            "method_1_1": html.var("live_status_tcp_port"),
            "method_2": "",
            "method_sel": "1",
            "mode": "edit_site",
            "multisiteurl": "http://"  + html.var("site_ip") + "/" + html.var("name") + "/check_mk/",
            "repl_priority": "0",
            "replication": "slave",
            "save": "Save",
            "sh_host": "",
            "sh_site": "",
            "timeout": "10",
            "url_prefix": "http://" + html.var("site_ip") + "/" + html.var("name") + "/"
        }
    except AttributeError, e:
        return "Unable To Add Multisite"
    url = "http://omdadmin:omd@localhost/BT/check_mk/wato.py"  
    reply = requests.post(url,payload)
    html.write(json.dumps(payload))

    return reply.status_code

#Url to multisite login page
def login_page_multisite(site_id):
    try:
        payload = {
            "_login": site_id,
            "_transid": "-1",
            "folder": "",
            "mode": "sites"
        }
    except AttributeError, e:
        return "Unable To Login Multisite"

    url = "http://omdadmin:omd@localhost/BT/check_mk/wato.py"

    r = requests.get(url, params=payload)
    html.write("Logged-in to multisite\n")

    login_multisite(site_id)

#Url to login to multisite
def login_multisite(site_id):
    try:
        payload = {
            "_do_login": "Login",
            "_login": site_id,
            "_name": "omdadmin",
            "_passwd": "omd",
            "_transid": "-1",
            "filled_in": "login",
            "folder": "",
            "mode": "sites"
        }
    except AttributeError, e:
        return "Unable To Activate Multisite"

    url = "http://omdadmin:omd@localhost/BT/check_mk/wato.py"

    r = requests.get(url, params=payload)
    html.write("Multisite Activated\n")