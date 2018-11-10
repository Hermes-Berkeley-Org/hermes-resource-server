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
CORS(app, resources={r"/*": {"origins": os.environ.get('HERMES_UI_URL')}})
app.config.from_object(Config)

client = MongoClient(os.environ.get('MONGODB_URI'))
db = client[os.environ.get('DATABASE_NAME')]

logger = logging.getLogger('app_logger')
sh = logging.StreamHandler(stream=sys.stdout)
sh.setFormatter(
    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)
logger.addHandler(sh)
logger.setLevel(logging.INFO)

ok_server = app.config['OK_SERVER']

def get_oauth_token():
    """Retrieves OAuth token from the request header
    """
    authorization = request.headers.get("Authorization")
    if authorization:
        return authorization.replace('Bearer ', '')

def validate_and_pass_on_ok_id(func):
    """
    Decorator that takes in a function and confirms the user's ok_id is valid
    and passes on the ok_id into the function as an argument leaving all other
    arguments unchanged.
    """
    @wraps(func)
    def get_id(*args, **kwargs):
        r = requests.get('{0}/api/v3/user/?access_token={1}'.format(
                app.config['OK_SERVER'],
                get_oauth_token()
            )
        )
        if r.ok:
            ok_resp = r.json()
            if ok_resp and 'data' in ok_resp:
                ok_data = ok_resp['data']
                if 'id' in ok_data:
                    return func(ok_id=ok_data['id'], *args,**kwargs)
        logger.info("OK validation failed")
        return jsonify(success=False), 403
    return get_id

def get_updated_user_courses():
    """Gets course info for a specific user
    """
    r = requests.get('{0}/api/v3/user/?access_token={1}'.format(
            app.config['OK_SERVER'],
            get_oauth_token()
        )
    )
    if r.ok:
        ok_resp = r.json()
        if 'data' in ok_resp and 'participations' in ok_resp['data']:
            return ok_resp['data']['participations']

@app.route('/home/')
@validate_and_pass_on_ok_id
def home(ok_id=None):
    """
    Route for homepage (with all the classes)
    @return all courses a user can access in a JSON object
    """
    def include_course(course):
        return course['role'] == consts.INSTRUCTOR or \
            db[Class.collection].find({'ok_id': course['course_id']}).count() > 0

    courses = get_updated_user_courses()
    return json_dump(
        {
            "courses":list(filter(include_course, courses))
        }
    )

def get_user_data(ok_id):
    if ok_id:
        db_result = db[User.collection].find_one({'ok_id': ok_id}) or {}
        return db_result

@app.route('/course/<course_ok_id>', methods=['GET'])
@validate_and_pass_on_ok_id
def course(course_ok_id, ok_id=None):
    """Gets all the lectures within a class
    """
    user = get_user_data(ok_id)
    #TODO: Change to Courses
    course = db['Classes'].find_one(
        {'ok_id': int(course_ok_id)},
        {"_id": 0, "display_name": 1}
    )
    if not course:
        return jsonify(success=False), 403
    return bson_dump({
        "info": course,
        "lectures": db['Lectures'].find(
            {'cls': course_ok_id},
            {
                "name": 1,
                "date": 1,

                "lecture_number": 1,
                "_id": 0
            }
        ).sort([('date', 1)])
    })

@app.route('/course/<course_ok_id>/<lecture_number>/<video_number>', methods=["GET, POST"])
@validate_and_pass_on_ok_id
def lecture(course_ok_id, lecture_number, video_index, ok_id=None):
    #TODO: Change to Courses
    course_obj = db['Classes'].find_one({
        'ok_id':int(course_ok_id)
    })
    lecture_obj = db['Lectures'].find_one({
        'course':course_ok_id,
        'lecture_number':int(lecture_number)
    })
    user = get_user_data(ok_id)
    user['role'], data = get_role
    questions_interval= 30
    video_info={}
    video_index = int(video_index)
    video_obj= lecture_obj['video_lst'][video_index] #returns a video
    preds = lecture_obj.get('preds')
    transcript = lecture_obj.get('transcript')
    if not preds:
        preds= [(None, [0, len(transcript)//2 + 1])]
    link = "https://www.youtube.com/watch?v={0}".format(
            video_obj['youtube_video_id']
        )
    video_info['video_id'] = transcribe_utils.get_youtube_id(link)
    video_info['partition_titles'] = list(
            app_utils.generate_partition_titles(
                lecture_obj['durations'][play_num],
                questions_interval
            )
        )
    video_info['duration'] = video_obj.get('durations')
    video_info['num_videos'] = len(lecture_obj['video_lst'])
    vitamins = db['Vitamins'].find({'$and':[{'lecture_id': str(lecture_obj["_id"])}, {'video_index': str(video_index)}]})
    resources = db['Resources'].find({'$and':[{'lecture_id': str(lecture_obj["_id"])}, {'video_index': str(video_index)}]})

@app.route('/course/<course_ok_id>/create_lecture', methods=["POST"])
@validate_and_pass_on_ok_id
def create_lecture(course_ok_id, ok_id=None):
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
        return jsonify(success=False), 403
    lecture = Lecture(
            name=request.form['title'],
            lecture_url=db_utils.encode_url(request.form['title']),
            date=request.form['date'],
            link=url,
            lecture_number=len(course['lectures']),
            course=course_ok_id,
            video_lst=[]
        )
    lecture.add_videos(course_ok_id = course_ok_id, params = params, url = url, youtube = youtube)
