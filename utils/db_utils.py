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
    return db[collection].find_one({'_id': ObjectId(id)})

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
            classes = []
            for participation in ok_data['participations']:
                classes.append({
                    'ok_id': participation['course']['id'],
                    'display_name': participation['course']['display_name'],
                    'offering': participation['course']['offering'],
                    'role': participation['role']
                })
            attr['classes'] = classes
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

    @staticmethod
    def remove_google_credentials(id, db):
        db[User.collection].update_one(
            {
                '_id': id
            },
            {
                '$set': {
                    'google_credentials': {}
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
                'lectures': id,
              }
            },
            upsert=False
        )
        return id

    @staticmethod
    def get_semester(offering):
        return offering.split('/')[-1].upper()

    @staticmethod
    def create_class(display_name, data, db):
        data['display_name'] = display_name
        return insert(
            Class(
                lectures=[],
                semester=Class.get_semester(data['offering']),
                **data
            ),
            db
        )


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
                lecture_id=question['lecture'],
                anon = question['anon']
            ),
            db
        ).inserted_id

    @staticmethod
    def edit_question(id, question, db):
        return db[Question.collection].update({
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
    def write_answer(user, answer, db):
        return insert(
            Answer(
                question_id=ObjectId(answer['question_id']),
                text=answer['text'],
                user=user['_id'],
                name=user['name'],
                upvotes=[],
                anon= answer['anon']
            ),
            db
        ).inserted_id

    @staticmethod
    def edit_answer(answer_id, answer, db):
        return db[Answer.collection].update_one({
            {'_id': answer_id},
            {
              '$set': {
                'text': answer["text"],
              }
            },
        }, upsert = False).inserted_id

    @staticmethod
    def upvote_answer(data, db):

        user_id = data['user_id']
        print(user_id)
        upvotes =  find_one_by_id(data['answer_id'], Answer.collection, db)['upvotes']

        if user_id not in upvotes:
            return db[Answer.collection].update_one(
                {
                    '_id': ObjectId(data['answer_id'])
                },
                {
                    '$addToSet': {
                        'upvotes': user_id
                    }
                },
                upsert=False
            )
        else:
            return db[Answer.collection].update_one(
                {
                    '_id': ObjectId(data['answer_id'])
                },
                {
                    '$pop': {
                        'upvotes': user_id
                    }
                },
                upsert=False
            )


if __name__ == '__main__':
    client = MongoClient(os.environ.get('MONGODB_URI'))
    db = client[os.environ.get('DATABASE_NAME')]
