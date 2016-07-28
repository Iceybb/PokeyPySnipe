from flask import Flask
from flask import request
from flask import render_template
from flask import redirect, url_for
from flask import jsonify
import subprocess
import os
import sys
app = Flask(__name__)

@app.route('/_snipe_')
def restart_server():
    authtype = request.args.get('authtype', 0)
    username = request.args.get('username', 0)
    password = request.args.get('password', 0)
    startingloc = request.args.get('startingloc', 0)
    snipecoords = request.args.get('snipecoords', 0)
	
   
    
    workDir = os.path.dirname(os.path.realpath(sys.argv[0]))
    subprocess.Popen([workDir + r'\snipeparam.bat',authtype,username,password,str(startingloc),str(snipecoords)], creationflags = subprocess.CREATE_NEW_CONSOLE)
    
    return render_template('dashboard.html')


@app.route('/')
def index():
    return render_template('dashboard.html')
	
	 
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5100)