from pymongo import MongoClient
import os

def insert(dbobj, db):
    return db[dbobj.collection].insert_one(dbobj.to_dict())

def get_keys(d, keys):
    return {key: d[key] for key in keys}

def encode_url(s):
    return s.lower().replace(' ', '-')

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


class Class(DBObject):

    collection = 'Classes'

    def __init__(self, **attr):
        DBObject.__init__(self, **attr)

    @staticmethod
    def add_lecture(cls, lecture, db):
        id = insert(lecture, db).inserted_id
        questions_id = insert(
            Question(
                lecture_id=id,
                lecture_name=lecture.get('name'),
                questions=[]
            ), db).inserted_id
        db[Lecture.collection].update_one(
            {
              '_id': id
            },
            {
              '$set': {
                'questions_id': questions_id
              }
            },
            upsert=False
        )
        return db[Class.collection].update_one(
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


class Note(DBObject):

    collection = 'Notes'

    def __init__(self, **attr):
        DBObject.__init__(self, **attr)

class Lecture(DBObject):

    collection = 'Lectures'

    def __init__(self, **attr):
        DBObject.__init__(self, **attr)

    @staticmethod
    def write_question(lecture, question, db):

        return db[Question.collection].update_one(
            {
              '_id': lecture['questions_id']
            },
            {
              '$push': {
                'questions': question
              }
            },
            upsert=False
        )

class Question(DBObject):

    collection = 'Questions'

    def __init__(self, **attr):
        DBObject.__init__(self, **attr)

if __name__ == '__main__':
    client = MongoClient(os.environ.get('MONGODB_URI'))
    db = client[os.environ.get('DATABASE_NAME')]
