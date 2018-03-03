from flask import Flask
from flask import render_template
from pymongo import MongoClient
import os
import logging

app = Flask(__name__)

logging.basicConfig(filename="example.log", level=logging.DEBUG)
client = MongoClient(os.environ.get('MONGODB_URI'))
db = client[os.environ.get('DATABASE_NAME')]

@app.route('/')
def index():
    logging.warning("nah")
    return render_template('index.html')

@app.route('/data/')
def data():
    return render_template('data.html', query=db['data'].find({'flag': 1}))

# @app.route('/home/')
# def home():
#     return render_template('home.html', )
