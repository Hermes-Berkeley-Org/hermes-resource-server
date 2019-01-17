import sys
import os
import re
from datetime import datetime
from functools import wraps

from flask import Flask
from flask import request, session, jsonify
from flask_cors import CORS
from pymongo import MongoClient

from json import dumps as json_dump
from bson.json_util import dumps as bson_dump
from bson.objectid import ObjectId

from config import Config

import logging

import requests

from utils.db_utils import User, Course, Lecture, Vitamin, Resource, Video, Transcript
import utils.lecture_utils as LectureUtils
import utils.piazza_client as Piazza
from utils.errors import CreateLectureFormValidationError
from utils.es_client import ESClient

from pprint import pprint
import consts

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

# THIS creates the Elasticsearch client from utils, the link is a test instance
# i have running right now, we'll replace it with a hermes one and keep the link
# in our deploy folder
eslink = "https://search-hermestest-75oaeb7bmqusoddwau6ql2ev4q.us-east-2.es.amazonaws.com"
es_client = ESClient(eslink)


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
        return jsonify(success=False, message="OK validation failed"), 403
    return get_id

def get_user_data():
    """Queries OK to retrieve most up-to-date information on a user

    NOTE: OK IDs for courses are INTS here, but are converted to STRINGS in
    this application so they can be used as keys in MongoDB objects

    """
    r = requests.get('{0}/api/v3/user/?access_token={1}'.format(
            app.config['OK_SERVER'],
            get_oauth_token()
        )
    )
    if r.ok:
        user = r.json()
        if user and 'data' in user:
            return user['data']
    return False

def get_updated_user_courses():
    """Gets course info for a specific user
    """
    user = get_user_data()
    if user and 'participations' in user:
        return user['participations']
    return False

def get_ok_course(course_ok_id):
    user_courses = get_updated_user_courses()
    for user_course in user_courses:
        if str(user_course['course_id']) == course_ok_id:
            return user_course

@app.route('/user_data')
def user_data(ok_id=None):
    """Route for get_user_data()"""
    return json_dump(get_user_data())

@app.route('/hello')
@validate_and_pass_on_ok_id
def hello(ok_id=None):
    """Validates if ok_id exists"""
    return jsonify(success=True), 200

@app.route('/ok_code')
def ok_code():
    """Proxy for the front-end to authorize users: takes an OAuth code
    (generated on a login) and returns an OAuth token"""
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
    """Proxy for front-end to perform refreshes on OAuth tokens"""
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
    Route for homepage (with all the courses)
    @return all courses a user can access in a JSON object
    """
    ok_courses = get_updated_user_courses()
    courses = []
    for ok_course in ok_courses:
        db_course = db[Course.collection].find_one({'course_ok_id': str(ok_course['course_id'])})
        if ok_course['role'] == consts.INSTRUCTOR or db_course:
            if db_course:
                ok_course['course']['display_name']  = db_course['display_name']
            courses.append(ok_course)
    return json_dump(
        {
            "courses": courses
        }
    )

@app.route('/course/<course_ok_id>', methods=['GET'])
@validate_and_pass_on_ok_id
def course(course_ok_id, ok_id=None):
    """Gets all the lectures within a course
    """
    course = db[Course.collection].find_one(
        {'course_ok_id': course_ok_id},
        {"_id": 0, "display_name": 1}
    )
    if not course:
        return jsonify(
            success=False,
            message="Course with OK ID {0} does not exist".format(course_ok_id)
        ), 400
    return bson_dump({
        "info": course,
        "lectures": db[Lecture.collection].find(
            {'course_ok_id': course_ok_id},
            {
                "name": 1,
                "date": 1,
                "lecture_url_name": 1,
                "video_titles": 1,
                "_id": 0
            }
        ).sort([('lecture_index', 1)])
    })

@app.route('/course/<course_ok_id>/lecture/<lecture_url_name>/video/<int:video_index>', methods=["GET"])
@validate_and_pass_on_ok_id
def video(course_ok_id, lecture_url_name, video_index, ok_id=None):
    user_courses = get_updated_user_courses()
    int_course_ok_id = int(course_ok_id)
    for course in user_courses:
        if course['course_id'] == int_course_ok_id:
            video = db[Video.collection].find_one({
                'course_ok_id': course_ok_id,
                'lecture_url_name': lecture_url_name,
                'video_index': video_index
            })
            if video:
                return json_dump({
                    'title': video['title'],
                    'duration': video['duration'],
                    'youtube_id': video['youtube_id']
                })
            return jsonify(success=False, message="No video found"), 404
    return jsonify(success=False, message="Can only view a video on Hermes for an OK course you are a part of"), 403

@app.route('/course/<course_ok_id>/lecture/<lecture_url_name>/video/<int:video_index>/transcript')
@validate_and_pass_on_ok_id
def transcript(course_ok_id, lecture_url_name, video_index, ok_id=None):
    """Gets the transcript associated with a video in a lecture"""
    transcript = db[Transcript.collection].find_one({
        'course_ok_id': course_ok_id,
        'lecture_url_name': lecture_url_name,
        'video_index': video_index
    })
    if transcript:
        return json_dump({
            'transcript': transcript['transcript']
        })
    return jsonify(success=False, message="No transcript found"), 404

@app.route('/course/<course_ok_id>/lecture/<lecture_url_name>/video/<int:video_index>/edit_transcript', methods=['POST'])
@validate_and_pass_on_ok_id
def edit_transcript(course_ok_id, lecture_url_name, video_index, ok_id=None):
    transcript = db[Transcript.collection].find_one({
        'course_ok_id': course_ok_id,
        'lecture_url_name': lecture_url_name,
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
              'lecture_url_name': lecture_url_name,
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

@app.route('/course/<course_ok_id>/create_lecture', methods=["POST"])
@validate_and_pass_on_ok_id
def create_lecture(course_ok_id, ok_id=None):
    """Validates that the person creating the Lecture is an instructor of the
    course, and creates the course.
    """
    user_courses = get_updated_user_courses()
    int_course_ok_id = int(course_ok_id)
    for course in user_courses:
        if course['course_id'] == int_course_ok_id:
            if course['role'] != consts.INSTRUCTOR:
                return jsonify(success=False, message="Only instructors can post lectures"), 403
            try:
                create_lecture_response = LectureUtils.create_lecture(
                    course_ok_id,
                    db,
                    request.form['title'],
                    request.form['date'],
                    request.form['link'],
                    request.form['youtube_access_token'],
                    es_client
                )
                return jsonify(success=True, **create_lecture_response), 200
            except CreateLectureFormValidationError as e:
                return jsonify(success=False, message=str(e)), 400
            except ValueError as e:
                return jsonify(success=False, message=str(e)), 500
    return jsonify(success=False, message="Can only create a lecture on Hermes for an OK course you are a part of"), 403

@app.route('/course/<course_ok_id>/lecture/<lecture_url_name>', methods=["DELETE"])
@validate_and_pass_on_ok_id
def delete_lecture(course_ok_id, lecture_url_name, ok_id=None):
    """Deletes the associated Lecture, Video, and Transcript objects associated
    with a lecture_url_name in a course"""
    user_courses = get_updated_user_courses()
    int_course_ok_id = int(course_ok_id)
    for course in user_courses:
        if course['course_id'] == int_course_ok_id:
            if course['role'] != consts.INSTRUCTOR:
                return jsonify(success=False, message="Only instructors can delete lectures"), 403
            db[Lecture.collection].remove(
                {
                    'course_ok_id': course_ok_id,
                    'lecture_url_name': lecture_url_name
                }
            )
            db[Video.collection].remove(
                {
                    'course_ok_id': course_ok_id,
                    'lecture_url_name': lecture_url_name
                }
            )
            db[Transcript.collection].remove(
                {
                    'course_ok_id': course_ok_id,
                    'lecture_url_name': lecture_url_name
                }
            )
            return jsonify(success=True), 200
    return jsonify(success=False, message="Can only delete a lecture on Hermes for an OK course you are a part of"), 403

@app.route('/course/<course_ok_id>/reorder_lectures', methods=["POST"])
@validate_and_pass_on_ok_id
def reorder_lectures(course_ok_id, ok_id=None):
    """Changes all lecture_index fields in lectures in a course at once to match
    a professor's preferred order

    POST payload format:
    {
        "ordering": {
            <lecture_url_name>: index
            ...
        }
    }
    """
    user_courses = get_updated_user_courses()
    int_course_ok_id = int(course_ok_id)
    for course in user_courses:
        if course['course_id'] == int_course_ok_id:
            if course['role'] != consts.INSTRUCTOR:
                return jsonify(success=False, message="Only instructors can reorder lectures"), 403
            ordering = request.get_json().get('ordering')
            if ordering:
                lectures = db[Lecture.collection].find(
                    {
                        'course_ok_id': course_ok_id
                    }
                )
                lecture_url_names = set(lecture['lecture_url_name'] for lecture in lectures)
                if len(lecture_url_names.difference(set(ordering.keys()))) > 0:
                    return jsonify(
                        success=False,
                        message="Payload does not match lectures in the DB"
                    ), 400
                for lecture_url_name in lecture_url_names:
                    db[Lecture.collection].update_one(
                        {
                            'course_ok_id': course_ok_id,
                            'lecture_url_name': lecture_url_name
                        },
                        {
                            '$set': {
                                'lecture_index': ordering[lecture_url_name]
                            }
                        }
                    )
                return jsonify(success=True), 200
            return jsonify(success=False, message='No post payload'), 400
    return jsonify(success=False, message="Can only reorder lectures on Hermes for an OK course you are a part of"), 403

@app.route('/course/<course_ok_id>/lecture/<lecture_url_name>', methods=["GET"])
@validate_and_pass_on_ok_id
def lecture(course_ok_id, lecture_url_name, ok_id=None):
    """Retrieves the metadata on a lecture"""
    user_courses = get_updated_user_courses()
    for course in user_courses:
        # OK has course IDs as ints
        if course['course_id'] == int(course_ok_id):
            db_obj = db[Lecture.collection].find_one(
                {
                    'course_ok_id': course_ok_id,
                    'lecture_url_name': lecture_url_name
                }
            )
            return bson_dump(db_obj)
    return jsonify(success=False, message="Can only view a lecture on Hermes for an OK course you are a part of"), 403

@app.route('/course/<course_ok_id>/create_course', methods=["POST"])
@validate_and_pass_on_ok_id
def create_course(course_ok_id, ok_id=None):
    """Registers a Course in the DB
    """
    user_courses = get_updated_user_courses()
    int_course_ok_id = int(course_ok_id)
    for course in user_courses:
        if course['course_id'] == int_course_ok_id:
            if course['role'] == consts.INSTRUCTOR:
                if db['Courses'].find_one({'course_ok_id': course_ok_id}):
                    return jsonify(success=False, message="Course has already been created"), 403
                try:
                    form_data = request.form.to_dict()
                    Course.create_course(
                        offering= form_data["offering"],
                        course_ok_id= course_ok_id,
                        display_name= form_data["display_name"],
                        db=db
                    )
                    return jsonify(success=True), 200
                except ValueError as e:
                    return jsonify(success=False, message=str(e)), 500
            return jsonify(success=False, message="Only instructors can create courses"), 403
        pprint(course)
    return jsonify(success=False, message="Can only create a course on Hermes for an OK course you are a part of"), 403

@app.route('/course/<course_ok_id>/create_piazza_bot', methods=["POST"])
@validate_and_pass_on_ok_id
def create_piazza_bot(course_ok_id, ok_id=None):
    user_courses = get_updated_user_courses()
    int_course_ok_id = int(course_ok_id)
    seperate_folders = request.form["piazza_folders"].split(" ")
    for course in user_courses:
        if course['course_id'] == int_course_ok_id:
            print(int_course_ok_id)
            if course['role'] == consts.INSTRUCTOR or user_courses[course_ok_id_key] == consts.STAFF:
                if not request.form["piazza_course_id"].isalnum():
                    return jsonify(success=False, message="Please Enter a Valid Pizza API"), 403
                if not seperate_folders:
                    return jsonify(success=False, message="Must include at one least folder for posts to go in"), 403
                try:
                    Piazza.create_master_post(folders = seperate_folders, \
                    piazza_course_id  = request.form["piazza_course_id"], content = request.form["content"])
                    db['Courses'].update(
                        {'course_ok_id': course_ok_id},
                        {"$set" :
                            {"piazza_course_id" : request.form["piazza_course_id"],
                            "piazza_folders" : seperate_folders,
                            "piazza_active" : True}
                        }
                    )
                    return jsonify(success=True), 200
                except ValueError as e:
                    return jsonify(success=False, message= consts.PIAZZA_ERROR_MESSAGE), 403
            return jsonify(success=False, message="Only staff can create a Piazza Bot"), 403
    return jsonify(success=False, message="Can only create a PiazzaBot on behalf of Hermes for an OK course you are a part of"), 403

# this endpoint will return a search through all transcripts and return the timestamp/part of
# video that matches the search as best as possible
@app.route('/search', methods=["GET"])
#@validate_and_pass_on_ok_id
def search_transcripts(ok_id=None):
    params = {
    'query': {
            'match': {
                'text': request.form['text']
                #'cls': request.form['cls']
            }
        }
    }
    res = es_client.search_transcripts(params)
    return res
