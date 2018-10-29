import os
import piazza_api as p
piazza = p.Piazza()
piazza.user_login(email=os.environ.get("PIAZZA_EMAIL"),password=os.environ.get("PIAZZA_PASSWORD"))
network = piazza.network("jhf7k1p4m3n364")
rpc = network._rpc

def create_lecture_post(lecture_number, folders):
    dct = {
        "type": "note",
        "title":"Hermes- Lecture number"+str(lecture_number) ,
        "subject": "Hermes- Lecture number "+str(lecture_number) ,
        "content":"Lecture thread for Lecture number "+str(lecture_number) + \
        ". Ask questions about this questions below.",
        "folders": folders
        }
    return piazza.content_create(dct['nr'])

def create_followup_question(lecture_number, question):
    post = rpc.content_get(lecture_number)
    followup = network.create_followup(post=post, content=question)
    return followup

print(create_followup_question(9, "Why?"))
