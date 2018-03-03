from flask import Flask
from flask import render_template, request, redirect, url_for, flash
from pymongo import MongoClient
import os
import logging
from config import Config
from utils.webpage_utils import CreateLectureForm
from utils import db_utils
from utils.db_utils import User, Class, Lecture, Note


app = Flask(__name__)
app.config.from_object(Config)

logging.basicConfig(filename="example.log", level=logging.DEBUG)
client = MongoClient(os.environ.get('MONGODB_URI'))
db = client[os.environ.get('DATABASE_NAME')]

@app.route('/')
def index():
    logging.warning("SUCK MY NUTS U DUMB CUNT")
    return render_template('index.html')

@app.route('/data/')
def data():
    return render_template('data.html', query=db['data'].find({'flag': 1}))

# @app.route('/home/')
# def home():
#     return render_template('home.html', )

@app.route('/class/<cls>', methods=['GET', 'POST'])
def classpage(cls):
    form = CreateLectureForm(request.form)

    if request.method == 'POST':
        if form.validate():
            lecture = Lecture(name=request.form['title'], date=request.form['date'], cls=cls)
            success = db_utils.insert(lecture, db)
    return render_template(
        'class.html',
        info=db['Classes'].find_one({'Name': cls}),
        lectures=db['Lectures'].find({'cls': cls}),
        form=form
    )
