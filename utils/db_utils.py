from pymongo import MongoClient
from bson.objectid import ObjectId
import os

def insert(dbobj, db):
    return db[dbobj.collection].insert_one(dbobj.to_dict())

def get_keys(d, keys):
    return {key: d.get(key) for key in keys}

def encode_url(s):
    return s.lower().replace(' ', '-')

def find_by_id(id, collection, db):
    return db[collection].find({'_id': ObjectId(id)})

def find_one_by_id(id, collection, db):
    return db[collection].find({'_id': ObjectId(id)})

class DBObject:

    collection = None

    def __init__(self, **attr):
        self.attributes = attr

    def get(self, key):
        return self.attributes.get(key)

    def to_dict(self):
        return self.attributes

class User(DBObject):

    collection = 'Users'

    def __init__(self, **attr):
        DBObject.__init__(self, **attr)

    @staticmethod
    def register_user(ok_data, db):
        if db[User.collection].find({'ok_id': ok_data['id']}).count() == 0:
            attr = get_keys(
                ok_data,
                ['name', 'email', 'is_admin']
            )
            attr['ok_id'] = ok_data['id']
            u = User(**attr)
            return insert(u, db)

    @staticmethod
    def add_admin_google_credentials(id, credentials, db):
        db[User.collection].update_one(
            {
                '_id': id
            },
            {
                '$set': {
                    'google_credentials': credentials
                }
            },
            upsert=False
        )


class Class(DBObject):

    collection = 'Classes'

    def __init__(self, **attr):
        DBObject.__init__(self, **attr)

    @staticmethod
    def add_lecture(cls, lecture, db):
        id = insert(lecture, db).inserted_id
        db[Class.collection].update_one(
            {
              '_id': cls['_id']
            },
            {
              '$push': {
                'Lectures': id,
              }
            },
            upsert=False
        )
        return id


class Note(DBObject):

    collection = 'Notes'

    def __init__(self, **attr):
        DBObject.__init__(self, **attr)

class Lecture(DBObject):

    collection = 'Lectures'

    def __init__(self, **attr):
        DBObject.__init__(self, **attr)


    @staticmethod
    def add_transcript(lecture_id, transcript, db):
        db[Lecture.collection].update_one(
            {
              '_id': lecture_id
            },
            {
              '$set': {
                'transcript': transcript,
              }
            },
            upsert=False
        )



class Question(DBObject):

    collection = 'Questions'

    def __init__(self, **attr):
        DBObject.__init__(self, **attr)

    @staticmethod
    def write_question(question, db):
        def convert_seconds_to_timestamp(ts):
            return '%d:%02d' % (ts // 60, ts % 60)
        question['timestamp'] = convert_seconds_to_timestamp(
            round(float(question['seconds'])))
        return insert(
            Question(
                seconds=float(question['seconds']),
                timestamp=question['timestamp'],
                text=question['text'],
                name=question['name'],
                ok_id=question['ok_id'],
                lecture_id=question['lecture']
            ),
            db
        ).inserted_id

    def edit_answer(id, question, db):
        return db[collection].update({
            {'id':id},
            {
              '$set': {
                'question': question["text"],
              }
            },
        }, upsert = False).inserted_id

class Answer(DBObject):

    collection = 'Answers'

    def __init__(self, **attr):
        DBObject.__init__(self, **attr)

    @staticmethod
    def add_answer(answer, db):
        return insert(
            Answer(
                question_id=answer['question_id'],
                text=answer['text'],
                user_id=answer['user_id'],
                name=answer['name'],
                upvotes=0,
                endorsed=False
            ),
            db
        ).inserted_id

    def edit_answer(answer_id, answer, db):
        return db[collection].update_one({
            {'id': answer_id},
            {
              '$set': {
                'text': answer["text"],
              }
            },
        }, upsert = False).inserted_id


if __name__ == '__main__':
    client = MongoClient(os.environ.get('MONGODB_URI'))
    db = client[os.environ.get('DATABASE_NAME')]
