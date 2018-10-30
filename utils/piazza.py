import os
import piazza_api as p

piazza = p.Piazza()
piazza.user_login(email=os.environ.get("PIAZZA_EMAIL"),password=os.environ.get("PIAZZA_PASSWORD"))

def create_master_post(folders, course_id):
    """
    Creates a master post where links to all the hermes posts will be put.
    """
    dct = {
        "type": "note",
        "title":"Hermes Master Thread",
        "subject": "Hermes Master Thread",
        "content":"All lectures with their dates, names, and threads will be posted here. \n \n #pin",
        "folders": folders
        }
    network = piazza.network(course_id)
    rpc = network._rpc
    post = rpc.content_create(dct)

def edit_master(network, post):
    """
    Adds a tag of the most recently added lecture to the body of the master post
    Returns the updated master post.
    """
    master_post = get_master_thread(network)
    full_content_master = network.get_post(master_post['id'])
    old_vers = full_content_master['history'][0]['content']
    split_by_pin = old_vers.split("<p>pin")
    if len(split_by_pin) > 1:
        new_vers = split_by_pin[0]+"<p>&#64;" + str(post['nr']) + "</p> \n #pin"
    else:
        new_vers = old_vers+"<p>&#64;"+str(post['nr'])+ "</p>"
    edit_post(network = network, cid=master_post['nr'], post_data=full_content_master,content = new_vers)
    return post

def get_master_thread(network = None ,course_id = None):
    if not network:
        network = piazza.network(course_id)
    rpc = network._rpc
    posts = rpc.search("Hermes Master Thread")
    for post in posts:
        if 'instructor-note' in post['tags'] and post['subject'] == "Hermes Master Thread":
            return post
    return None

def create_lecture_post(lecture_number, folders, course_id):
    """
    Creates a lecture post on piazza for a given lecture number. Takes in
    an array of folders that it will put the course in as well as the course_id
    for a course on piazza.
    Returns the lecture post
    """
    dct = {
        "type": "note",
        "title":"Hermes- Lecture number"+str(lecture_number) ,
        "subject": "Hermes- Lecture number "+str(lecture_number) ,
        "content":"Lecture thread for Lecture number "+str(lecture_number) + \
        ". Ask questions regarding this lecture below and fellow students/staff \
        will respond.",
        "folders": folders
        }
    network = piazza.network(course_id)
    rpc = network._rpc
    post = rpc.content_create(dct)
    edit_master(network, post)
    return post

def create_followup_question(lecture_number, course_id, question):
    """Adds a followup question to a given lecture post. Takes in a lecture number,
    course id, and contents of a question.
    Returns the question
    """
    network = piazza.network(course_id)
    rpc = network._rpc
    post = rpc.content_get(lecture_number)
    followup = network.create_followup(post=post, content=question)
    return followup

def edit_post(network, cid=None, post_data=None, title=None, content=None):
    """Edits a post and changes the body and/or the title
    Returns the updated post
    """
    if post_data is None:
        post_data = network.get_post(cid)
    print(post_data)
    params = {
        'cid':post_data['id'],
        'subject' : post_data['history'][0]['subject'] if title is None else title,
        'content' : post_data['history'][0]['content'] if content is None else content,
        'folders' : post_data['folders'],
        'revision' : len(post_data['history']),
        'type' : post_data['type']
    }
    return network._rpc.request("content.update", params)
