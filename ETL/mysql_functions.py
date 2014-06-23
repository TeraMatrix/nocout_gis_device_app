import MySQLdb

def mysql_execute(query,event_db):
	out = None
	conn = MySQLdb.connect(host= "localhost",
                  user="root",
                  passwd="lnmiit",
                  db=event_db)
	x = conn.cursor()

	try:
   		x.execute(query)
   		conn.commit()

	except MySQLdb.Error, e:
		print "Error %d: %s" %(e.args[0],e.args[1])
   		conn.rollback()

	finally:
		if conn:
			conn.close()
	return x
