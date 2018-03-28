from flask import Flask
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from pymongo import MongoClient
import os
from config import Config

import logging

from utils.webpage_utils import CreateLectureForm
from utils import db_utils
from utils.db_utils import User, Class, Lecture, Note

import urllib.parse
from werkzeug import security
from flask_oauthlib.client import OAuth

import requests

app = Flask(__name__)
app.config.from_object(Config)

client = MongoClient(os.environ.get('MONGODB_URI'))
db = client[os.environ.get('DATABASE_NAME')]

def create_client(app):

    oauth = OAuth(app)

    ok_server = app.config['OK_SERVER']

    remote = oauth.remote_app(
        'ok-server',  # Server Name
        consumer_key=app.config['CLIENT_ID'],
        consumer_secret=app.config['CLIENT_SECRET'],
        request_token_params={'scope': 'all',
                              'state': lambda: security.gen_salt(10)},
        base_url='{0}/api/v3/'.format(ok_server),
        request_token_url=None,
        access_token_method='POST',
        access_token_url='{0}/oauth/token'.format(ok_server),
        authorize_url='{0}/oauth/authorize'.format(ok_server)
    )

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/login')
    def login():
        if app.config['OK_MODE'] == 'bypass':
            return redirect(url_for('home'))
        return remote.authorize(callback=url_for('authorized', _external=True))

    @app.route('/logout')
    def logout():
        session.pop('dev_token', None)
        return redirect(url_for('index'))

    @app.route('/authorized')
    def authorized():
        resp = remote.authorized_response()
        if resp is None:
            return 'Access denied: error=%s' % (
                request.args['error']
            )
        if isinstance(resp, dict) and 'access_token' in resp:
            session['dev_token'] = (resp['access_token'], '')
            r = requests.get('{0}/api/v3/user/?access_token={1}'.format(
                    app.config['OK_SERVER'],
                    session['dev_token'][0]
                )
            )
            ok_resp = r.json()
            if ok_resp and 'data' in ok_resp:
                ok_data = ok_resp['data']
                User.register_user(ok_data, db)
                return redirect(url_for('home'))
        return redirect(url_for('error'))

    @remote.tokengetter
    def get_oauth_token():
        return session.get('dev_token')

    def get_ok_id():
        if app.config['OK_MODE'] == 'bypass':
            return app.config['TESTING_OK_ID']
        else:
            token = session['dev_token'][0]
            r = requests.get('{0}/api/v3/user/?access_token={1}'.format(
                    app.config['OK_SERVER'],
                    token
                )
            )
            ok_resp = r.json()
            if ok_resp and 'data' in ok_resp:
                ok_data = ok_resp['data']
                return ok_data['id']

    def get_user_data():
        ok_id = get_ok_id()
        if ok_id:
            db_result = db['Users'].find_one({'ok_id': ok_id}) or {}
            return db_result

    @app.route('/home/')
    def home():
        db_result = get_user_data()
        if db_result:
            return render_template('home.html', query=db_result.items())
        return redirect(url_for('error'))

    @app.route('/class/<cls>/lecture/<lesson>')
    def lecture(cls, lesson):
        lecture_obj = db['Lectures'].find_one({'url_name': lesson})
        cls_obj = db['Classes'].find_one({'Name': cls})
        question_obj = db['Questions'].find_one({'lecture_name': lecture_obj['name']})
        if lecture:
            url = urllib.parse.urlparse(lecture_obj['link'])
            params = urllib.parse.parse_qs(url.query)
            if 'v' in params:
                return render_template(
                    'lecture.html',
                    id=params['v'][0],
                    lecture=lecture_obj['_id'],
                    user=get_user_data()['_id'],
                    cls=cls_obj['_id'],
                    questions=question_obj['questions']
                )
        return redirect(url_for('error'))


    @app.route('/class/<class_name>', methods=['GET', 'POST'])
    def classpage(class_name):
        form = CreateLectureForm(request.form)

        if request.method == 'POST':
            cls = db['Classes'].find_one({'Name': class_name})
            num_lectures = len(cls['Lectures'])
            if form.validate():
                lecture = Lecture(
                    name=request.form['title'],
                    url_name=db_utils.encode_url(request.form['title']),
                    date=request.form['date'],
                    link=request.form['link'],
                    lecture_number=num_lectures,
                    cls=class_name
                )
                success = Class.add_lecture(cls, lecture, db)
            else:
                flash('All fields required')
        cls = db['Classes'].find_one({'Name': class_name})
        return render_template(
            'class.html',
            info=cls,
            lectures=[db['Lectures'].find_one({'_id': lecture_id}) for lecture_id in cls['Lectures']],
            form=form
        )

    @app.route('/write_question')
    def write_question():
        if request.method == 'POST':
            print(request.data)

    @app.route('/error')
    def error():
        return 'SUCK MY NUTS'

create_client(app)
