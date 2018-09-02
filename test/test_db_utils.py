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
def create_users(returned_ids, collection, db):
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
    create_users(returned_ids, collection, db)
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
    create_users(returned_ids, collection, db)
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

#Tests the Class Methods
def create_classes(returned_ids, collection, db):
    for i in range(100):
        info = dbu.Class.create_class('CS61'+str(i),
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
                assert dbu.Class.get_semester(offering) == "FA" + str(i)
            if j == 1:
                assert dbu.Class.get_semester(offering) == "SP" + str(i)
            if j == 2:
                assert dbu.Class.get_semester(offering) == "SU" + str(i)

def test_create_class():
    db = mongomock.MongoClient().db
    collection = db.create_collection("Classes")
    returned_ids = []
    create_classes(returned_ids,collection, db)
    for i in range(100):
        item = dbu.find_one_by_id(returned_ids[i], "Classes", db)
        assert item['lectures'] == []
        assert item['students'] ==[]
        assert item['display_name'] == "CS61"+str(i)
        assert item['semester'] == "FA" + str(i)
        assert item['ok_id'] == i


#Tests the Lecture Methods

#Tests Resource Methods

#Tests Question Methods

#Tests Answer Methods


if __name__ == '__main__':
    test_register_user()
    test_google_credentials()
    test_get_semester()
    test_create_class()
