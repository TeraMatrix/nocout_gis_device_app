from configparser import parse_config_obj


def main():
    configs = parse_config_obj()
    for section, options in configs.items():
        script = options.get('network').get('script')
	service_script = options.get('service').get('script')
        migration_script = __import__(script)
	service_migration_script = __import__(service_script)
        migration_script.main(site=options.get('site'), host=options.get('host'),
            user=options.get('user'), port=options.get('port'),
            sql_passwd=options.get('sql_passwd'),
            nosql_db=options.get('network').get('nosql_db'),
            sql_db=options.get('network').get('sql_db'), ip=options.get('ip')
        )
	service_migration_script.main(site=options.get('site'), host=options.get('host'),
	    user=options.get('user'), port=options.get('port'),
            sql_passwd=options.get('sql_passwd'),
            nosql_db=options.get('service').get('nosql_db'),
            sql_db=options.get('service').get('sql_db'), ip=options.get('ip')
        )

if __name__ == '__main__':
    main()
