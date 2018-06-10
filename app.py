from flask import Flask
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from pymongo import MongoClient
import os
from config import Config

from datetime import datetime

from bson.objectid import ObjectId

import logging

from utils.webpage_utils import CreateLectureForm, CreateClassForm
from utils import db_utils, app_utils
from utils.db_utils import User, Class, Lecture, Note, Question, Answer
from utils.transcribe_utils import transcribe, get_youtube_id, get_video_duration, get_video_titles, get_playlist_titles, get_playlist_video_duration
from utils.textbook_utils import CLASSIFIERS

import consts

import urllib.parse
from werkzeug import security
from flask_oauthlib.client import OAuth

from functools import wraps

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

    @app.before_request
    def before_request():
        if 'localhost' in request.host_url or '0.0.0.0' in request.host_url:
            app.jinja_env.cache = {}

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

    def login_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if get_user_data() is None:
                return redirect(url_for('login', next=request.url))
            return f(*args, **kwargs)
        return decorated_function

    def validate_user(user_id, class_ok_id, role):
        def user_role_matches():
            supposed_role, data = get_role(class_ok_id, user_id=user_id)
            return supposed_role and \
                consts.OK_ROLES.index(supposed_role) >= consts.OK_ROLES.index(role)
        def user_matches_logged_in_user():
            logged_in_user = get_user_data()
            return logged_in_user and str(logged_in_user.get('_id')) == user_id
        user_role_match = user_role_matches()
        logged_in_user_match = user_matches_logged_in_user()
        if not user_role_match:
            logger.info("User does not have clearance to authorize as {0}".format(role))
        if not logged_in_user_match:
            logger.info("User does not match logged in user")
        return user_role_match and logged_in_user_match

    def post_on_behalf_of(role):
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if request.method == 'POST':
                    data = request.form.to_dict()
                    user_id, class_ok_id = data.get('user_id'), data.get('class_ok_id')
                    if user_id and class_ok_id and validate_user(user_id, class_ok_id, role):
                        logger.info("Successfully authenticated a " + role)
                        return f(*args, **kwargs)
                    else:
                        logger.info("Authentication for {0} rejected".format(role))
                        return jsonify(success=False), 403
                else:
                    logger.info("Illegal request type: %s", request.method)
                    return redirect(url_for('error', code=500))
            return decorated_function
        return decorator

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

    def get_user_data(user_id=None):
        if not session.get('logged_in'):
            return
        if user_id:
            return db_utils.find_one_by_id(user_id, User.collection, db)
        ok_id = get_ok_id()
        if ok_id:
            db_result = db[User.collection].find_one({'ok_id': ok_id}) or {}
            return db_result

    @app.route('/home/')
    @login_required
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
                curr_semester=app_utils.get_curr_semester()
            )
        logger.info("Displaying home.")
        return redirect(url_for('index'))

    @app.route('/class/<cls>/lecture/<lecture_number>/', defaults={'playlist_number': None})
    @app.route('/class/<cls>/lecture/<lecture_number>/<playlist_number>')
    @login_required
    def lecture(cls, lecture_number, playlist_number=None):
        logger.info(playlist_number)
        cls_obj = db['Classes'].find_one({'ok_id': int(cls)})
        lecture_obj = db['Lectures'].find_one(
            {'cls': cls, 'lecture_number': int(lecture_number)}
        )
        user = get_user_data()
        user['role'], data = get_role(cls)
        questions_interval = 30
        lecture_obj['lecture_number'] = lecture_number
        video_info = {}
        if not playlist_number:
            preds = lecture_obj.get('preds')
            if not preds:
                preds = [(None, [0, len(lecture_obj['transcript']) // 2 + 1])]
            video_info['video_id'] = get_youtube_id(lecture_obj['link'])
            transcript = lecture_obj['transcript']
            video_info['partition_titles'] = list(
                app_utils.generate_partition_titles(
                    lecture_obj['duration'],
                    questions_interval
                )
            )
            video_info['duration'] = lecture_obj['duration']
            video_info['num_videos'] = 1
        else:
            play_num = int(playlist_number)
            link = "https://www.youtube.com/watch?v=" + lecture_obj["videos"][play_num]
            preds = lecture_obj.get('preds')[play_num]
            if not preds:
                preds = [(None, [0, len(lecture_obj['transcript'][play_num]) // 2 + 1])]
            video_info['video_id'] = get_youtube_id(link)
            transcript = lecture_obj['transcript'][play_num]
            video_info['partition_titles'] = list(
                app_utils.generate_partition_titles(
                    lecture_obj['duration'][play_num],
                    questions_interval
                )
            )
            video_info['duration'] = lecture_obj['duration'][play_num]
            video_info['num_videos'] = len(lecture_obj['videos'])
        if lecture_obj and cls_obj:
            logger.info("Displaying lecture.")
            if playlist_number:
                logger.info("It is the ", play_num, " video in the playlist")
            return render_template(
                'lecture.html',
                video_info=video_info,
                playlist_number=playlist_number,
                lecture=lecture_obj,
                transcript=transcript,
                preds=preds,
                cls=cls_obj,
                user=user,
                questions_interval=questions_interval,
                app_utils=app_utils,
                consts=consts,
                db=db,
                api_key=app.config['HERMES_API_KEY']
            )
        return redirect(url_for('error', code=404))

    def get_role(class_ok_id, user_id=None):
        user = get_user_data(user_id=user_id)
        if user:
            for participation in user['classes']:
                if participation['ok_id'] == int(class_ok_id):
                    return participation['role'], participation
        return None, None

    @app.route('/class/<class_ok_id>', methods=['GET', 'POST'])
    @login_required
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
                try:
                    test_response = youtube.search().list(
                        q='test',
                        part='id,snippet'
                    ).execute()
                except:
                    return redirect(url_for('google_authorize', class_ok_id=class_ok_id))

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
                    youtube_vids=youtube.playlistItems().list(
                        part='contentDetails',
                        maxResults=25,
                        playlistId= youtube_id
                    ).execute()
                    youtube_vid= [vid["contentDetails"]["videoId"] for vid in youtube_vids["items"]]
                    duration = get_playlist_video_duration(youtube_vid)
                    title = get_playlist_titles(youtube_vid, youtube)
                elif "v=" in url:
                    youtube_vid= request.form['link']
                    is_playlist = False
                    duration = get_video_duration(youtube_vid)
                    title = get_video_titles(youtube_vid, youtube)
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
                    duration=duration,
                    cls=class_ok_id,
                    videos = youtube_vid,
                    vid_title = title
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

    @app.route('/delete_lecture', methods=['POST'])
    @post_on_behalf_of(consts.INSTRUCTOR)
    def delete_lecture():
        Lecture.delete_lecture(request.form.to_dict(), db)
        logger.info("Successfully deleted lecture.")
        return jsonify(success=True), 200

    @app.route('/write_question', methods=['POST'])
    @post_on_behalf_of(consts.STUDENT)
    def write_question():
        Question.write_question(request.form.to_dict(), db)
        logger.info("Successfully wrote question.")
        return jsonify(success=True), 200

    @app.route('/delete_question', methods=['POST'])
    @post_on_behalf_of(consts.STUDENT)
    def delete_question():
        role, data = get_role(request.form.get('class_ok_id'))
        is_instructor = (role == consts.INSTRUCTOR)
        Question.delete_question(request.form.to_dict(), db, is_instructor)
        logger.info("Successfully deleted question.")
        return jsonify(success=True), 200

    @app.route('/edit_question', methods=['POST'])
    @post_on_behalf_of(consts.STUDENT)
    def edit_question():
        role, data = get_role(request.form.get('class_ok_id'))
        is_instructor = (role == consts.INSTRUCTOR)
        Question.edit_question(request.form.to_dict(), db, is_instructor)
        logger.info("Successfully edited question.")
        return jsonify(success=True), 200

    @app.route('/upvote_question', methods=['POST'])
    @post_on_behalf_of(consts.STUDENT)
    def upvote_question():
        Question.upvote_question(request.form.to_dict(), db)
        logger.info("Successfully upvoted question.")
        return jsonify(success=True), 200

    @app.route('/write_answer', methods=['POST'])
    @post_on_behalf_of(consts.STUDENT)
    def write_answer():
        Answer.write_answer(get_user_data(), request.form.to_dict(), db)
        logger.info("Successfully wrote answer.")
        return jsonify(success=True), 200

    @app.route('/delete_answer', methods=['POST'])
    @post_on_behalf_of(consts.STUDENT)
    def delete_answer():
        role, data = get_role(request.form.get('class_ok_id'))
        is_instructor = (role == consts.INSTRUCTOR)
        Answer.delete_answer(request.form.to_dict(), db, is_instructor)
        logger.info("Successfully deleted answer.")
        return jsonify(success=True), 200

    @app.route('/edit_answer', methods=['POST'])
    @post_on_behalf_of(consts.STUDENT)
    def edit_answer():
        role, data = get_role(request.form.get('class_ok_id'))
        is_instructor = (role == consts.INSTRUCTOR)
        Answer.edit_answer(request.form.to_dict(), db, is_instructor)
        logger.info("Successfully edited answer.")
        return jsonify(success=True), 200

    @app.route('/edit_transcript', methods=['POST'])
    @post_on_behalf_of(consts.STUDENT)
    def edit_transcript():
        Lecture.suggest_transcript(request.form.to_dict(), db)
        logger.info("Successfully edited transcript.")
        return jsonify(success=True), 200

    @app.route('/upvote_answer', methods=['POST'])
    @post_on_behalf_of(consts.STUDENT)
    def upvote_answer():
        Answer.upvote_answer(request.form.to_dict(), db)
        logger.info("Successfully upvoted answer.")
        return jsonify(success=True), 200

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
