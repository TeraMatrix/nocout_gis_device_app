from mod_python import apache
import requests
from wato import *
import json
import os
import pprint
import grp


hosts_file = root_dir + "hosts.mk"
rules_file = root_dir + "rules.mk"

variables = {
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


def add_host():
    payload = {}
    host_tags = {
        "snmp": "snmp-only|snmp",
        "cmk_agent": "cmk-agent|tcp",
        "snmp_v1": "snmp-v1|snmp",
        "dual": "snmp-tcp|snmp|tcp",
        "ping": "ping"
    }

    payload = {
        "host": html.var("device_name"),
        "attr_alias": html.var("device_alias"),
        "attr_ipaddress": html.var("ip_address"),
        "site": html.var("site"),
        "agent_tag": html.var("agent_tag")
    }
    give_permissions(hosts_file)
    load_file(hosts_file)

    host_entry = "%s|lan|prod|%s|site:%s|wato|//" \
        % (payload.get('host'), host_tags.get(html.var('agent_tag')), payload.get('site'))
    variables['all_hosts'].append(host_entry)

    variables['ipaddresses'].update({payload.get('host'): payload.get('attr_ipaddress')})
    variables['host_attributes'].update({
        payload.get('host'): {
            'alias': payload.get('attr_alias'),
            'contactgroups': (True, ['all']),
            'ipaddress': payload.get('attr_ipaddress'),
            'site': payload.get('site'),
            'tag_agent': host_tags.get(html.var('agent_tag'))
        }
    })

    save_host(hosts_file)
    

def load_file(file_path):
    try:
        execfile(file_path, variables, variables)
        del variables['__builtins__']
    except IOError, e:
        raise IOError, e


def save_host(file_path):
    f = open(file_path, 'w')
    f.seek(0)
    f.write("# encoding: utf-8\n\n")

    f.write("\nhost_contactgroups += [\n")
    for host_contactgroup in variables.get('host_contactgroups'):
        f.write(pprint.pformat(host_contactgroup))
        f.write(",\n")
    f.write("]\n\n")

    f.write("all_hosts += [\n")
    for host in variables.get('all_hosts'):
        f.write(pprint.pformat(host))
        f.write(",\n")
    f.write("]\n")

    f.write("\n# Explicit IP addresses\n")
    f.write("ipaddresses.update(")
    f.write(pprint.pformat(variables.get('ipaddresses')))
    f.write(")")
    f.write("\n\n")

    f.write("host_attributes.update(\n%s)\n" 
        % pprint.pformat(variables.get('host_attributes'))
    )


def give_permissions(file_path):
    if not os.path.exists(file_path):
        fd = os.open(file_path, os.O_CREAT)
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
