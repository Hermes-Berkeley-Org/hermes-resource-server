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
from utils.db_utils import insert, User, Course, Lecture, Vitamin, Resource, Video, Transcript
from utils.textbook_utils import CLASSIFIERS

import utils.lecture_utils as LectureUtils

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
    """Retrieves OAuth token from the request header"""
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

@app.route('/hello')
@validate_and_pass_on_ok_id
def hello(ok_id=None):
    """Validates if ok_id exists"""
    return jsonify(success=True), 200

@app.route('/ok_code')
def ok_code():
    code = request.args.get('code')
    if not code:
        return jsonify(success=False), 400
    r = requests.post('https://okpy.org/oauth/token', data={
        'code': code,
        'client_secret': app.config['CLIENT_SECRET'],
        'client_id': app.config['CLIENT_ID'],
        'grant_type': 'authorization_code',
        'redirect_uri': 'http://localhost:3000/authorized'
    })
    if r.ok:
        return json_dump(r.json())
    return jsonify(success=False, message=r.text), r.status_code

@app.route('/ok_refresh')
def ok_refresh():
    refresh_token = request.args.get('refresh_token')
    if not refresh_token:
        return jsonify(success=False), 400
    r = requests.post('https://okpy.org/oauth/token', data={
        'refresh_token': refresh_token,
        'client_secret': app.config['CLIENT_SECRET'],
        'client_id': app.config['CLIENT_ID'],
        'grant_type': 'refresh_token',
        'redirect_uri': 'http://localhost:3000/authorized'
    })
    if r.ok:
        return json_dump(r.json())
    return jsonify(success=False, message=r.text), r.status_code

@app.route('/home/')
@validate_and_pass_on_ok_id
def home(ok_id=None):
    """
    Route for homepage (with all the classes)
    @return all courses a user can access in a JSON object
    """
    def include_course(course):
        return course['role'] == consts.INSTRUCTOR or \
            db[Course.collection].find({'ok_id': course['course_id']}).count() > 0

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

@app.route('/course/<int:course_ok_id>', methods=['GET'])
@validate_and_pass_on_ok_id
def course(course_ok_id, ok_id=None):
    """Gets all the lectures within a class
    """
    user = get_user_data(ok_id)
    course = db[Course.collection].find_one(
        {'ok_id': course_ok_id},
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

@app.route('/course/<int:course_ok_id>/lecture/<int:lecture_index>/video/<int:video_index>/video_info')
@validate_and_pass_on_ok_id
def video_info(course_ok_id, lecture_index, video_index, ok_id=None):
    video = db[Video.collection].find_one({
        'course_ok_id': course_ok_id,
        'lecture_index': lecture_index,
        'video_index': video_index
    })
    if video:
        return json_dump({
            'title': video['title'],
            'duration': video['duration'],
            'youtube_id': video['youtube_id']
        })
    return jsonify(success=False, message="No video found"), 404

@app.route('/course/<int:course_ok_id>/lecture/<int:lecture_index>/video/<int:video_index>/transcript')
@validate_and_pass_on_ok_id
def transcript(course_ok_id, lecture_index, video_index, ok_id=None):
    transcript = db[Transcript.collection].find_one({
        'course_ok_id': course_ok_id,
        'lecture_index': lecture_index,
        'video_index': video_index
    })
    if transcript:
        return json_dump({
            'transcript': transcript['transcript']
        })
    return jsonify(success=False, message="No transcript found"), 404

@app.route('/course/<int:course_ok_id>/lecture/<int:lecture_index>/video/<int:video_index>/edit_transcript', methods=['POST'])
@validate_and_pass_on_ok_id
def edit_transcript(course_ok_id, lecture_index, video_index, ok_id=None):
    transcript = db[Transcript.collection].find_one({
        'course_ok_id': course_ok_id,
        'lecture_index': lecture_index,
        'video_index': video_index
    })
    if transcript:
        new_transcript_obj = Transcript.suggest_transcript(
            transcript['transcript'],
            int(request.form['index']),
            request.form['suggestion'],
            request.form['user_id']
        )
        db[Transcript.collection].update_one(
            {
              'course_ok_id': course_ok_id,
              'lecture_index': lecture_index,
              'video_index': video_index
            },
            {
              '$set': {
                'transcript': new_transcript_obj,
              }
            },
            upsert=False
        )
        return jsonify(success=True), 200
    return jsonify(success=False, message="No transcript found"), 404

@app.route('/course/<int:course_ok_id>/create_lecture', methods=["POST"])
@validate_and_pass_on_ok_id
def create_lecture(course_ok_id, ok_id=None):
    """
    Validates that the person creating the Lecture is an instructor of the
    course, and creates the course.
    """
    user = get_user_data(ok_id)
    for course in user['classes']:
        if course['ok_id'] == course_ok_id:
            if course['role'] != consts.INSTRUCTOR:
                return jsonify(success=False, message="Only instructors can post videos"), 403
            break
    try:
        LectureUtils.create_lecture(
            course_ok_id,
            db,
            request.form['title'],
            request.form['date'],
            request.form['link'],
            request.form['youtube_access_token']
        )
        return jsonify(success=True), 200
    except ValueError as e:
        return jsonify(success=False, message=str(e)), 500

@app.route('/course/<int:course_ok_id>/lecture/<int:lecture_index>/video/<int:video_index>/create_vitamin', 
    methods=["POST"])
@validate_and_pass_on_ok_id
def create_vitamin(course_ok_id, lecture_index, video_index, ok_id=None):
    """
    Creates a vitamin for a specified video in a lecture.
    """
    user = get_user_data(ok_id)
    for course in user['classes']:
        if course['ok_id'] == course_ok_id:
            if course['role'] != consts.INSTRUCTOR:
                return jsonify(success=False, message="Only instructors can add vitamins"), 403
            break
    try:
        vitamin = Vitamin.add_vitamin(
            course_ok_id,
            lecture_index,
            video_index,
            db,
            request.form['question'],
            request.form['answer'],
            request.form['choices'],
            request.form['timestamp']
        )
        insert(vitamin, db)
        return jsonify(success=True), 200
    except ValueError as e:
        return jsonify(success=False, message=str(e)), 500

@app.route('/course/<int:course_ok_id>/lecture/<int:lecture_index>/video/<int:video_index>/create_resource', 
    methods=["POST"])
@validate_and_pass_on_ok_id
def create_resource(course_ok_id, lecture_index, video_index, ok_id=None):
    """
    Creates a vitamin for a specified video in a lecture.
    """
    user = get_user_data(ok_id)
    for course in user['classes']:
        if course['ok_id'] == course_ok_id:
            if course['role'] != consts.INSTRUCTOR:
                return jsonify(success=False, message="Only instructors can add resources"), 403
            break
    try:
        resource = Resource.add_resource(
            course_ok_id,
            lecture_index,
            video_index,
            db,
            request.form['link']
        )
        insert(resource, db)
        return jsonify(success=True), 200
    except ValueError as e:
        return jsonify(success=False, message=str(e)), 500

