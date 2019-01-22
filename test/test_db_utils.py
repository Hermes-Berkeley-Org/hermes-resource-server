import os, sys
sys.path.append(".")
sys.path.append("..")
sys.path.append("../utils")
sys.path.append("./utils")
import db_utils as dbu
from datetime import datetime, date
import json
import pytest, mongomock
from bson.objectid import ObjectId
from pprint import pprint #helps print out pymongo curser items nicely
import unittest

class TestDBUtils(unittest.TestCase):
    def create_test_users(self, returned_ids, collection, db):
        for i in range(100):
            info = dbu.User.register_user({'id':str(i) ,
                'name' : "Kartik" + str(i),
                "is_admin" : False,
                "participations": [{'role': 'staff',
                'course':{'id':1, "display_name":"CS61D",
                "offering" : "fa18"}}]}, db)
            returned_ids.append(info.inserted_id)
            self.assertEqual(collection.count_documents({}), i + 1)
        return returned_ids

    def test_register_user(self):
        db = mongomock.MongoClient().db
        collection = db.create_collection("Users")
        returned_ids = []
        self.create_test_users(returned_ids, collection, db)
        for i in range(100):
            item = dbu.find_one_by_id(returned_ids[i], "Users", db)
            self.assertEqual(item['name'], "Kartik" + str(i))
            self.assertEqual(int(item["ok_id"]), i)
        # cursor = collection.find({})
        # for document in cursor:
        #     pprint(document)

    def test_google_credentials(self):
        db = mongomock.MongoClient().db
        collection = db.create_collection("Users")
        returned_ids = []
        self.create_test_users(returned_ids, collection, db)
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
            self.assertEqual(google_creds['token'], "abcdefgh" + str(i))
            self.assertEqual(google_creds['refresh_token'], "kartik" + str(i))
            self.assertEqual(google_creds['token_uri'], "https://accounts.google.com/o/oauth2/token" + str(i))
            self.assertEqual(google_creds["client_secret"], "asfgh" + str(i))
            self.assertEqual(len(google_creds['scopes']), 1)
            self.assertEqual(google_creds['scopes'][0], "https://www.googleapis.com/auth/youtube.force-ssl" + str(i))
        for i in range(100):
            dbu.User.remove_google_credentials(returned_ids[i], db)
        for i in range(100):
            item = dbu.find_one_by_id(returned_ids[i],"Users", db)
            self.assertEqual(len(item['google_credentials']), 0)

    #Tests the Course Methods
    def create_test_courses(self, returned_ids, collection, db):
        for i in range(100):
            info = dbu.Course.create_course(
                 offering =  "cal/cs61a/fa" + str(i),
                 display_name = 'CS61'+str(i),
                 course_ok_id = str(i) ,
                 db = db)
            returned_ids.append(info.inserted_id)
        return returned_ids

    def test_get_semester(self):
        sems =['cal/cs61d/fa' , 'cal/cs61d/sp', 'cal/cs61d/su']
        for i in range(100):
            for j in range(len(sems)):
                offering = sems[j] + str(i)
                if j == 0:
                    self.assertEqual(dbu.Course.get_semester(offering), "FA" + str(i))
                if j == 1:
                    self.assertEqual(dbu.Course.get_semester(offering), "SP" + str(i))
                if j == 2:
                    self.assertEqual(dbu.Course.get_semester(offering), "SU" + str(i))

    def test_create_course(self):
        db = mongomock.MongoClient().db
        collection = db.create_collection("Courses")
        returned_ids = []
        self.create_test_courses(returned_ids,collection, db)
        for i in range(100):
            item = dbu.find_one_by_id(returned_ids[i], "Courses", db)
            self.assertEqual(item['display_name'], "CS61" + str(i))
            self.assertEqual(item['course_ok_id'], str(i))

    #Tests the Lecture Methods

    def create_test_lectures(self, cls, returned_ids, collection, db):
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

    def test_create_lecture(self):
        db = mongomock.MongoClient().db
        collection = db.create_collection("Courses")
        lecs = db.create_collection("Lectures")
        returned_ids = []
        course_id = dbu.Course.create_course(
            display_name = 'CS61',
            offering = "cal/cs61a/fa",
            course_ok_id =  "1",
              db = db)
        cls = (dbu.find_one_by_id(course_id.inserted_id, "Courses", db))
        self.create_test_lectures(cls, returned_ids ,collection, db)
        for i in range(100):
            item = dbu.find_one_by_id(returned_ids[i], "Lectures", db)
            self.assertEqual(item['name'], "lect" + str(i))
            self.assertEqual(item['url'], "lect" + str(i))
            self.assertEqual(datetime.strptime(item['date'], "%m/%d/%y"), datetime.strptime("2018-3-9", "%Y-%m-%d"))
            self.assertEqual(item['link'], "https://www.youtube.com/watch?v=5B5tJWrCtoI")
            self.assertEqual(item['lecture_number'], i)

    def create_test_transcript(self, tst_transcript):
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

    def test_add_transcript(self):
        tst_transcript = []
        self.create_test_transcript(tst_transcript)
        beginmin = 0
        endmin = 0
        beginsec = 1
        endsec = 6
        beginhour = 0
        endhour = 0
        self.assertEqual(len(tst_transcript), 10000)
        for i in range(10000):
            info = tst_transcript[i]
            self.assertEqual(info['begin'], str(beginhour).zfill(2) + ":" + str(beginmin).zfill(2) + ":" + str(beginsec).zfill(2)+ ".000")
            self.assertEqual(info['end'], str(endhour).zfill(2) + ":" + str(endmin).zfill(2) + ":" + str(endsec).zfill(2) + ".000")
            self.assertEqual(info['text'], str(i))
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

if __name__ == '__main__':
    unittest.main()
