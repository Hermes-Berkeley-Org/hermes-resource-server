from pymongo import MongoClient
import os

def insert(dbobj, db):
    return db[dbobj.collection].insert_one(dbobj.to_dict())

class DBObject:

    def __init__(self, collection, **attr):
        self.collection = collection
        self.attributes = attr

    def get(self, key):
        return self.attributes.get(key)

    def to_dict(self):
        return self.attributes

class User(DBObject):

    def __init__(self, **attr):
        DBObject.__init__(self, 'Users', **attr)

class Class(DBObject):

    def __init__(self, **attr):
        DBObject.__init__(self, 'Classes', **attr)

class Note(DBObject):

    def __init__(self, **attr):
        DBObject.__init__(self, 'Notes', **attr)

class Lecture(DBObject):

    def __init__(self, **attr):
        DBObject.__init__(self, 'Lectures', **attr)

if __name__ == '__main__':
    client = MongoClient(os.environ.get('MONGODB_URI'))
    db = client[os.environ.get('DATABASE_NAME')]
