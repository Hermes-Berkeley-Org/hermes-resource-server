from flask import Flask
from flask import render_template
from pymongo import MongoClient
import os


app = Flask(__name__)

client = MongoClient(os.environ.get('MONGODB_URI'))
db = client[os.environ.get('DATABASE_NAME')]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data/')
def data():
    return render_template('data.html', query=db['data'].find({'flag': 1}))

# @app.route('/home/')
# def home():
#     return render_template('home.html', )

@app.route('/class/<cls>')
def classpage(cls):
    return render_template('class.html', info=db['Classes'].find_one({'Name': cls}), lectures=db['Lectures'].find({'cls': cls}))
