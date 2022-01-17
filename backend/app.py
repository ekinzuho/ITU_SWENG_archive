from flask import Flask, request, make_response, jsonify, send_file
import requests
import os
import configparser
import mysql.connector as mc
import sys
import boto3
import json
from flask_cors import CORS


configFile = "/config.cfg"
config = configparser.ConfigParser()
path = os.path.dirname(os.path.realpath(__file__)) #current path
config.read(f'{path}'+configFile)



########## VARIABLES ##########
db = config['MYSQL_DB']['DB']
dbUser = config['MYSQL_DB']['USER']
dbPasswd = config['MYSQL_DB']['PASSWORD']
dbHost = config['MYSQL_DB']['HOST']
appHost = config['APP']['HOST']
appPort = config['APP']['PORT']
dbTable_login = "USER_LOGIN"
dbTable_codeFile = "CODE_FILE"
s3_id = config['AWS']['ID']
s3_key = config['AWS']['KEY']
s3_region = 'eu-central-1'
bucket_name = "pythoncode-storage"


########## DATABASE WORKS ##########
def mysqlConn():
	try:
		return mc.connect(user=dbUser, password=dbPasswd, host=dbHost, database=db, auth_plugin="mysql_native_password")
	except Exception as e:
		print("Mysql database connection: " + str(e), file=sys.stderr)


def createTable(db):
	try:
		cursor = db.cursor(buffered=True)
		query = "CREATE TABLE IF NOT EXISTS " + dbTable_login + " (id INT NOT NULL AUTO_INCREMENT, email VARCHAR(100), password VARCHAR(20), PRIMARY KEY (id));"
		cursor.execute(query)
		query = "CREATE TABLE IF NOT EXISTS " + dbTable_codeFile + " (id INT NOT NULL AUTO_INCREMENT, filename VARCHAR(200), description VARCHAR(200), user_id INT, PRIMARY KEY (id));"
		cursor.execute(query)
	except Exception as e:
		print("Database Table Create: "+ str(e), file=sys.stderr)



########## RUN APP ##########
app = Flask(__name__)
CORS(app)


########## ENDPOINTS ##########
@app.route('/signup', methods=['POST'])
def signup():
	print("signup")
	mysqlDb = mysqlConn()
	if mysqlDb != None:
		try:
			cursor = mysqlDb.cursor(buffered=True)
			email = request.get_json()['username']
			password = request.get_json()['password']

			if email != '' and password != '':
				q = "SELECT email FROM " + db + "." + dbTable_login + f" WHERE email = '{email}' "
				cursor.execute(q) #run query
				res = cursor.fetchall() # get result

				if res: #email already exists
					return {'success':'false', 'message':'Email already exists!..'}
				else:
					q = "INSERT INTO " + db + "." + dbTable_login + f" (email, password) VALUES ('{email}','{password}');"
					cursor.execute(q) #run query
					mysqlDb.commit()
			else:
				return {'success':'false', 'message':'Empty email or password!..'}

			mysqlDb.close()
			return {'success':'true', 'message':'Successfully signup!..'}

		except Exception as e:
			print("debug_1: ", e, file=sys.stderr)

	else:
		print('This is error output', file=sys.stderr)
		print('This is standard output', file=sys.stdout)

	return {'success':'false', 'message':'404!..'}




@app.route('/login', methods=['POST'])
def login():
	print("login")
	mysqlDb = mysqlConn()
	if mysqlDb != None:
		try:
			cursor = mysqlDb.cursor(buffered=True)

			email = request.get_json()['username']
			password = request.get_json()['password']

			if email != '' and password != '':
				q = "SELECT id, password FROM " + db + "." + dbTable_login + f" WHERE email = '{email}' " 
				cursor.execute(q) #run query
				res = cursor.fetchall() # get result

				if not res:
					return {'success':'false', 'message':'Email does not exist!..', 'projectsInfo': []}

				else:
					user_id = res[0][0]
					passwd = res[0][1]

					if password == passwd:
						#get files' infos
						q = "SELECT filename, description FROM " + db + "." + dbTable_codeFile + f" WHERE user_id = '{user_id}' "
						cursor.execute(q)
						files_info = cursor.fetchall()

						info=[]
						for feature in files_info:

						    item = {'name': feature[0], 'description':feature[1]}
						    info.append(item)

						return {'success':'true', 'message':'Login is successful.', 'projectsInfo':info}

					else:
						return {'success':'false', 'message':'Invalid email or password!..', 'projectsInfo':[]}

			else:
				return {'success':'false', 'message':'Empty email or password!..', 'projectsInfo':[]}

			mysqlDb.close()

		except Exception as e: 
			print("debug_2: ", e, file=sys.stderr)
	else:
		print('This is error output', file=sys.stderr)

	return {'success':'false', 'message':'404!..'} # get 500 when no return value



@app.route('/upload', methods=['POST'])
def upload():
	print("upload")
	mysqlDb = mysqlConn()
	if mysqlDb != None:
		try:
			cursor = mysqlDb.cursor(buffered=True)

			print(request.get_json())

			text = request.get_json()['code']
			email = request.get_json()['email']
			file_name = request.get_json()['filename']
			file_des = request.get_json()['fileDescription']



			if email!='' and file_name!='' and file_des!='':
				q = "SELECT id FROM " + db + "." + dbTable_login + f" WHERE email = '{email}' "
				cursor.execute(q)
				idd = cursor.fetchall()

				if idd: 

					local_path = '/home/ubuntu/buse/codes/upload/' + str(idd[0][0]) 
					if not os.path.isdir(local_path):
					    os.makedirs(local_path)
					    print("debug55443")
					filepath = os.path.join(local_path, file_name)

					f = open(filepath, "w") #create file
					for t in text:
						f.write(t)
					f.close()

					q = "SELECT id FROM " + db + "." + dbTable_codeFile + f" WHERE user_id = '{idd[0][0]}' and filename = '{file_name}' "
					cursor.execute(q)
					id_f = cursor.fetchall()

					s3_client = boto3.client('s3', aws_access_key_id=s3_id, aws_secret_access_key=s3_key, region_name=s3_region)
					if id_f:
						print("sil")
						#boto3.set_stream_logger('')
						#s3_client.delete_object(Bucket=bucket_name, Key=str(idd) + '/' + file_name)

						s3 = boto3.client("s3", aws_access_key_id=s3_id, aws_secret_access_key=s3_key)
						s3.delete_object(Bucket=bucket_name, Key=str(idd)+'/'+file_name)


					if not id_f:
						print("debug1555")
						q = "INSERT INTO " + db + "." + dbTable_codeFile + f" (user_id, filename, description) VALUES ('{idd[0][0]}','{file_name}','{file_des}');" # id type dan dolayı hata olabilir
						cursor.execute(q) #run query
						mysqlDb.commit()

					res = s3_client.upload_file(filepath, bucket_name, str(idd[0][0]) + '/' + file_name)
					os.remove(filepath) #delete file in local					

					return {'success':'true', 'message':'Successful!..'}
				else:
					return {'success':'false', 'message':'Invalid email!..'}
			else:
				return {'success':'false', 'message':'Empty email, file or file name!..'} 

		except Exception as e:
			print("debug_6: ", e, file=sys.stderr)

	else:
		print("debug_5: DB")

	return {'success':'false', 'message':'404!..'}



@app.route('/dowload_code', methods=['POST'])
def download(): #from bucket to local
	print("download")

	client = boto3.client('s3', aws_access_key_id = s3_id, aws_secret_access_key = s3_key, region_name = s3_region)
	mysqlDb = mysqlConn()
	if mysqlDb != None:
		try:
			cursor = mysqlDb.cursor(buffered=True)

			email = request.get_json()['username']
			file_name = request.get_json()['projectName']

			if email!='' and file_name!='':
				q = "SELECT id FROM " + db + "." + dbTable_login + f" WHERE email = '{email}' "
				cursor.execute(q)
				idd = cursor.fetchall()

				if idd: # user id
					idd = str(idd[0][0])

					q = "SELECT id FROM " + db + "." + dbTable_codeFile + f" WHERE filename = '{file_name}' and user_id = '{idd}' "
					cursor.execute(q)
					idd_f = cursor.fetchall()

					if idd_f: 
						local_path = '/home/ubuntu/buse/codes/download/' + idd
						if not os.path.isdir(local_path):
						    os.makedirs(local_path)

						filepath = os.path.join(local_path, file_name)

						#client.download_file(bucket_name, local_path, file_path)
						client.download_file(bucket_name, idd+'/'+file_name, filepath)

						f = open(filepath, "r")
						t = f.read()
						os.remove(filepath)

						return {'success':'true', 'code':t} 

					else:
						return {'success':'false', 'message':'Invalid file name!..'} 
				else:
					return {'success':'false', 'message':'Invalid email!..'} 			
			else:
				return {'success':'false', 'message':'Empty email or file name!..'} 

		except Exception as e:
			print("debug_10: ", e, file=sys.stderr)

	else:
		print("debug_50: DB")

	return {'success':'false', 'message':'404!..'}


@app.route('/check', methods=['GET'])
def check():
	return "OKAY"
	


########## MAIN ##########
if __name__ =="__main__":
	mysqlDb = mysqlConn()
	print(appHost, appPort)
	if mysqlDb != None:
		createTable(mysqlDb)
		try:
			mysqlDb.close()
		except Exception as e:
			print("debug_3: ", e, file=sys.stderr)
	try:
		app.run(host=appHost, port=appPort, debug=True)

	except Exception as e:
		print("debug_4: ", e, file=sys.stderr)



