import os
from datetime import datetime

from pymongo import MongoClient
from bson.objectid import ObjectId



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

    def set(self, key, value):
        self.attributes[key] = value


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
        def change_date_format(lecture):
            british_date = lecture.get('date')
            date = datetime.strptime(british_date, "%Y-%m-%d")
            lecture.set('date', date.strftime("%m/%d/%y"))
        change_date_format(lecture)
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

    @staticmethod
    def save_textbook(documents, links, db, class_ok_id):
        db[Class.collection].update_one(
            {
                'ok_id': class_ok_id
            },
            {
                '$set': {
                    'documents': documents,
                    'links': links
                }
            }
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
    def add_transcript(lecture_id, transcript, preds, db):
        db[Lecture.collection].update_one(
            {
              '_id': lecture_id
            },
            {
              '$set': {
                'transcript': transcript,
                'preds': preds
              }
            },
            upsert=False
        )

    @staticmethod
    def edit_transcript(data, db):
        lecture = find_one_by_id(data['lecture_id'], Lecture.collection, db)
        def replace_transcript_elem(lecture, index, text):
            transcript = lecture['transcript']
            transcript_elem = transcript[index]
            transcript_elem['text'] = text
            return transcript[:index] + [transcript_elem] + transcript[index+1:]
        db[Lecture.collection].update_one(
            {
                '_id': ObjectId(data['lecture_id'])
            },
            {
                '$set': {
                    'transcript': replace_transcript_elem(lecture, int(data['index']), data['text'])
                }
            }
        )

    @staticmethod
    def delete_lecture(data, db):
        db[Lecture.collection].delete_one(
            {
                '_id': ObjectId(data['lectureid'])
            }
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
                upvotes =[],
                anon = question['anon']
            ),
            db
        ).inserted_id

    @staticmethod
    def edit_question(data, db):
        edit = data['text']
        return db[Question.collection].update_one(
            {'_id': ObjectId(data['questionId'])},
            {
              '$set': {
                'text': edit,
              }
            })

    @staticmethod
    def delete_question(question, db):
        question_id = question['question_id']
        result = db[Question.collection].delete_one(
        {'_id': ObjectId(question_id)}
        )

    @staticmethod
    def upvote_question(data, db):

        user_id = data['user_id']
        upvotes =  find_one_by_id(data['question_id'], Question.collection, db)['upvotes']

        if user_id not in upvotes:
            return db[Question.collection].update_one(
                {
                    '_id': ObjectId(data['question_id'])
                },
                {
                    '$addToSet': {
                        'upvotes': user_id
                    }
                },
                upsert=False
            )
        else:
            return db[Question.collection].update_one(
                {
                    '_id': ObjectId(data['question_id'])
                },
                {
                    '$pop': {
                        'upvotes': user_id
                    }
                },
                upsert=False
            )

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
    def edit_answer(data, db):
        edit = data['text']

        return db[Answer.collection].update_one(
            {'_id': ObjectId(data['answerId'])},
            {
              '$set': {
                'text': edit,
              }
            }
        )

    @staticmethod
    def upvote_answer(data, db):

        user_id = data['user_id']
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

    @staticmethod
    def delete_answer(answer, db):
        answer_id = answer['answer_id']
        return db[Answer.collection].delete_one(
        {'_id': ObjectId(answer_id)}
        )


if __name__ == '__main__':
    client = MongoClient(os.environ.get('MONGODB_URI'))
    db = client[os.environ.get('DATABASE_NAME')]
