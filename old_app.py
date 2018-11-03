from flask import Flask
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from pymongo import MongoClient
import sys
import os
import re
import pprint
from json import dumps as json_dump
from bson.json_util import dumps as bson_dump
from config import Config

from datetime import datetime

from bson.objectid import ObjectId

import logging

from utils.webpage_utils import CreateLectureForm, CreateClassForm
from utils import db_utils, app_utils, transcribe_utils
from utils.db_utils import User, Class, Lecture, Note, Question, Answer, Vitamin, Resource
from utils.textbook_utils import CLASSIFIERS

import consts

from urllib.parse import urlparse, parse_qs
from werkzeug import security
from flask_oauthlib.client import OAuth
from flask_cors import CORS

from functools import wraps

import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery

from google.auth.exceptions import RefreshError
from requests.exceptions import RequestException

import requests

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})
app.config.from_object(Config)

client = MongoClient(os.environ.get('MONGODB_URI'))
db = client[os.environ.get('DATABASE_NAME')]

CLIENT_SECRETS_FILE = 'keys/client_secret.json'

SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'

logger = logging.getLogger('app_logger')
sh = logging.StreamHandler(stream=sys.stdout)
sh.setFormatter(
    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)
logger.addHandler(sh)
logger.setLevel(logging.INFO)


ok_server = app.config['OK_SERVER']
app.secret_key = app.config['SECRET_KEY']

@app.before_request
def before_request():
    if 'localhost' in request.host_url or '0.0.0.0' in request.host_url:
        app.jinja_env.cache = {}

@app.route('/')
def index():
    if not get_user_data():
        # session['logged_in'] = False
        return jsonify(success=False)
    logger.info("Successfully routed to index.")
    return jsonify(success=True)
    # return render_template('index.html')

@app.route('/about')
def about():
    if not get_user_data():
        # session['logged_in'] = False
        return jsonify(success=False)
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
        return supposed_role and consts.OK_ROLES.index(supposed_role) >= consts.OK_ROLES.index(role)
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
        # session['logged_in'] = True
        logger.info("Successfully bypassed login.")
        return redirect(url_for('home'))
    logger.info("Authorizing user.")
    return remote.authorize(callback=url_for('authorized', _external=True))

@app.route('/authorized')
def authorized():
    resp = remote.authorized_response()
    if resp is None:
        return 'Access denied: error=%s' % (
            request.args['error']
        )
    if isinstance(resp, dict) and 'access_token' in resp:
        # session['dev_token'] = (resp['access_token'], '')
        r = requests.get('{0}/api/v3/user/?access_token={1}'.format(
                app.config['OK_SERVER'],
                # session['dev_token'][0]
            )
        )
        ok_resp = r.json()
        if ok_resp and 'data' in ok_resp:
            ok_data = ok_resp['data']
            User.register_user(ok_data, db)
            # session['logged_in'] = True
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

    # session['state'] = state
    # session['class_oauth_redirect'] = request.args.get('class_ok_id')
    return redirect(authorization_url)

@app.route('/google_authorized')
def google_authorized():
    # state = session['state']

    # class_ok_id = session['class_oauth_redirect']

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

def get_oauth_token():
    return request.headers.get('Authorization').replace('Bearer ', '')


def validate_and_pass_on_ok_id(func):
    @wraps(func)
    def get_id(*args, **kwargs):
        if app.config['OK_MODE'] == 'bypass':
            return app.config['TESTING_OK_ID']
        else:
            r = requests.get('{0}/api/v3/user/?access_token={1}'.format(
                app.config['OK_SERVER'],
                get_oauth_token()
                )
            )
            logger.info(r)
            if not r:
                logger.info("Request not allowed")
                return jsonify(success=False), 403
            ok_resp = r.json()
            if ok_resp and 'data' in ok_resp:
                ok_data = ok_resp['data']
                if 'id' in ok_data:
                    return func(ok_id=ok_data['id'], *args,**kwargs)
            return jsonify(success=False), 403
    return get_id

def get_user_data(ok_id):
    if ok_id:
        db_result = db[User.collection].find_one({'ok_id': ok_id}) or {}
        return db_result

def get_updated_user_classes():
    token = get_oauth_token()
    r = requests.get('{0}/api/v3/user/?access_token={1}'.format(
            app.config['OK_SERVER'],
            get_oauth_token()
        )
    )
    ok_resp = r.json()
    if 'data' in ok_resp and 'participations' in ok_resp['data']:
        return ok_resp['data']['participations']

@app.route('/home/')
# @login_required
@validate_and_pass_on_ok_id
def home(ok_id=None):
    def class_exists(participation):
        return db[Class.collection].find({'ok_id': participation['id']}).count() > 0
    def is_instructor(participation):
        return participation['role'] == consts.INSTRUCTOR
    def is_staff_not_instructor(participation):
        return participation['role'] != consts.STUDENT and participation['role'] != consts.INSTRUCTOR
    if ok_id:
        classes = get_updated_user_classes()
        if classes:
            valid_staff_active_classes = []
            valid_staff_inactive_classes = []
            invalid_instructor_active_classes = []
            invalid_instructor_inactive_classes = []
            valid_student_active_classes = []
            valid_student_inactive_classes = []
            for cls in classes:
                exists = class_exists(cls['course'])
                active = cls['course']['active']
                cls['class_exists'] = exists
                if (is_instructor(cls) or is_staff_not_instructor(cls)) and active and exists:
                    valid_staff_active_classes.append(cls)
                elif (is_instructor(cls) or is_staff_not_instructor(cls)) and not active and exists:
                    valid_staff_inactive_classes.append(cls)
                elif is_instructor(cls) and active and not exists:
                    invalid_instructor_active_classes.append(cls)
                elif is_instructor(cls) and not active and not exists:
                    invalid_instructor_inactive_classes.append(cls)
                elif not is_instructor(cls) and not is_staff_not_instructor(cls) and active and exists:
                    valid_student_active_classes.append(cls)
                elif not is_instructor(cls) and not is_staff_not_instructor(cls) and not active and exists:
                    valid_student_inactive_classes.append(cls)
            return json_dump({
                    "user":ok_id,
                    "valid_staff_active_classes":valid_staff_active_classes,
                    "valid_staff_inactive_classes":valid_staff_inactive_classes,
                    "invalid_instructor_active_classes":invalid_instructor_active_classes,
                    "valid_student_active_classes":valid_student_active_classes,
                    "valid_student_inactive_classes":valid_student_inactive_classes,
            })
    return jsonify(success=False), 403
    # return redirect(url_for('index'))

@app.route('/class/<cls>/lecture/<lecture_number>/', defaults={'playlist_number': None})
@app.route('/class/<cls>/lecture/<lecture_number>/<playlist_number>')
# @login_required
@validate_and_pass_on_ok_id
def lecture(cls, lecture_number, ok_id, playlist_number=None):
    cls_obj = db['Classes'].find_one({'ok_id': int(cls)})
    lecture_obj = db['Lectures'].find_one(
        {'cls': cls, 'lecture_number': int(lecture_number)}
    )
    user = get_user_data(ok_id)
    user['role'], data = get_role(cls)
    questions_interval = 30
    lecture_obj['lecture_number'] = lecture_number
    video_info = {}
    if not lecture_obj.get('is_playlist'):
        preds = lecture_obj.get('preds')
        if not preds:
            preds = [(None, [0, len(lecture_obj['transcript']) // 2 + 1])]
        video_info['video_id'] = transcribe_utils.get_youtube_id(lecture_obj['link'])
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
        if not playlist_number:
            return redirect(url_for('error', code=404))
        play_num = int(playlist_number)
        link = "https://www.youtube.com/watch?v={0}".format(
            lecture_obj['youtube_video_ids'][play_num]
        )
        preds = lecture_obj.get('preds')[play_num]
        transcript = lecture_obj['transcripts'][play_num]
        if not preds:
            preds = [(None, [0, len(transcript) // 2 + 1])]
        video_info['video_id'] = transcribe_utils.get_youtube_id(link)
        video_info['partition_titles'] = list(
            app_utils.generate_partition_titles(
                lecture_obj['durations'][play_num],
                questions_interval
            )
        )
        video_info['duration'] = lecture_obj['durations'][play_num]
        video_info['num_videos'] = len(lecture_obj['youtube_video_ids'])
    vitamins = db['Vitamins'].find({'$and':[{'lecture_id': str(lecture_obj["_id"])}, {'playlist_number': str(playlist_number)}]})
    resources = db['Resources'].find({'$and':[{'lecture_id': str(lecture_obj["_id"])}, {'playlist_number': str(playlist_number)}]})
    if lecture_obj and cls_obj:
        logger.info("Displaying lecture.")
        if playlist_number:
            logger.info("It is video {0} in the playlist".format(playlist_number))
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
            vitamins=vitamins,
            resources=resources
        )
    return redirect(url_for('error', code=404))

@app.route('/class/<class_ok_id>/get_role')
@validate_and_pass_on_ok_id
def get_role(class_ok_id, ok_id=None):
    user = get_user_data(ok_id)
    if user:
        for participation in get_updated_user_classes():
            if participation['course']['id'] == int(class_ok_id):
                return json_dump({
                    "role": participation['role']
                })
    return None, None

def add_transcript(cls, lecture, youtube, url):
    ts_classifier = None
    if cls['display_name'] in CLASSIFIERS:
        ts_classifier = CLASSIFIERS[cls['display_name']](db, cls['ok_id'])
    if not lecture.get('is_playlist'):
        try:
            print(url)
            transcript, preds = transcribe_utils.transcribe(
                mode=app.config['TRANSCRIPTION_MODE'],
                youtube_link=url,
                youtube=youtube,
                transcription_classifier=ts_classifier,
            )
            id = Class.add_lecture(cls, lecture, db)
            Lecture.add_transcript(id, transcript, preds, db)
        except ValueError as e:
            flash('There was a problem retrieving the caption track for this video. {0}'.format(consts.NO_CAPTION_TRACK_MESSAGE))
    else:
        transcript_lst = []
        preds_lst = []
        playlist_captions_success = True
        for i, youtube_id in enumerate(lecture.get('youtube_video_ids') or []):
            try:
                transcript, preds = transcribe_utils.transcribe(
                    mode=app.config['TRANSCRIPTION_MODE'],
                    video_id=youtube_id,
                    youtube=youtube,
                    transcription_classifier=ts_classifier,
                    )
                transcript_lst.append(transcript)
                preds_lst.append(preds)
            except ValueError as e:
                flash('There was a problem retrieving the caption track for video {0}. {1}'.format(i, consts.NO_CAPTION_TRACK_MESSAGE))
                playlist_captions_success = False
                break
        if playlist_captions_success:
            id = Class.add_lecture(cls, lecture, db)
            Lecture.add_transcripts(id, transcript_lst, preds_lst, db)

def get_video_info(params, lecture, youtube,link):
    try:
        youtube_id = params['v'][0]
        title, duration = transcribe_utils.get_video_info(youtube_id, youtube)
        if not (title and duration):
            raise ValueError('Video does not have a title or duration')
        lecture.set('duration', duration)
        lecture.set('youtube_video_link', link)
        lecture.set('video_title', title)
        lecture.set('is_playlist', False)
        return True
    except (ValueError, OSError) as e:
        flash('There was a problem with this video')

def get_playlist_info(params, lecture, youtube):
    youtube_id = params['list'][0]
    youtube_vids = youtube.playlistItems().list(
        part='contentDetails',
        maxResults=25,
        playlistId=youtube_id
    ).execute()
    playlist_items = youtube_vids.get('items')
    if playlist_items:
        youtube_ids = [vid["contentDetails"]["videoId"] for vid in playlist_items]
        durations = []
        titles = []
        playlist_success = True
        for i, id in enumerate(youtube_ids):
            try:
                title, duration = transcribe_utils.get_video_info(id, youtube)
                if title and duration:
                    durations.append(duration)
                    titles.append(title)
                else:
                    raise ValueError('Video does not have a title or duration')
            except (ValueError, OSError) as e:
                playlist_success = False
                flash('There was a problem with video {0} in the playlist. Please make sure this video is not deleted or unavailable.'.format(i))
                break
        if playlist_success:
            lecture.set('durations', durations)
            lecture.set('youtube_video_ids', youtube_ids)
            lecture.set('video_titles', titles)
            lecture.set('is_playlist', True)
            return True
    else:
        flash('Something went wrong. Please try again later.')

def submit_lecture(form, user, youtube, role, cls, class_ok_id):
    """
    WtForm form: Form that Professor submits with link, date, title
    param User: User Data
    param Youtube: Youtube API Client
    String role: User's role in the class
    Dictionary cls: Current class's data
    Int class_ok_id: class's ok id
    return: A lecture template

    note:: urlparse takes a url and parse it into an Object with
    various fields (scheme, netloc, path, params, query, and fragment)
    note:: parse_qs takes in a string and parses the query parameters and
    returns a dictionary of the parameters and their values
    """
    if form.validate():
        ses = requests.Session()
        success = False
        url = None
        params = None
        parse_obj = None
        link = request.form['link']
        if not link.startswith('http'):
            link = 'http://{0}'.format(link)
        try:
            url = ses.head(link, allow_redirects=True).url
            parse_obj = urlparse(url)
            logger.info(parse_obj)
            params = parse_qs(parse_obj.query)
            logger.info(params)
        except RequestException as e:
            flash('Please enter a valid URL')
        lecture = Lecture(
            name=request.form['title'],
            url_name=db_utils.encode_url(request.form['title']),
            date=request.form['date'],
            link=url,
            lecture_number=len(cls['lectures']),
            cls=class_ok_id,
        )
        if parse_obj and 'youtube' in parse_obj.netloc and url and params:
            if 'list' in params and len(params['list']) > 0:
                success = get_playlist_info(params, lecture, youtube)
            elif 'v' in params and len(params['v']) > 0:
                success = get_video_info(params, lecture, youtube, link)
            else:
                flash('Please enter a valid YouTube video/playlist')
        if success:
            add_transcript(cls, lecture, youtube, url)
        else:
            flash('Please enter a valid YouTube video/playlist')
    else:
        flash('All fields required')
    return bson_dump({
        info:cls,
        lectures:db['Lectures'].find({'cls': class_ok_id}).sort([('date', 1)]),
        form:form,
        user:user,
        role:role,
        consts:consts,
        api_key:app.config['HERMES_API_KEY']
    })
    # return render_template(
    #     'class.html',
    #     info=cls,
    #     lectures=db['Lectures'].find({'cls': class_ok_id}).sort([('date', 1)]),
    #     form=form,
    #     user=user,
    #     role=role,
    #     consts=consts,
    #     api_key=app.config['HERMES_API_KEY']
    # )

@app.route('/class/<class_ok_id>', methods=['GET', 'POST'])
# @login_required
@validate_and_pass_on_ok_id
def classpage(class_ok_id, ok_id ):

    form = CreateLectureForm(request.form)
    user = get_user_data(ok_id)
    youtube = None
    role, data = get_role(class_ok_id)
    cls = db['Classes'].find_one({'ok_id': int(class_ok_id)})
    if not cls:
        return jsonify(success=False), 403
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
                youtube.search().list(
                    q='test',
                    part='id,snippet'
                ).execute()
            except RefreshError as e:
                return redirect(url_for('google_authorize', class_ok_id=class_ok_id))
    if request.method == 'POST':
        if role != consts.INSTRUCTOR:
            logger.info("Error: user access level is %s", role)
            redirect(url_for('error', code=403))
        return submit_lecture(form, user, youtube, role, cls, class_ok_id)
    return bson_dump({
        "info":cls,
        "lectures":db['Lectures'].find({'cls': class_ok_id}).sort([('date', 1)]),
        "user":user,
        "role":role,
        "api_key":app.config['HERMES_API_KEY']
    })


@app.route('/class/<cls>/edit_lecture/<lecture_number>/', defaults={'playlist_number': None})
@app.route('/class/<cls>/edit_lecture/<lecture_number>/<playlist_number>')
@login_required
def edit_lecture(cls, lecture_number, playlist_number=None):
    cls_obj = db['Classes'].find_one({'ok_id': int(cls)})
    class_ok_id = cls_obj["ok_id"]
    lecture_obj = db['Lectures'].find_one({'cls': cls_obj, 'lecture_number': int(lecture_number)})
    user = get_user_data()
    role, data = get_role(class_ok_id)
    if role == consts.INSTRUCTOR:
        lecture_obj = db['Lectures'].find_one({'cls': cls, 'lecture_number': int(lecture_number)})
        cls_obj = db['Classes'].find_one({'ok_id': int(cls)})
        video_info = {}
        if lecture_obj.get('is_playlist'):
            if not playlist_number:
                return redirect(url_for('error', code=404))
            play_num = int(playlist_number)
            video_info['video_id'] = lecture_obj['youtube_video_ids'][play_num]
            video_info['num_videos'] = len(lecture_obj['youtube_video_ids'])
        else:
            video_info['video_id'] = transcribe_utils.get_youtube_id(lecture_obj['link'])
            video_info['num_videos'] = 1
        vitamins = (db['Vitamins'].find_one({ 'lecture_id': str(lecture_obj.get("_id")), 'playlist_number': str(playlist_number)}))
        questions = (db['Resources'].find_one({ 'lecture_id': str(lecture_obj.get("_id")), 'playlist_number': str(playlist_number)}))
        return (bson_dump({
            "video_info":video_info,
            "user":user,
            "cls":cls_obj,
            "lecture":lecture_obj,
            "playlist_number":playlist_number,
            "vitamins":vitamins,
            "question":questions
        }))
        # return render_template(
        #     'edit_lecture.html',
        #     video_info=video_info,
        #     user=user,
        #     cls=cls_obj,
        #     lecture=lecture_obj,
        #     playlist_number=playlist_number,
        #     db=db
        # )
    else:
        logger.info("Error: user access level is %s", role)
        return redirect(url_for('error'), code=403)

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
            return json_dump({
                init_display_name:data['display_name'],
                form:form
            })
            # return render_template(
            #     'create_class.html',
            #     init_display_name=data['display_name'],
            #     form=form
            # )
    else:
        logger.info("Error: user access level is %s", role)
        return redirect(url_for('error', code=403))

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
    Question.delete_question(
        request.form.to_dict(),
        db,
        has_clearance_for(role, consts.STAFF)
    )
    logger.info("Successfully deleted question.")
    return jsonify(success=True), 200

@app.route('/edit_question', methods=['POST'])
@post_on_behalf_of(consts.STUDENT)
def edit_question():
    role, data = get_role(request.form.get('class_ok_id'))
    Question.edit_question(
        request.form.to_dict(),
        db,
        has_clearance_for(role, consts.STAFF)
    )
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
    Answer.delete_answer(
        request.form.to_dict(),
        db,
        has_clearance_for(role, consts.STAFF)
    )
    logger.info("Successfully deleted answer.")
    return jsonify(success=True), 200

@app.route('/edit_answer', methods=['POST'])
@post_on_behalf_of(consts.STUDENT)
def edit_answer():
    role, data = get_role(request.form.get('class_ok_id'))
    Answer.edit_answer(
        request.form.to_dict(),
        db,
        has_clearance_for(role, consts.STAFF)
    )
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

@app.route('/add_vitamin', methods=['GET', 'POST'])
@post_on_behalf_of(consts.INSTRUCTOR)
def add_vitamin():
    Vitamin.add_vitamin(request.form.to_dict(), db)
    logger.info("Successfully added vitamin.")
    return jsonify(success=True), 200

@app.route('/delete_vitamin', methods=['GET', 'POST'])
@post_on_behalf_of(consts.INSTRUCTOR)
def delete_vitamin():
    Vitamin.delete_vitamin(request.form.to_dict(), db)
    logger.info("Successfully deleted vitamin.")
    return jsonify(success=True), 200

@app.route('/add_resource', methods=['GET', 'POST'])
@post_on_behalf_of(consts.INSTRUCTOR)
def add_resource():
    Resource.add_resource(request.form.to_dict(), db)
    logger.info("Successfully added resource.")
    return jsonify(success=True), 200

@app.route('/delete_resource', methods=['GET', 'POST'])
@post_on_behalf_of(consts.INSTRUCTOR)
def delete_resource():
    Resource.delete_resource(request.form.to_dict(), db)
    logger.info("Successfully deleted resource.")
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

@app.template_filter('clearance_for')
def has_clearance_for(user_role, clearance_role):
    return consts.OK_ROLES.index(user_role) >= consts.OK_ROLES.index(clearance_role)

@app.template_filter('external_link')
def create_link(link):
    return link if link.startswith('http') else 'http://{0}'.format(link)


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
		return jsonify(success=False), 404
	elif code == '403':
		return jsonify(success=False), 403
	elif code == '500':
		return jsonify(success=True), 500