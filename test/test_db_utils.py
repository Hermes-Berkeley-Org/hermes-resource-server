import os, sys
sys.path.append(".")
sys.path.append("..")
sys.path.append("../utils")
sys.path.append("./utils")
import db_utils as dbu
from datetime import datetime
import pytest, mongomock
from bson.objectid import ObjectId
from pprint import pprint #helps print out pymongo curser items nicely

#Tests the User Methods
def create_test_users(returned_ids, collection, db):
    for i in range(100):
        info = dbu.User.register_user({'id':str(i) ,
            'name' : "Kartik" + str(i),
            "is_admin" : False,
            "participations": [{'role': 'staff',
            'course':{'id':1, "display_name":"CS61D",
            "offering" : "fa18"}}]}, db)
        returned_ids.append(info.inserted_id)
        assert collection.count() == (i + 1)
    return returned_ids

def test_register_user():
    db = mongomock.MongoClient().db
    collection = db.create_collection("Users")
    returned_ids = []
    create_test_users(returned_ids, collection, db)
    for i in range(100):
        item = dbu.find_one_by_id(returned_ids[i], "Users", db)
        assert item['name'] == "Kartik" + str(i)
        assert int(item["ok_id"])== i
    # cursor = collection.find({})
    # for document in cursor:
    #     pprint(document)

def test_google_credentials():
    db = mongomock.MongoClient().db
    collection = db.create_collection("Users")
    returned_ids = []
    create_test_users(returned_ids, collection, db)
    for i in range(100):
        dbu.User.add_admin_google_credentials(returned_ids[i],
                {"token": "abcdefgh" + str(i),
                "refresh_token": "kartik" + str(i),
                "token_uri": "https://accounts.google.com/o/oauth2/token"+str(i),
                "client_id": "123.apps.googleusercontent.com"+str(i),
                "client_secret": "asfgh"+str(i),
                "scopes": [
                    "https://www.googleapis.com/auth/youtube.force-ssl"+str(i)
                    ]}, db)
    for i in range(100):
        item = dbu.find_one_by_id(returned_ids[i],"Users", db)
        google_creds = item['google_credentials']
        assert google_creds['token'] == "abcdefgh"+str(i)
        assert google_creds['refresh_token'] == "kartik"+str(i)
        assert google_creds['token_uri'] == "https://accounts.google.com/o/oauth2/token"+str(i)
        assert google_creds["client_secret"] ==  "asfgh"+str(i)
        assert len(google_creds['scopes']) == 1
        assert google_creds['scopes'][0] == "https://www.googleapis.com/auth/youtube.force-ssl"+str(i)
    for i in range(100):
        dbu.User.remove_google_credentials(returned_ids[i], db)
    for i in range(100):
        item = dbu.find_one_by_id(returned_ids[i],"Users", db)
        assert len(item['google_credentials']) == 0

#Tests the Course Methods
def create_test_courses(returned_ids, collection, db):
    for i in range(100):
        info = dbu.Course.create_course('CS61'+str(i),
            {"id" : i ,
             "offering" : "cal/cs61a/fa" + str(i),
             "active" : True,
             "ok_id" : str(i)},
              db)
        returned_ids.append(info.inserted_id)
    return returned_ids

def test_get_semester():
    sems =['cal/cs61d/fa' , 'cal/cs61d/sp', 'cal/cs61d/su']
    for i in range(100):
        for j in range(len(sems)):
            offering = sems[j] + str(i)
            if j == 0:
                assert dbu.Course.get_semester(offering) == "FA" + str(i)
            if j == 1:
                assert dbu.Course.get_semester(offering) == "SP" + str(i)
            if j == 2:
                assert dbu.Course.get_semester(offering) == "SU" + str(i)

def test_create_course():
    db = mongomock.MongoClient().db
    collection = db.create_collection("Courses")
    returned_ids = []
    create_test_courses(returned_ids,collection, db)
    for i in range(100):
        item = dbu.find_one_by_id(returned_ids[i], "Courses", db)
        assert item['lectures'] == []
        assert item['students'] ==[]
        assert item['display_name'] == "CS61"+str(i)
        assert item['semester'] == "FA" + str(i)
        assert item['ok_id'] == i

#Tests the Lecture Methods

def create_test_lectures(cls,returned_ids, collection, db):
    for i in range(100):
        lec = dbu.Lecture(
            name = "lect" + str(i),
            url = "lect" + str(i),
            date = "2018-3-9",
            link = "https://www.youtube.com/watch?v=5B5tJWrCtoI",
            lecture_number= i
        )
        info = dbu.Course.add_lecture(cls, lec, db)
        returned_ids.append(info)

def test_create_lecture():
    db = mongomock.MongoClient().db
    collection = db.create_collection("Courses")
    lecs = db.create_collection("Lectures")
    returned_ids = []
    course_id = dbu.Course.create_course('CS61',
        {"id" : 1 ,
         "offering" : "cal/cs61a/fa",
         "active" : True,
         "ok_id" : 1},
          db)
    cls = (dbu.find_one_by_id(course_id.inserted_id, "Courses", db))
    create_test_lectures(cls, returned_ids ,collection, db)
    for i in range(100):
        item = dbu.find_one_by_id(returned_ids[i], "Lectures", db)
        item['name'] == "lect" + str(i),
        item['url'] == "lect" + str(i),
        item['date'] == "2018-3-9",
        item['link'] == "https://www.youtube.com/watch?v=5B5tJWrCtoI",
        item['lecture_number'] == i

def create_test_transcript(tst_transcript):
    beginmin = 0
    endmin = 0
    beginsec = 1
    endsec = 6
    beginhour = 0
    endhour = 0
    for i in range(10000):
        dct = {
            "begin": str(beginhour).zfill(2) + ":" + str(beginmin).zfill(2) + ":" + str(beginsec).zfill(2) + ".000",
            "end": str(endhour).zfill(2)+ ":"+ str(endmin).zfill(2) + ":"+ str(endsec).zfill(2) + ".000",
            "text": str(i)
        }
        tst_transcript.append(dct)
        beginsec += 4
        endsec += 6
        if endsec//60 > 0:
            endmin += 1
            endsec = endsec%60
        if beginsec//60 > 0:
            beginmin += 1
            beginsec = beginsec%60
        if beginmin//60 > 0:
            beginhour += 1
            beginmin = beginmin%60
        if endmin//60 > 0:
            endhour += 1
            endmin = endmin%60
    return tst_transcript

def test_add_transcript():
    tst_transcript = []
    create_test_transcript(tst_transcript)
    beginmin = 0
    endmin = 0
    beginsec = 1
    endsec = 6
    beginhour = 0
    endhour = 0
    assert len(tst_transcript) == 10000
    for i in range(10000):
        info = tst_transcript[i]
        assert info['begin'] == str(beginhour).zfill(2) + ":" + str(beginmin).zfill(2) + ":" + str(beginsec).zfill(2)+ ".000"
        assert info['end'] == str(endhour).zfill(2) + ":" + str(endmin).zfill(2) + ":" + str(endsec).zfill(2) + ".000"
        assert info['text'] == str(i)
        beginsec += 4
        endsec += 6
        if endsec//60 > 0:
            endmin += 1
            endsec = endsec%60
        if beginsec//60 > 0:
            beginmin += 1
            beginsec = beginsec%60
        if beginmin//60 > 0:
            beginhour += 1
            beginmin = beginmin%60
        if endmin//60 > 0:
            endhour += 1
            endmin = endmin%60


#Tests Resource Methods


if __name__ == '__main__':
    test_register_user()
    test_google_credentials()
    test_get_semester()
    test_create_course()
    test_create_lecture()
    test_add_transcript()
