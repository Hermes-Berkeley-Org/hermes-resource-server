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
from utils.app_utils import get_curr_semester, partition, generate_partition_titles
from utils.db_utils import User, Class, Lecture, Note, Question, Answer
from utils.transcribe_utils import transcribe, get_youtube_id, get_video_duration
from utils.textbook_utils import CLASSIFIERS

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

logger = logging.getLogger('app_logger')
logger.setLevel(logging.INFO)

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
        logger.info("Successfully routed to index.")
        return render_template('index.html')

    @app.route('/about')
    def about():
        if not get_user_data():
            session['logged_in'] = False
        logger.info("Successfully routed to index.")
        return render_template('about.html')


    @app.route('/login')
    def login():
        if app.config['OK_MODE'] == 'bypass':
            session['logged_in'] = True
            logger.info("Successfully bypassed login.")
            return redirect(url_for('home'))
        logger.info("Authorizing user.")
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
        logger.info("Successfully logged out user.");
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
                logger.info("Authorization successful.")
                return redirect(url_for('home'))
        logger.info("Authorization failed.")
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
            if 'dev_token' in session:
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
        user = get_user_data()
        def validate(participation):
            participation['semester'] = Class.get_semester(participation['offering'])
            participation['class_exists'] = db[Class.collection].find({'ok_id': participation['ok_id']}).count() > 0
            return participation['role'] == consts.INSTRUCTOR or \
                participation['class_exists']
        if user:
            classes = [participation for participation in user['classes'] if validate(participation)]
            return render_template(
                'home.html',
                user=user,
                classes=classes,
                curr_semester=get_curr_semester()
            )
        logger.info("Displaying home.")
        return redirect(url_for('index'))

    @app.route('/class/<cls>/lecture/<lecture_number>/', defaults={'playlist_number': None})
    @app.route('/class/<cls>/lecture/<lecture_number>/<playlist_number>')
    def lecture(cls, lecture_number, playlist_number=None):
        logger.info(playlist_number)
        cls_obj = db['Classes'].find_one({'ok_id': int(cls)})
        lecture_obj = db['Lectures'].find_one({'cls': cls, 'lecture_number': int(lecture_number)})
        user = get_user_data()
        questions_interval = 30
        if playlist_number is None:
            preds = lecture_obj.get('preds')
            if not preds:
                preds = [(None, [0, len(lecture_obj['transcript'])])]
            id=get_youtube_id(lecture_obj['link'])
            transcript = lecture_obj['transcript']
            partition_titles = list(generate_partition_titles(lecture_obj['duration'], questions_interval))
            duration=lecture_obj['duration']
            num_videos = 1
        else:
            play_num = int(playlist_number)
            link = "https://www.youtube.com/watch?v=" + lecture_obj["videos"][play_num]
            preds = lecture_obj.get('preds')[play_num]
            if not preds:
                preds = [(None, [0, len(lecture_obj['transcript'])])]
            id=get_youtube_id(link)
            transcript = lecture_obj['transcript'][play_num]
            partition_titles= list(generate_partition_titles(lecture_obj['duration'][play_num], questions_interval))
            duration = lecture_obj['duration'][play_num]
            num_videos = len(lecture_obj['videos'])
        if lecture_obj and cls_obj:
            return render_template(
                'lecture.html',
                id=id,
                lecture=str(lecture_obj['_id']),
                name=lecture_obj['name'],
                transcript=transcript,
                preds=preds,
                cls_name=cls_obj['display_name'],
                user=user,
                questions_interval=questions_interval,
                partition=partition,
                partition_titles=partition_titles,
                duration=duration,
                user_id=str(user['_id']),
                role=get_role(cls)[0],
                consts=consts,
                cls=str(cls_obj['_id']),
                playlist_number=playlist_number,
                num_videos = num_videos,
                lecture_num = lecture_number,
                cls_num = cls,
                db=db,
                api_key=app.config['HERMES_API_KEY']
            )
            logger.info("Displaying Playlist lecture. It is the ", play_num, " video in the playlist")
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
                    API_SERVICE_NAME, API_VERSION, credentials=credentials, cache_discovery=False)

        if request.method == 'POST':
            if role != consts.INSTRUCTOR:
                logger.info("Error: user access level is %s", role)
                redirect(url_for('error', code=403))
            if form.validate():
                num_lectures = len(cls['lectures'])
                ses = requests.Session()
                url = ses.head(request.form["link"], allow_redirects=True).url
                if "list=" in url:
                    is_playlist = True
                    youtube_id = url.split("list=")[1]
                    youtube_id = youtube_id.split("&")[0]
                    logger.info("youtube_id " + youtube_id)
                    youtube_vid=youtube.playlistItems().list(
                        part='contentDetails',
                        maxResults=25,
                        playlistId= youtube_id
                    ).execute()
                    youtube_vid= [vid["contentDetails"]["videoId"] for vid in youtube_vid["items"]]
                elif "v=" in url:
                    youtube_vid= request.form['link']
                    is_playlist = False
                else:
                    logger.info("Enter a valid link")
                    redirect(url_for('error', code=403))
                lecture = Lecture(
                    name=request.form['title'],
                    url_name=db_utils.encode_url(request.form['title']),
                    date=request.form['date'],
                    link=request.form['link'],
                    lecture_number=num_lectures,
                    is_playlist= is_playlist,
                    duration=get_video_duration(youtube_vid, is_playlist),
                    cls=class_ok_id,
                    videos = youtube_vid
                )
                id = Class.add_lecture(cls, lecture, db)

                ts_classifier = None
                if cls['display_name'] in CLASSIFIERS:
                    ts_classifier = CLASSIFIERS[cls['display_name']](db, cls['ok_id'])
                if(not is_playlist):
                    transcript, preds = transcribe(
                        request.form['link'],
                        app.config['TRANSCRIPTION_MODE'],
                        is_playlist = False,
                        youtube=youtube,
                        transcription_classifier=ts_classifier,
                        error_on_failure=True
                    )
                    Lecture.add_transcript(id, transcript, preds, db)
                else:
                    transcript_lst = []
                    preds_lst = []
                    for vid in youtube_vid:
                        transcript, preds = transcribe(
                            vid,
                            app.config['TRANSCRIPTION_MODE'],
                            is_playlist = True,
                            youtube=youtube,
                            transcription_classifier=ts_classifier,
                            error_on_failure = True
                        )
                        transcript_lst.append(transcript)
                        preds_lst.append(preds)
                    Lecture.add_transcript(id, transcript_lst, preds_lst, db)


            else:
                flash('All fields required')
        return render_template(
            'class.html',
            info=cls,
            lectures=db['Lectures'].find({'cls': class_ok_id}),
            form=form,
            user=user,
            role=role,
            consts=consts,
            api_key=app.config['HERMES_API_KEY']
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
                logger.info("Creating class.")
                return render_template(
                    'create_class.html',
                    init_display_name=data['display_name'],
                    form=form
                )
        else:
            logger.info("Error: user access level is %s", role)
            return redirect(url_for('error'), code=403)

    @app.route('/delete_lecture', methods=['GET', 'POST'])
    def delete_lecture():
        if request.method == 'POST':
            if request.form['api_key'] == app.config['HERMES_API_KEY']:
                Lecture.delete_lecture(request.form.to_dict(), db)
                logger.info("Successfully deleted lecture.")
                return jsonify(success=True), 200
            else:
                return jsonify(success=False), 403
        else:
            logger.info("Illegal request type: %s", request.method)
            return redirect(url_for('error', code=500))

    @app.route('/write_question', methods=['GET', 'POST'])
    def write_question():
        if request.method == 'POST':
            if request.form['api_key'] == app.config['HERMES_API_KEY']:
                Question.write_question(request.form.to_dict(), db)
                logger.info("Successfully wrote question.")
                return jsonify(success=True), 200
            else:
                return jsonify(success=False), 403
        else:
            logger.info("Illegal request type: %s", request.method)
            return redirect(url_for('error', code=500))

    @app.route('/delete_question', methods=['GET', 'POST'])
    def delete_question():
        if request.method == 'POST':
            if request.form['api_key'] == app.config['HERMES_API_KEY']:
                Question.delete_question(request.form.to_dict(), db)
                logger.info("Successfully deleted question.")
                return jsonify(success=True), 200
            else:
                return jsonify(success=False), 403
        else:
            logger.info("Illegal request type: %s", request.method)
            return redirect(url_for('error', code=500))

    @app.route('/edit_question', methods=['GET', 'POST'])
    def edit_question():
        if request.method == 'POST':
            if request.form['api_key'] == app.config['HERMES_API_KEY']:
                Question.edit_question(id, request.form.to_dict(), db)
                logger.info("Successfully edited question.")
                return jsonify(success=True), 200
            else:
                return jsonify(success=False), 403
        else:
            logger.info("Illegal request type: %s", request.method)
            return redirect(url_for('error', code=500))

    @app.route('/upvote_question', methods=['GET', 'POST'])
    def upvote_question():
        if request.method == 'POST':
            if request.form['api_key'] == app.config['HERMES_API_KEY']:
                Question.upvote_question(request.form.to_dict(), db)
                logger.info("Successfully upvoted question.")
                return jsonify(success=True), 200
            else:
                return jsonify(success=False), 403
        else:
            logger.info("Illegal request type: %s", request.method)
            return redirect(url_for('error', code=500))

    @app.route('/write_answer', methods=['GET', 'POST'])
    def write_answer():
        if request.method == 'POST':
            if request.form['api_key'] == app.config['HERMES_API_KEY']:
                Answer.write_answer(get_user_data(), request.form.to_dict(), db)
                logger.info("Successfully wrote answer.")
                return jsonify(success=True), 200
            else:
                return jsonify(success=False), 403
        else:
            logger.info("Illegal request type: %s", request.method)
            return redirect(url_for('error', code=500))

    @app.route('/delete_answer', methods=['GET', 'POST'])
    def delete_answer():
        if request.method == 'POST':
            if request.form['api_key'] == app.config['HERMES_API_KEY']:
                Answer.delete_answer(request.form.to_dict(), db)
                logger.info("Successfully deleted answer.")
                return jsonify(success=True), 200
            else:
                return jsonify(success=False), 403
        else:
            logger.info("Illegal request type: %s", request.method)
            return redirect(url_for('error', code=500))

    @app.route('/edit_answer', methods=['GET', 'POST'])
    def edit_answer():
        if request.method == 'POST':
            if request.form['api_key'] == app.config['HERMES_API_KEY']:
                Answer.edit_answer(request.form.to_dict(), db)
                logger.info("Successfully edited answer.")
                return jsonify(success=True), 200
            else:
                return jsonify(success=False), 403
        else:
            logger.info("Illegal request type: %s", request.method)
            return redirect(url_for('error', code=500))

    @app.route('/edit_transcript', methods=['GET', 'POST'])
    def edit_transcript():
        if request.method == 'POST':
            if request.form['api_key'] == app.config['HERMES_API_KEY']:
                Lecture.edit_transcript(request.form.to_dict(), db)
                logger.info("Successfully edited transcript.")
                return jsonify(success=True), 200
            else:
                return jsonify(success=False), 403
        else:
            logger.info("Illegal request type: %s", request.method)
            return redirect(url_for('error', code=500))

    @app.route('/upvote_answer', methods=['GET', 'POST'])
    def upvote_answer():
        if request.method == 'POST':
            if request.form['api_key'] == app.config['HERMES_API_KEY']:
                Answer.upvote_answer(request.form.to_dict(), db)
                logger.info("Successfully upvoted answer.")
                return jsonify(success=True), 200
            else:
                return jsonify(success=False), 403
        else:
            logger.info("Illegal request type: %s", request.method)
            return redirect(url_for('error', code=500))

    @app.template_filter('exclude')
    def exclude(lst, excl):
        ret = []
        for elem in lst:
            flag = True
            for tup in excl:
                if elem[tup[0]] == tup[1]:
                    flag = False
                    break
            if flag:
                ret.append(elem)
        return ret

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
