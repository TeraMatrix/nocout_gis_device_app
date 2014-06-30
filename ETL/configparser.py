import ConfigParser
from configobj import ConfigObj
import os


# Not at use, as of now
def parse_config():
    file_path = os.path.dirname(os.path.abspath(__file__))
    path = [path for path in file_path.split('/')]

    if len(path) <= 4 or 'sites' not in path:
        raise Exception, "Place the file in appropriate omd site"
    else:
        site = path[path.index('sites') + 1]
    
    p = ConfigParser.ConfigParser()
    p.read('/opt/omd/sites/%s/nocout/config.ini' % site)

    config = {}
    for section in p.sections():
        config[section] = {}
        for option  in p.options(section):
            config[section][option] = p.get(section, option)

    return config


def parse_config_obj():
    config = ConfigObj('nocout/config.ini')
    
    return config


if __name__ == '__main__':
    c =  parse_config_obj()

