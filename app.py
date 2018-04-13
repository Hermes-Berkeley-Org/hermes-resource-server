from flask import Flask
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from pymongo import MongoClient
import os
from config import Config

from datetime import datetime

from bson.objectid import ObjectId

import logging

from utils.webpage_utils import CreateLectureForm, CreateClassForm
from utils import db_utils
from utils.db_utils import User, Class, Lecture, Note, Question, Answer
from utils.transcribe_utils import transcribe, get_youtube_id

import consts

import urllib.parse
from werkzeug import security
from flask_oauthlib.client import OAuth

import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery

import requests

app = Flask(__name__)
app.config.from_object(Config)

client = MongoClient(os.environ.get('MONGODB_URI'))
db = client[os.environ.get('DATABASE_NAME')]

CLIENT_SECRETS_FILE = 'keys/client_secret.json'

SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'

def create_client(app):

    oauth = OAuth(app)

    ok_server = app.config['OK_SERVER']

    remote = oauth.remote_app(
        'ok-server',  # Server Name
        consumer_key=app.config['CLIENT_ID'],
        consumer_secret=app.config['CLIENT_SECRET'],
        request_token_params={'scope': 'email',
                              'state': lambda: security.gen_salt(10)},
        base_url='{0}/api/v3/'.format(ok_server),
        request_token_url=None,
        access_token_method='POST',
        access_token_url='{0}/oauth/token'.format(ok_server),
        authorize_url='{0}/oauth/authorize'.format(ok_server)
    )

    @app.route('/')
    def index():
        if not get_user_data():
            session['logged_in'] = False
        return render_template('index.html')

    @app.route('/login')
    def login():
        if app.config['OK_MODE'] == 'bypass':
            session['logged_in'] = True
            return redirect(url_for('home'))
        return remote.authorize(callback=url_for('authorized', _external=True))

    @app.route('/logout')
    def logout():
        user = get_user_data()
        if user:
            User.remove_google_credentials(get_user_data()['_id'], db)
        if 'dev_token' in session:
            session.pop('dev_token', None)
        session['logged_in'] = False
        if 'google_credentials' in session:
            del session['google_credentials']
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
                session['logged_in'] = True
                return redirect(url_for('home'))
        return redirect(url_for('error', code=403))

    @app.route('/google_authorize')
    def google_authorize():
        # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow steps.
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE, scopes=SCOPES)

        flow.redirect_uri = url_for(
            'google_authorized',
            _external=True
        )

        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )

        session['state'] = state
        session['class_oauth_redirect'] = request.args.get('class_ok_id')
        return redirect(authorization_url)

    @app.route('/google_authorized')
    def google_authorized():
        state = session['state']

        class_ok_id = session['class_oauth_redirect']

        session.pop('class_oauth_redirect', None)

        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
        flow.redirect_uri = url_for('google_authorized', _external=True)

        authorization_response = request.url
        flow.fetch_token(authorization_response=authorization_response)

        credentials = flow.credentials
        user = get_user_data()
        credentials = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        User.add_admin_google_credentials(user['_id'], credentials, db)
        return redirect(url_for('classpage', class_ok_id=class_ok_id))

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
                if 'id' in ok_data:
                    return ok_data['id']

    def get_user_data():
        if not session.get('logged_in'):
            return
        ok_id = get_ok_id()
        if ok_id:
            db_result = db['Users'].find_one({'ok_id': ok_id}) or {}
            return db_result

    @app.route('/home/')
    def home():
        def get_curr_semester():
            today = datetime.today()
            month, year = today.month, today.year
            def get_season(month):
                if month < 6:
                    return 'SP'
                elif month < 8:
                    return 'SU'
                else:
                    return 'FA'
            return '{0}{1}'.format(get_season(month), str(year)[-2:])
        user = get_user_data()
        def validate(participation):
            participation['semester'] = Class.get_semester(participation['offering'])
            participation['class_exists'] = db[Class.collection].find({'ok_id': participation['ok_id']}).count() > 0
            return participation['role'] == consts.INSTRUCTOR or \
                participation['class_exists']
        if user:
            classes = [participation for participation in user['classes'] if validate(participation)]
            print(classes)
            return render_template(
                'home.html',
                user=user,
                classes=classes,
                curr_semester=get_curr_semester()
            )
        return redirect(url_for('index'))

    @app.route('/class/<cls>/lecture/<lecture_number>')
    def lecture(cls, lecture_number):
        cls_obj = db['Classes'].find_one({'ok_id': int(cls)})
        lecture_obj = db['Lectures'].find_one({'cls': cls, 'lecture_number': int(lecture_number)})
        user = get_user_data()
        if lecture_obj and cls_obj:
            return render_template(
                'lecture.html',
                id=get_youtube_id(lecture_obj['link']),
                lecture=str(lecture_obj['_id']),
                name=lecture_obj['name'],
                transcript=lecture_obj['transcript'],
                cls_name=lecture_obj['cls'],
                user=user,
                role=get_role(cls)[0],
                consts=consts,
                cls=str(cls_obj['_id']),
                db=db
            )
        return redirect(url_for('error', code=404))

    def get_role(class_ok_id):
        user = get_user_data()
        for participation in user['classes']:
            if participation['ok_id'] == int(class_ok_id):
                return participation['role'], participation

    @app.route('/class/<class_ok_id>', methods=['GET', 'POST'])
    def classpage(class_ok_id):

        form = CreateLectureForm(request.form)
        user = get_user_data()

        youtube = None

        role, data = get_role(class_ok_id)

        cls = db['Classes'].find_one({'ok_id': int(class_ok_id)})

        if role == consts.INSTRUCTOR:
            if not user.get('google_credentials'):
                return redirect(url_for('google_authorize', class_ok_id=class_ok_id))
            else:
                credentials = google.oauth2.credentials.Credentials(
                    **user['google_credentials']
                )
                youtube = googleapiclient.discovery.build(
                    API_SERVICE_NAME, API_VERSION, credentials=credentials)

        if request.method == 'POST':
            if role != consts.INSTRUCTOR:
                redirect(url_for('error', code=403))
            num_lectures = len(cls['lectures'])
            if form.validate():
                lecture = Lecture(
                    name=request.form['title'],
                    url_name=db_utils.encode_url(request.form['title']),
                    date=request.form['date'],
                    link=request.form['link'],
                    lecture_number=num_lectures,
                    cls=class_ok_id
                )
                id = Class.add_lecture(cls, lecture, db)
                transcript = transcribe(
                    request.form['link'],
                    app.config['TRANSCRIPTION_MODE'],
                    youtube=youtube
                )
                Lecture.add_transcript(id, transcript, db)
            else:
                flash('All fields required')
        return render_template(
            'class.html',
            info=cls,
            lectures=[db['Lectures'].find_one({'_id': lecture_id}) for lecture_id in cls['lectures']],
            form=form,
            user=user,
            role=role,
            consts=consts
        )


    @app.route('/create_class/<class_ok_id>', methods=['GET', 'POST'])
    def create_class(class_ok_id):
        form = CreateClassForm(request.form)

        role, data = get_role(class_ok_id)
        if role == consts.INSTRUCTOR:
            if request.method == 'POST':
                if form.validate():
                    Class.create_class(request.form['class_name'], data, db)
                else:
                    flash('All fields required')
                return redirect(url_for('classpage', _external=True, class_ok_id=class_ok_id))
            else:
                return render_template(
                    'create_class.html',
                    init_display_name=data['display_name'],
                    form=form
                )
        else:
            return redirect(url_for('error'), code=403)

    @app.route('/write_question', methods=['GET', 'POST'])
    def write_question():
        if request.method == 'POST':
            Question.write_question(request.form.to_dict(), db)
            return jsonify(success=True), 200
        else:
            return redirect(url_for('error', code=500))

    @app.route('/edit_question', methods=['GET', 'POST'])
    def edit_question():
        if request.method == 'POST':
            Question.edit_question(id, request.form.to_dict(), db)
            return jsonify(success=True), 200
        else:
            return redirect(url_for('error', code=500))

    @app.route('/write_answer', methods=['GET', 'POST'])
    def write_answer():
        if request.method == 'POST':
            Answer.write_answer(get_user_data(), request.form.to_dict(), db)
            return jsonify(success=True), 200
        else:
            return redirect(url_for('error', code=500))

    @app.route('/edit_answer', methods=['GET', 'POST'])
    def edit_answer():
        if request.method == 'POST':
            Answer.edit_answer(request.form.to_dict(), db)
            return jsonify(success=True), 200
        else:
            return redirect(url_for('error', code=500))

    @app.route('/upvote_answer', methods=['GET', 'POST'])
    def upvote_answer():
        if request.method == 'POST':
            Answer.upvote_answer(request.form.to_dict(), db)
            return jsonify(success=True), 200
        else:
            return redirect(url_for('error', code=500))

    @app.errorhandler(404)
    def page_not_found(e):
    	return redirect(url_for('error', code=404))

    @app.errorhandler(403)
    def forbidden(e):
    	return redirect(url_for('error', code=403))

    @app.errorhandler(500)
    def internal_server_error(e):
    	return redirect(url_for('error', code=500))

    @app.route('/error/<code>')
    def error(code):
    	if code == '404':
    		return render_template('404.html')
    	elif code == '403':
    		return render_template('403.html')
    	elif code == '500':
    		return render_template('500.html')


create_client(app)
