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
        return db[Class.collection].update_one(
            {
              '_id': cls['_id']
            },
            {
              '$set': {
                'Lectures': cls['Lectures'] + [id]
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

if __name__ == '__main__':
    client = MongoClient(os.environ.get('MONGODB_URI'))
    db = client[os.environ.get('DATABASE_NAME')]
