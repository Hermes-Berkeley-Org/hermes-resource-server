from flask import Flask
from flask import render_template
from pymongo import MongoClient
import os


app = Flask(__name__)

client = MongoClient(os.environ.get('MONGODB_URI'))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data/')
def hello():
    return render_template('data.html')
