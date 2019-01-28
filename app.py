import sys
import os
import re
from datetime import datetime
from functools import wraps

from flask import Flask
from flask import request, session, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import psycopg2

import json
from bson.json_util import dumps as bson_dump
from bson.objectid import ObjectId

from config import Config

import logging

import requests

from utils.db_utils import User, Course, Lecture, Vitamin, Resource, Video, \
    Transcript, convert_seconds_to_timestamp
import utils.lecture_utils as LectureUtils
import utils.piazza_client as Piazza
from utils.errors import CreateLectureFormValidationError
from utils.sql_client import SQLClient

import consts

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": os.environ.get('HERMES_UI_URL')}})
app.config.from_object(Config)

client = MongoClient(os.environ.get('MONGODB_URI'))
db = client[os.environ.get('DATABASE_NAME')]

conn = psycopg2.connect(os.environ.get('SQL_DATABASE_URL'))
sql_client = SQLClient(conn)

logger = logging.getLogger('app_logger')
sh = logging.StreamHandler(stream=sys.stdout)
sh.setFormatter(
    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)
logger.addHandler(sh)
logger.setLevel(logging.INFO)
logger.info('Backend READY')

ok_server = app.config['OK_SERVER']

json_dump = lambda j: json.dumps(j, indent=4)


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
                    return func(ok_id=ok_data['id'], *args, **kwargs)
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
        db_course = db[Course.collection].find_one(
            {'course_ok_id': str(ok_course['course_id'])})
        if ok_course['role'] == consts.INSTRUCTOR or db_course:
            if db_course:
                ok_course['course']['display_name'] = db_course['display_name']
            ok_course['hermes_active'] = bool(db_course)
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
        {"_id": 0}
    )
    if not course:
        return jsonify(
            success=False,
            message="Course with OK ID {0} does not exist".format(course_ok_id)
        ), 404
    return bson_dump({
        "info": course,
        "lectures": db[Lecture.collection].find(
            {'course_ok_id': course_ok_id},
            {
                "name": 1,
                "date": 1,
                "lecture_url_name": 1,
                "video_titles": 1,
                "lecture_piazza_id": 1,
                "_id": 0
            }
        ).sort([('lecture_index', 1)])
    }, indent=4)


@app.route(
    '/course/<course_ok_id>/lecture/<lecture_url_name>/video/<int:video_index>',
    methods=["GET"])
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
    return jsonify(success=False,
                   message="Can only view a video on Hermes for an OK course you are a part of"), 403


@app.route(
    '/course/<course_ok_id>/lecture/<lecture_url_name>/video/<int:video_index>/transcript')
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


@app.route(
    '/course/<course_ok_id>/lecture/<lecture_url_name>/video/<int:video_index>/edit_transcript',
    methods=['POST'])
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
    course, and creates the Lecture.
    """
    user_courses = get_updated_user_courses()
    int_course_ok_id = int(course_ok_id)
    for course in user_courses:
        if course['course_id'] == int_course_ok_id:
            if course['role'] != consts.INSTRUCTOR:
                return jsonify(success=False,
                               message="Only instructors can post lectures"), 403
            try:
                course_obj = db[Course.collection].find_one({
                    "course_ok_id": course_ok_id
                })
                create_lecture_response, lecture_url_name = LectureUtils.create_lecture(
                    course_ok_id,
                    db,
                    request.form['title'],
                    request.form['date'],
                    request.form['link'],
                    request.form['youtube_access_token']
                )
                # create the lecture first, then create the Piazza post in case of error
                if request.form["piazza_active"] == "active":
                    lecture_post = Piazza.create_lecture_post(
                        lecture_title=request.form['title'],
                        date=request.form["date"],
                        db=db, course_ok_id=course_ok_id,
                        lecture_url_name=lecture_url_name,
                        piazza_course_id=course_obj["piazza_course_id"],
                        master_id=course_obj["piazza_master_post_id"]
                    )
                    Piazza.recreate_master_post(
                        request.form["piazza_master_post_id"],
                        course_ok_id=course_ok_id,
                        piazza_course_id=request.form[
                            "piazza_course_id"], db=db)
                return jsonify(success=True, **create_lecture_response), 200
            except CreateLectureFormValidationError as e:
                return jsonify(success=False, message=str(e)), 400
            except ValueError as e:
                return jsonify(success=False, message=str(e)), 500
    return jsonify(success=False,
                   message="Can only create a lecture on Hermes for an OK course you are a part of"), 403


@app.route('/course/<course_ok_id>/lecture/<lecture_url_name>',
           methods=["DELETE"])
@validate_and_pass_on_ok_id
def delete_lecture(course_ok_id, lecture_url_name, ok_id=None):
    """Deletes the associated Lecture, Video, Transcript, and Vitamin objects associated
    with a lecture_url_name in a course"""
    user_courses = get_updated_user_courses()
    int_course_ok_id = int(course_ok_id)
    for course in user_courses:
        if course['course_id'] == int_course_ok_id:
            if course['role'] != consts.INSTRUCTOR:
                return jsonify(success=False,
                               message="Only instructors can delete lectures"), 403
            lecture = db[Lecture.collection].find_one_and_delete(
                {
                    'course_ok_id': course_ok_id,
                    'lecture_url_name': lecture_url_name
                }
            )
            if not lecture:
                return jsonify(success=False,
                               message="Lecture does not exist"), 404
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
            db[Vitamin.collection].remove(
                {
                    'course_ok_id': course_ok_id,
                    'lecture_url_name': lecture_url_name
                }
            )
            db[Resource.collection].remove(
                {
                    'course_ok_id': course_ok_id,
                    'lecture_url_name': lecture_url_name
                }
            )
            db_obj = db[Lecture.collection].find(
                {
                    "course_ok_id": course_ok_id
                }
            ).sort("date", 1)
            if request.args["piazza_active"] == "active":
                Piazza.delete_post(
                    piazza_course_id=request.args["piazza_course_id"],
                    cid=request.args["lecture_piazza_id"])
                Piazza.recreate_master_post(
                    request.args["piazza_master_post_id"],
                    piazza_course_id=request.args["piazza_course_id"],
                    db=db)
            return jsonify(success=True), 200
    return jsonify(success=False,
                   message="Can only delete a lecture on Hermes for an OK course you are a part of"), 403


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
                return jsonify(success=False,
                               message="Only instructors can reorder lectures"), 403
            ordering = request.get_json().get('ordering')
            if ordering:
                lectures = db[Lecture.collection].find(
                    {
                        'course_ok_id': course_ok_id
                    }
                )
                lecture_url_names = set(
                    lecture['lecture_url_name'] for lecture in lectures)
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
    return jsonify(success=False,
                   message="Can only reorder lectures on Hermes for an OK course you are a part of"), 403


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
            return bson_dump(db_obj, indent=4)
    return jsonify(success=False,
                   message="Can only view a lecture on Hermes for an OK course you are a part of"), 403


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
                    return jsonify(success=False,
                                   message="Course has already been created"), 400
                try:
                    form_data = request.form.to_dict()
                    Course.create_course(
                        offering=form_data["offering"],
                        course_ok_id=course_ok_id,
                        display_name=form_data["display_name"],
                        db=db
                    )
                    return jsonify(success=True), 200
                except ValueError as e:
                    return jsonify(success=False, message=str(e)), 500
            return jsonify(success=False,
                           message="Only instructors can create courses"), 403
    return jsonify(success=False,
                   message="Can only create a course on Hermes for an OK course you are a part of"), 403


@app.route('/course/<course_ok_id>/create_piazza_bot', methods=['POST'])
@validate_and_pass_on_ok_id
def create_piazza_bot(course_ok_id, ok_id=None):
    """
    Creates a piazza bot. Extra steps needed to make a piazza bot work on Piazza:
    1. Register the Hermes email as an instructor on course Piazza
    2. Create a folder called "hermes"

    POST payload format:

    {
        "piazza_course_id": the Piazza course id (the id in the url) piazza.com/<piazza_course_id>
        "piazza_master_id": the ID of the master post on the current course Piazza (blank if does not exist yet)
        "content": the body of the "Lecture Master Post": if not specified, will default to:

            "All lectures with their dates, names, and threads will be posted here. \n \n #pin"
    }
    """
    user_courses = get_updated_user_courses()
    int_course_ok_id = int(course_ok_id)
    for course in user_courses:
        if course['course_id'] == int_course_ok_id:
            if course['role'] in [consts.STAFF, consts.INSTRUCTOR]:
                if not request.form["piazza_course_id"].isalnum():
                    return jsonify(
                        success=False,
                        message="Please Enter a valid Piazza Course ID"
                    ), 400

                piazza_course_id = request.form["piazza_course_id"]
                piazza_master_post_id = request.form['piazza_master_post_id']

                if piazza_master_post_id:  # A Master post has already been created
                    Course.update_course(course_ok_id, db,
                                         piazza_active="active")
                    if Piazza.post_exists(post_id=piazza_master_post_id,
                                          piazza_course_id=piazza_course_id):
                        Piazza.pin_post(post_id=piazza_master_post_id,
                                        piazza_course_id=piazza_course_id)
                        Piazza.add_unadded_lectures(piazza_course_id,
                                                    piazza_master_post_id, db,
                                                    course_ok_id)
                        Piazza.recreate_master_post(
                            master_id=piazza_master_post_id,
                            course_ok_id=course_ok_id,
                            piazza_course_id=piazza_course_id,
                            db=db
                        )
                        return jsonify(success=True), 200
                try:
                    master_post = Piazza.create_master_post(
                        piazza_course_id=piazza_course_id,
                        content=request.form.get("content") or ""
                    )
                    master_id = master_post["nr"]

                    Piazza.add_unadded_lectures(piazza_course_id,
                                                piazza_master_post_id, db,
                                                course_ok_id)
                    Piazza.recreate_master_post(master_id=master_id,
                                                course_ok_id=course_ok_id,
                                                piazza_course_id=piazza_course_id,
                                                db=db)

                    Course.update_course(course_ok_id, db,
                                         piazza_course_id=piazza_course_id,
                                         piazza_active="active"
                                         , piazza_master_post_id=master_id)
                    return jsonify(success=True), 200
                except ValueError as e:
                    return jsonify(success=False,
                                   message=consts.PIAZZA_ERROR_MESSAGE), 400
            return jsonify(success=False,
                           message="Only staff can create a Piazza Bot"), 403
    return jsonify(success=False,
                   message="Can only create a PiazzaBot on behalf of Hermes for an OK course you are a part of"), 403


@app.route(
    '/course/<course_ok_id>/lecture/<lecture_url_name>/video/<int:video_index>/question',
    methods=["POST"])
@validate_and_pass_on_ok_id
def ask_piazza_question(course_ok_id, lecture_url_name, video_index,
                        ok_id=None):
    """
    For a question need the following items in a form:
    question, video title, timestamp, piazza_lecture_post_id (the id on Piazza
    for a lecture thread), and a piazza_course_id (the ID in the URL)
    """
    user_courses = get_updated_user_courses()
    int_course_ok_id = int(course_ok_id)
    for course in user_courses:
        if course['course_id'] == int_course_ok_id:
            name = "anonymously"
            if request.form["question"]:
                timestamp = convert_seconds_to_timestamp(
                    int(request.form["seconds"]))
                tag = "{0} {1}:".format(
                    request.form["video_title"], timestamp)
                piazza_lecture_post_id = request.form["piazza_lecture_post_id"]
                identity_msg = "posted Anonymously"
                if request.form["anonymous"] == "nonanon":
                    data = get_user_data()
                    name = data["name"]
                    email = data["email"]
                if Piazza.post_exists(
                        post_id=request.form["piazza_lecture_post_id"],
                        piazza_course_id=request.form["piazza_course_id"]):
                    identity_msg = "posted on behalf of " + name
                    post_id = Piazza.create_followup_question(
                        piazza_lecture_post_id, request.form["video_url"], tag,
                        request.form["question"],
                        piazza_course_id=request.form["piazza_course_id"],
                        identity_msg=identity_msg
                    )["id"]
                    try:
                        sql_client.post_question(
                            user_email=email,
                            course_ok_id=course_ok_id,
                            lecture_url_name=lecture_url_name,
                            video_index=video_index,
                            piazza_question_id=post_id,
                            seconds=request.form["seconds"],
                            identity=name)
                    except Exception as e:
                        pass
                    return jsonify(success=True), 200
                return jsonify(success=False,
                               message="Piazza Post is not active, please tell an instructor to a. recreate the post on Hermes or b. Delete this lecture"), 403
            return jsonify(success=False,
                           message="Please enter a question"), 400
    return jsonify(success=False,
                   message="Can only create ask a question for an OK course you are a part of"), 403


@app.route('/course/<course_ok_id>/disable_piazza', methods=["POST"])
@validate_and_pass_on_ok_id
def disable_piazza(course_ok_id, ok_id=None):
    user_courses = get_updated_user_courses()
    int_course_ok_id = int(course_ok_id)

    for course in user_courses:
        if course['course_id'] == int_course_ok_id:
            db[Course.collection].update_one({
                "course_ok_id": course_ok_id},
                {
                    "$set": {
                        "piazza_active": "inactive"
                    }
                }
            )
            if Piazza.post_exists(post_id=request.form["piazza_master_post_id"],
                                  piazza_course_id=request.form[
                                      "piazza_course_id"]):
                Piazza.unpin_post(post_id=request.form["piazza_master_post_id"],
                                  piazza_course_id=request.form[
                                      "piazza_course_id"])
            else:
                db[Course.collection].update_one({
                    "course_ok_id": course_ok_id},
                    {
                        "$set": {
                            "piazza_master_post_id": ""
                        }
                    }
                )
            return jsonify(success=True), 200
    return jsonify(success=False,
                   message="Can only disable piazza for an OK course you are a part of"), 403


@app.route(
    '/course/<course_ok_id>/lecture/<lecture_url_name>/video/<int:video_index>/questions',
    methods=["GET"])
@validate_and_pass_on_ok_id
def get_questions_in_range(course_ok_id, lecture_url_name, video_index,
                           ok_id=None):
    user_courses = get_updated_user_courses()
    int_course_ok_id = int(course_ok_id)
    for course in user_courses:
        if course['course_id'] == int_course_ok_id:
            sql_returned = sql_client.retrieve_questions_for_timestamp(
                request.form["start_second"], request.form["end_second"],
                course_ok_id, lecture_url_name, video_index)
            questions = []
            for question in sql_returned:
                followup = Piazza.get_followup(request.form["lecture_post_id"],
                                               question["piazza_question_id"],
                                               piazza_course_id=request.form[
                                                   "piazza_course_id"])
                content = followup["subject"].split("</b>")[1]
                questions.append(
                    [content, question["seconds"], question["identity"]])
            return json_dump({
                'questions': questions
            })
            return jsonify(success=True), 200
    return jsonify(success=False,
                   message="Can only get questions for an OK course you are a part of"), 403


@app.route(
    '/course/<course_ok_id>/lecture/<lecture_url_name>/video/<int:video_index>/create_vitamin',
    methods=["POST"])
@validate_and_pass_on_ok_id
def create_vitamin(course_ok_id, lecture_url_name, video_index, ok_id=None):
    """Creates a vitamin in the specified video within a lecture of a course."""
    user_courses = get_updated_user_courses()
    int_course_ok_id = int(course_ok_id)
    for course in user_courses:
        if course['course_id'] == int_course_ok_id:
            if course['role'] == consts.INSTRUCTOR:
                if db[Video.collection].find_one({
                    'course_ok_id': course_ok_id,
                    'lecture_url_name': lecture_url_name,
                    'video_index': video_index
                }):
                    try:
                        vitamin = request.get_json().get('vitamin')
                        Vitamin.add_vitamin(
                            course_ok_id=course_ok_id,
                            lecture_url_name=lecture_url_name,
                            video_index=video_index,
                            data=vitamin,
                            db=db
                        )
                        return jsonify(success=True), 200
                    except ValueError as e:
                        return jsonify(success=False, message=str(e)), 500
            return jsonify(success=False,
                           message="Only instructors can create vitamins"), 403
    return jsonify(success=False,
                   message="Can only create a vitamin on Hermes for an OK course you are a part of"), 403


@app.route('/course/<course_ok_id>/lecture/<lecture_url_name>/video/<int:video_index>/edit_vitamin/<int:vitamin_index>', methods=["POST"])
@validate_and_pass_on_ok_id
def edit_vitamin(course_ok_id, lecture_url_name, video_index, vitamin_index, ok_id=None):
    """Creates a vitamin in the specified video within a lecture of a course."""
    user_courses = get_updated_user_courses()
    int_course_ok_id = int(course_ok_id)
    for course in user_courses:
        if course['course_id'] == int_course_ok_id:
            if course['role'] == consts.INSTRUCTOR:
                try:
                    vitamin = request.get_json().get('vitamin')
                    # new_vitamin is a DB/BSON object
                    vitamin.pop('_id')
                    db[Vitamin.collection].update_one(
                        {
                            'course_ok_id': course_ok_id,
                            'lecture_url_name': lecture_url_name,
                            'video_index': video_index,
                            'vitamin_index': vitamin_index
                        },
                        {
                            '$set': vitamin
                        },
                        upsert=False
                    )
                    return jsonify(success=True), 200
                except ValueError as e:
                    return jsonify(success=False, message=str(e)), 500
            return jsonify(success=False, message="Only instructors can create vitamins"), 403
    return jsonify(success=False, message="Can only create a vitamin on Hermes for an OK course you are a part of"), 403

@app.route('/course/<course_ok_id>/lecture/<lecture_url_name>/video/<int:video_index>/edit_resource/<int:resource_index>', methods=["POST"])
@validate_and_pass_on_ok_id
def edit_resource(course_ok_id, lecture_url_name, video_index, resource_index, ok_id=None):
    """Creates a vitamin in the specified video within a lecture of a course."""
    user_courses = get_updated_user_courses()
    int_course_ok_id = int(course_ok_id)
    for course in user_courses:
        if course['course_id'] == int_course_ok_id:
            if course['role'] == consts.INSTRUCTOR:
                try:
                    db[Resource.collection].update_one(
                        {
                            'course_ok_id': course_ok_id,
                            'lecture_url_name': lecture_url_name,
                            'video_index': video_index,
                            'resource_index': resource_index
                        },
                        {
                            '$set': request.form.to_dict()
                        },
                        upsert=False
                    )
                    return jsonify(success=True), 200
                except ValueError as e:
                    return jsonify(success=False, message=str(e)), 500
            return jsonify(success=False, message="Only instructors can create vitamins"), 403
    return jsonify(success=False, message="Can only create a vitamin on Hermes for an OK course you are a part of"), 403

@app.route('/course/<course_ok_id>/lecture/<lecture_url_name>/video/<int:video_index>/edit')
@validate_and_pass_on_ok_id
def edit_video(course_ok_id, lecture_url_name, video_index, ok_id=None):
    """Gets all vitamins on a video"""
    user_courses = get_updated_user_courses()
    int_course_ok_id = int(course_ok_id)
    for course in user_courses:
        if course['course_id'] == int_course_ok_id:
            return bson_dump({
                "vitamins": db[Vitamin.collection].find({
                    'course_ok_id': course_ok_id,
                    'lecture_url_name': lecture_url_name,
                    'video_index': video_index
                }).sort("seconds", 1),
                "resources": db[Resource.collection].find({
                    'course_ok_id': course_ok_id,
                    'lecture_url_name': lecture_url_name,
                    'video_index': video_index
                })
            })
    return jsonify(success=False, message="Can only get vitamins on Hermes for an OK course you are a part of"), 403

@app.route('/course/<course_ok_id>/lecture/<lecture_url_name>/video/<int:video_index>/create_resource', methods=["POST"])
@validate_and_pass_on_ok_id
def create_resource(course_ok_id, lecture_url_name, video_index, ok_id=None):
    """Creates a resource in the specified video within a lecture of a course."""

    user_courses = get_updated_user_courses()
    int_course_ok_id = int(course_ok_id)
    for course in user_courses:
        if course['course_id'] == int_course_ok_id:
            if course['role'] == consts.INSTRUCTOR:
                if db[Video.collection].find_one({
                    'course_ok_id': course_ok_id,
                    'lecture_url_name': lecture_url_name,
                    'video_index': video_index
                }):
                    try:
                        Resource.add_resource(
                            course_ok_id = course_ok_id,
                            lecture_url_name = lecture_url_name,
                            video_index = video_index,
                            db = db,
                            resource_data = request.form.to_dict()

                        )
                        return jsonify(success=True), 200
                    except ValueError as e:
                        return jsonify(success=False, message=str(e)), 500
            return jsonify(success=False,
                           message="Only instructors can create resources"), 403
    return jsonify(success=False,
                   message="Can only create a resource on Hermes for an OK course you are a part of"), 403


@app.route(
    '/course/<course_ok_id>/lecture/<lecture_url_name>/video/<int:video_index>/delete_vitamin/<int:vitamin_index>',
    methods=["DELETE"])
@validate_and_pass_on_ok_id
def delete_vitamin(course_ok_id, lecture_url_name, video_index, vitamin_index,
                   ok_id=None):
    """Deletes a specified vitamin within a specific video of a lecture in a given course."""
    user_courses = get_updated_user_courses()
    int_course_ok_id = int(course_ok_id)
    for course in user_courses:
        if course['course_id'] == int_course_ok_id:
            if course['role'] != consts.INSTRUCTOR:
                return jsonify(success=False,
                               message="Only instructors can delete vitamins"), 403
            db[Vitamin.collection].delete_one(
                {
                    'course_ok_id': course_ok_id,
                    'lecture_url_name': lecture_url_name,
                    'video_index': video_index,
                    'vitamin_index': vitamin_index
                }
            )
            return jsonify(success=True), 200
    return jsonify(success=False,
                   message="Can only delete a vitamin on Hermes for an OK course you are a part of"), 403


@app.route(
    '/course/<course_ok_id>/lecture/<lecture_url_name>/video/<int:video_index>/delete_resource/<int:resource_index>',
    methods=["DELETE"])
@validate_and_pass_on_ok_id
def delete_resource(course_ok_id, lecture_url_name, video_index, resource_index,
                    ok_id=None):
    """Deletes a specified resource within a specific video of a lecture in a given course."""
    user_courses = get_updated_user_courses()
    int_course_ok_id = int(course_ok_id)
    for course in user_courses:
        if course['course_id'] == int_course_ok_id:
            if course['role'] != consts.INSTRUCTOR:
                return jsonify(success=False,
                               message="Only instructors can delete resources"), 403
            db[Resource.collection].delete_one(
                {
                    'course_ok_id': course_ok_id,
                    'lecture_url_name': lecture_url_name,
                    'video_index': video_index,
                    'resource_index': resource_index
                }
            )
            return jsonify(success=True), 200
    return jsonify(success=False,
                   message="Can only delete a resource on Hermes for an OK course you are a part of"), 403


@app.route(
    '/course/<course_ok_id>/lecture/<lecture_url_name>/video/<int:video_index>/answer_vitamin/<int:vitamin_index>',
    methods=["POST"])
@validate_and_pass_on_ok_id
def answer_vitamin(course_ok_id, lecture_url_name, video_index, vitamin_index,
                   ok_id=None):
    """Submits the user's answer to a given vitamin and returns if the user got it correct or not."""
    user_courses = get_updated_user_courses()
    int_course_ok_id = int(course_ok_id)
    user_ok_id = get_user_data()["id"]
    for course in user_courses:
        if course['course_id'] == int_course_ok_id:
            vitamin = db[Vitamin.collection].find_one({
                'course_ok_id': course_ok_id,
                'lecture_url_name': lecture_url_name,
                'video_index': video_index,
                'vitamin_index': vitamin_index
            })
            if vitamin:
                time = datetime.now()

                sql_client.answer_vitamin(user_ok_id, course_ok_id,
                                          vitamin['answer'], video_index,
                                          vitamin_index, lecture_url_name)
                submission = request.get_json().get('answer')
                if submission == vitamin['answer']:
                    return jsonify(success=True, message="Correct!"), 200
                else:
                    return jsonify(success=True,
                                   message="Incorrect, please try again."), 200
            else:
                return jsonify(success=False, message="Invalid vitamin"), 404
    return jsonify(success=False,
                   message="Can only answer a vitamin on Hermes for an OK course you are a part of"), 403
