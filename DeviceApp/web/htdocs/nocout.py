"""nocout_gis Device App web services to C/U/D a host/service into Nagios
monitoring core through check_mk functions.
"""

from wato import *
import requests
import json
import pprint
import os


hosts_file = root_dir + "hosts.mk"
rules_file = root_dir + "rules.mk"

nocout_replication_paths = [
    ( "dir",  "check_mk",   root_dir ),
    ( "dir",  "multisite",  multisite_dir ),
    ( "file", "htpasswd",   defaults.htpasswd_file ),
    ( "file", "auth.secret",  '%s/auth.secret' % os.path.dirname(defaults.htpasswd_file) ),
    ( "file", "auth.serials", '%s/auth.serials' % os.path.dirname(defaults.htpasswd_file) ),
    ( "dir", "usersettings", defaults.var_dir + "/web" ),
]
nocout_backup_paths = nocout_replication_paths + [
    ( "file", "sites",      sites_mk)
]

host_tags = {
    "snmp": "snmp-only|snmp",
    "cmk_agent": "cmk-agent|tcp",
    "snmp_v1": "snmp-v1|snmp",
    "dual": "snmp-tcp|snmp|tcp",
    "ping": "ping"
}

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

g_service_vars = {
    "only_hosts": None,
    "ALL_HOSTS": [],
    "host_contactgroups": [],
    "bulkwalk_hosts": [],
    "extra_host_conf": {},
    "extra_service_conf": {},
    "static_checks": {},
    "ping_levels": []
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
        response = {
            "success": 0,
            "message": "No action defined for mode " + action
        }

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
    global host_tags
    tags = []
    service_tuple = []
    response = {
        "success": 1,
        "device_name": html.var('device_name'),
        "service_name": html.var('service_name'),
        "message": "Service added for host ",
        "error_code": None,
        "error_message": None
    }
    payload = {
        "host": html.var("device_name"),
        "service": html.var("service_name"),
        "serv_params": html.var('serv_params'),
        "cmd_params": html.var('cmd_params'),
        "agent_tag": html.var('agent_tag'),
        "snmp_port": html.var("snmp_port")
    }
    new_host = nocout_find_host(payload.get('host'))
    if not new_host:
        threshold_items = {}
        threshold_values = None

        if payload.get('cmd_params'):
            cmd_params = json.loads(payload.get('cmd_params'))
            for ds, thresholds in cmd_params.items():
                threshold_items[ds] = ()
                threshold_items[ds] += (thresholds.get('warning'),)
                threshold_items[ds] += (thresholds.get('critical'),)
            for k, v in threshold_items.items():
                threshold_values = v

        snmp_port_tuple = None
        if payload.get('snmp_port'):
            snmp_port_tuple = (int(payload.get('snmp_port')),[],[payload.get('host')])
        elif payload.get('service').lower() != 'ping':
            snmp_port_tuple = (161,[],[payload.get('host')])

        give_permissions(rules_file)
        tags = host_tags.get(payload.get('agent_tag'))
        #service_tuple = ((payload.get('service'), None, threshold_values), [tags], [payload.get('host')])
        service_tuple = ([payload.get('host')], payload.get('service'), None, threshold_values)
        save_service(payload.get('service'), service_tuple, snmp_port_tuple)
    else:
        response.update({
            "success": 0,
            "error_message": html.var('device_name') + " not added yet",
            "message": "Service not added",
            "error_code": 1
        })
    # Push these configs to all slave multisites
    sync()

    return response


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


def deletehost():
    response = {
        "success": 1,
        "device_name": html.var('device_name'),
        "message": "Device deleted successfully",
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


def sync():
    sites_affected = []
    response = {
        "success": 1,
        "message": "Config pushed to "
    }
    # Snapshot for the local-site; to be used only by master site
    #nocout_create_snapshot()

    nocout_create_sync_snapshot()
    nocout_sites = nocout_distributed_sites()
    if len(nocout_sites) == 1:
        response.update({
            "success": 0,
            "message": "No slave multisites present"
        })
        return response

    for site, attrs in nocout_sites.items():
        if attrs.get("replication") == "slave":
            response_text = nocout_synchronize_site(site, attrs, True)
            if response_text is True:
                sites_affected.append(site)
    response.update({
        "message": "Config pushed to " + ','.join(sites_affected)
    })

    return response


def nocout_synchronize_site(site, site_attrs, restart):
    response = nocout_push_snapshot_to_site(site, site_attrs, True)

    return response


def nocout_distributed_sites():
    nocout_site_vars = {
        "sites": {}
    }
    sites_file = defaults.default_config_dir + "/multisite.d/sites.mk"
    execfile(sites_file, nocout_site_vars, nocout_site_vars)

    return nocout_site_vars.get("sites")


def nocout_push_snapshot_to_site(site, site_attrs, restart):
    mode = "slave"
    url_base = site_attrs.get('multisiteurl') + "automation.py?"
    var_string = htmllib.urlencode_vars([
        ("command", "push-snapshot"),
        ("siteid", site),
        ("mode", mode),
        ("restart", "yes"),
        ("debug", "1"),
        ("secret", site_attrs.get('secret'))
    ])
    url = url_base + var_string
    response_text = upload_file(url, sync_snapshot_file, '')
    try:
        response = eval(response_text)
        return response
    except:
        return "Garbled response from automation"


def nocout_create_sync_snapshot():
    global nocout_replication_paths
    #os.remove(sync_snapshot_file)
    tmp_path = "%s-%s" % (sync_snapshot_file, 'nocout')
    multitar.create(tmp_path, nocout_replication_paths)
    os.rename(tmp_path, sync_snapshot_file)


def nocout_create_snapshot():
    global nocout_backup_paths
    snapshot_name = "wato-snapshot-%s.tar.gz" %  \
                    time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(time.time()))
    multitar.create(snapshot_dir + snapshot_name, nocout_backup_paths)

    return "Snapshot created " + snapshot_name
    

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


def save_service(service_name, service_tuple, snmp_port_tuple):
    try:
        with open(rules_file, 'a') as f:
            f.write("\nchecks += [\n")
            f.write(" " + pprint.pformat(service_tuple) + "\n")
            f.write("]\n")
            f.write("\nsnmp_ports += [\n")
            f.write(" " + pprint.pformat(snmp_port_tuple) + "\n")
            f.write("]\n")
    except OSError, e:
        raise OSError(e)


def save_service_old(service_name, service_tuple):
    try:
        with open(rules_file, 'a') as f:
            f.write("\nstatic_checks.setdefault('" + service_name + "', [])\n")
            f.write("static_checks['" + service_name + "'] =  [\n")
            f.write(pprint.pformat(service_tuple))
            f.write(",\n")
            f.write("] + static_checks['" + service_name + "']\n\n")
    except OSError, e:
        raise OSError(e)
    

def nocout_add_host_attributes(host_attrs):
    global host_tags
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
    load_file(hosts_file)
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
