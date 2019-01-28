import os
import piazza_api as p
from pprint import pprint
from .db_utils import User, Course, Lecture, Vitamin, Resource, Video, \
    Transcript

piazza = p.Piazza()
piazza.user_login(
    email=os.environ.get("PIAZZA_EMAIL"),
    password=os.environ.get("PIAZZA_PASSWORD")
)


def create_master_post(content="", network=None, piazza_course_id=None):
    """
    Takes in:
    folders: array of which folders hermes posts should be in),
    content: the content of the post,
    piazza_course_id: the Piazza course id (the id in the url) piazza.com/<piazza_course_id>

    Creates a master post that links to all Hermes lecture posts

    Returns: the created master post dictionary

    Note: There cannot be duplicate titles in Piazza
    """
    if not network:
        network = piazza.network(piazza_course_id)
    if not content:
        content = "All lectures with their dates, names, and threads will be posted here. \n \n #pin"
    else:
        content = content + "\n \n #pin"
    rpc = network._rpc
    master_post = rpc.content_create({
        "type": "note",
        "title": "Hermes Master Thread",
        "subject": "Hermes Master Thread",
        "content": content,
        "folders": ["hermes"]
    })
    return master_post


def create_lecture_post(lecture_title, date,db,master_id,course_ok_id, lecture_url_name,
                        network=None, piazza_course_id=None, content=None):
    """
    Creates a lecture post on piazza for a given lecture number. Takes in
    an array of folders that it will put the course in as well as the piazza_course_id
    (the id in the url)- piazza.com/<piazza_course_id>
    for a course on piazza.
    master_id is the id of the master thread on piazza.
    content is just the question

    Returns the lecture dictionary with the following contents:
        nr: The id of the lecture post
        created: time created
        children: Followup questions
    """
    if not network:
        network = piazza.network(piazza_course_id)
    if not content:
        content = "Lecture thread for {0}. Ask questions regarding \
this lecture below and fellow students/staff \
will (hopefully) respond.".format(lecture_title)
    rpc = network._rpc
    post = rpc.content_create({
        "type": "note",
        "title": "Lecture Thread for {0} ({1})".format(lecture_title, date),
        "subject": "Lecture Thread for {0} ({1})".format(lecture_title, date),
        "content": content,
        "folders": ["hermes"]
    })
    lecture_piazza_id = post["nr"]
    db[Lecture.collection].update_one(
        {
            'course_ok_id': course_ok_id,
            'lecture_url_name': lecture_url_name
        },
        {
            '$set': {
                'lecture_piazza_id': lecture_piazza_id
            }
        }
    )
    return post


def create_followup_question(lecture_post_id, url, tag, question, network=None,
                             piazza_course_id=None, identity_msg="posted Anonymously"):
    """Adds a followup question to a given lecture post. Takes in a lecture number,
    course id, and contents of a question.
    piazza_course_id: (the id in the url)- piazza.com/<piazza_course_id>
    Returns the question dictionary with the following contents:
        id: the lecture post id
        uid: the id of the specific followup question that was created
        subject: the content of the followup question
    """
    if not network:
        network = piazza.network(piazza_course_id)
    rpc = network._rpc
    post = rpc.content_get(lecture_post_id)
    followup = network.create_followup(
        post=post,
        content="<b><a href={0}>{1}</a></b> {2}<p>{3}</p>".format(url, tag,
                                                                  question,
                                                                  identity_msg)
    )
    return followup


def edit_post(network=None, piazza_course_id=None, cid=None, post_data=None,
              title=None, content=None):
    """Edits a post and changes the body and/or the title
    Returns the updated post with the following contents:
        nr: The id of the lecture post
        created: time created
        children: Followup questions
    """
    if not network:
        network = piazza.network(piazza_course_id)
    if post_data is None:
        post_data = network.get_post(cid)
    params = {
        'cid': post_data['id'],
        'subject': title or post_data['history'][0]['subject'],
        'content': content or post_data['history'][0]['content'],
        'folders': post_data['folders'],
        'revision': len(post_data['history']),
        'type': post_data['type']
    }
    return network._rpc.request("content.update", params)


def get_followup(post_id, followup_id, network=None, piazza_course_id=None):
    """
    Gets a followup from a question.
    post_id: the id of the lecture question post
    followup_id: Id of the followup post
    Returns the followup dictionary with the following contents:
        id: the lecture post id
        uid: the id of the specific followup question that was created
        subject: the content of the followup question
    """
    if not network:
        network = piazza.network(piazza_course_id)
    rpc = network._rpc
    lecture_post = network.get_post(post_id)
    for child in lecture_post['children']:
        if child['id'] == followup_id:
            return child


def recreate_master_post(master_id, course_ok_id, db, network=None,
                         piazza_course_id=None):
    """
    Takes in:
    lecture: array of dictionaries containing date, lecture name, and lecture_piazza_id,
    master_id: Master thread's id on Piazza
    piazza_course_id: the Piazza course id (the id in the url) piazza.com/<piazza_course_id>

    Creates a master post that links to all Hermes lecture posts

    Returns: the created master post dictionary

    Note: There cannot be duplicate titles in Piazza
    """
    if not network:
        network = piazza.network(piazza_course_id)
    rpc = network._rpc
    piazza_ids = []
    lectures = db[Lecture.collection].find(
        {
            "course_ok_id": course_ok_id
        }
    ).sort("date", 1)
    for lecture in lectures:
        piazza_ids.append({
            "date": lecture["date"],
            "name": lecture["name"],
            "lecture_piazza_id": lecture["lecture_piazza_id"]
        })
    content = "All lectures with their dates, names, and threads will be posted here."
    for lecture in piazza_ids:
        content += "<p>{0}: &#64;{1}</p>".format(
            lecture["name"],
            lecture["lecture_piazza_id"])
    content += "#pin"
    edit_post(network=network, piazza_course_id=piazza_course_id,
              cid=master_id, content=content)



def pin_post(post_id, network=None, piazza_course_id=None):
    if not network:
        network = piazza.network(piazza_course_id)
    rpc = network._rpc
    post = network.get_post(post_id)
    post_content = post["history"][0]["content"]
    post_content += "<p>#pin</p>"
    edit_post(network=network, piazza_course_id=piazza_course_id, cid=post_id, content=post_content)


def unpin_post(post_id, network=None, piazza_course_id=None):
    if not network:
        network = piazza.network(piazza_course_id)
    rpc = network._rpc
    post = network.get_post(post_id)
    post_content = post["history"][0]["content"].replace("#pin", "")
    edit_post(network=network, piazza_course_id=piazza_course_id, cid=post_id, content=post_content)


def delete_post(network=None, piazza_course_id=None, cid=None, post_data=None,
                title=None, content=None):
    """Deletes a post
    """
    if not network:
        network = piazza.network(piazza_course_id)
    if post_data is None:
        post_data = network.get_post(cid)
    params = {
        'cid': post_data['id'],
        'subject': None,
        'content': None,
        'folders': None,
        'revision': None,
        'type': None
    }
    try:
        return network._rpc.request("content.delete", params)
    except:
        return

def add_unadded_lectures(db,course_ok_id):
    not_on_piazza_db_obj = db[Lecture.collection].find({
        "lecture_piazza_id": "",
        "course_ok_id": course_ok_id
    })

    for lecture in not_on_piazza_db_obj:
        lecture_post = Piazza.create_lecture_post(
            lecture_title=lecture["name"],
            date=lecture["date"],
            piazza_course_id=piazza_course_id,
            master_id=piazza_master_post_id
        )
