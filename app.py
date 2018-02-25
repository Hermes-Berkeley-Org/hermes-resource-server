from flask import Flask
from flask import render_template
from pymongo import MongoClient
import os


app = Flask(__name__)

client = MongoClient(os.environ.MONGODB_URI)

@app.route('/')
def index():
    return "Hermes"

@app.route('/hello/')
@app.route('/hello/<name>')
def hello(name=None):
    return render_template('hello.html', name=name)
