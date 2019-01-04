import os
import piazza_api as p
from pprint import pprint

piazza = p.Piazza()
piazza.user_login(email=os.environ.get("PIAZZA_EMAIL"),password=os.environ.get("PIAZZA_PASSWORD"))

def create_master_post(folders, content = "", network = None, piazza_course_id = None):
    """
    Takes in:
    folders: array of which folders hermes posts should be in),
    content: the content of the post,
    piazza_course_id: the piazz
    Creates a master post where links to all the hermes posts will be put.
    Returns the created master post dictionary
    Note that there cannot be duplicate titles in Piazza
    """
    if not network:
        network = piazza.network(piazza_course_id)
    if not content:
        content = "All lectures with their dates, names, and threads will be posted here. \n \n #pin"
    else:
        content = content + "\n \n #pin"
    dct = {
        "type": "note",
        "title":"Hermes Master Thread",
        "subject": "Hermes Master Thread",
        "content":"All lectures with their dates, names, and threads will be posted here. \n \n #pin",
        "folders": folders
        }
    rpc = network._rpc
    master_post = rpc.content_create(dct)
    return master_post

def edit_master(post, network= None,piazza_course_id= None, master_id = None, lecture_title = None):
    """
    Adds a tag of the most recently added lecture to the body of the master post
    Returns the updated master post.
    Note the &#64 is the @ symbol
    """
    if not network:
        network = piazza.network(piazza_course_id)
    full_content_master = network.get_post(master_id)
    old_vers = full_content_master['history'][0]['content']
    split_by_pin = old_vers.split("<p>#pin")
    if len(split_by_pin) > 1:
        new_vers = split_by_pin[0]+"<p>&#64;" + lecture_title + str(post['nr']) + "</p> \n #pin"
    else:
        new_vers = old_vers+"<p>" + lecture_title + " &#64;"+ str(post['nr'])+ "</p>"
    return edit_post(network = network, cid=master_id, \
        post_data = full_content_master,content = new_vers)

def create_lecture_post(folders, lecture_title, date, network = None, piazza_course_id = None, master_id = None, content = None):
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
        content = "Lecture thread for "+lecture_title + \
        ". Ask questions regarding this lecture below and fellow students/staff \
        will respond."
    dct = {
        "type": "note",
        "title":"Lecture Thread for "+ lecture_title + "("+ date+")" ,
        "subject": "Lecture Thread for "+ lecture_title + "("+ date+")" ,
        "content":content,
        "folders": folders}
    rpc = network._rpc
    post = rpc.content_create(dct)
    edit_master(post = post, network = network, master_id = master_id, lecture_title=lecture_title)
    return post

def create_followup_question(lecture_post_id, url,tag, question, network = None, piazza_course_id = None):
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
    question = "<b><a href = " + url +">" + tag + "</a></b> " + question
    followup = network.create_followup(post=post, content=question)
    return followup

def edit_post(network=None, piazza_course_id = None, cid=None, post_data=None, title=None, content=None):
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
        'cid':post_data['id'],
        'subject' : post_data['history'][0]['subject'] if title is None else title,
        'content' : post_data['history'][0]['content'] if content is None else content,
        'folders' : post_data['folders'],
        'revision' : len(post_data['history']),
        'type' : post_data['type']
    }
    return network._rpc.request("content.update", params)

def get_followup(post_id, followup_id,network = None, piazza_course_id = None):
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
        if child['uid'] == followup_id:
            return child
