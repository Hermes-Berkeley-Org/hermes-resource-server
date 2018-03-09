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

    @app.route('/home/')
    def home():
        token = session['dev_token'][0]
        r = requests.get('{0}/api/v3/user/?access_token={1}'.format(
                app.config['OK_SERVER'],
                token
            )
        )
        ok_resp = r.json()
        if ok_resp and 'data' in ok_resp:
            ok_data = ok_resp['data']
            ok_id = ok_data['id']
            db_result = db['Users'].find_one({'ok_id': ok_id}) or {}
            return render_template('home.html', query=db_result.items())
        return redirect(url_for('error'))


    @app.route('/class/<cls>', methods=['GET', 'POST'])
    def classpage(cls):
        form = CreateLectureForm(request.form)

        if request.method == 'POST':
            if form.validate():
                lecture = Lecture(name=request.form['title'], date=request.form['date'], cls=cls)
                success = db_utils.insert(lecture, db)
            else:
                flash('All fields required')
        return render_template(
            'class.html',
            info=db['Classes'].find_one({'Name': cls}),
            lectures=db['Lectures'].find({'cls': cls}),
            form=form
        )

create_client(app)

    # @app.route('/students')
    # def students():


# if __name__ == '__main__':


# @app.route('/class/<cls>/lecture/<lec>')
# def lecturepage(cls, date):
#     classobj = db['Classes'].find_one({'Name' : cls})
#     return render_template('lecture.html', name = classobj["name"]))
