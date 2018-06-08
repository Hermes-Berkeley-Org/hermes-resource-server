import os
from datetime import datetime

from collections import defaultdict
from operator import itemgetter

from pymongo import MongoClient
from bson.objectid import ObjectId

from utils.app_utils import edit_distance

import logging

logger = logging.getLogger('app_logger')
logger.setLevel(logging.INFO)

EDIT_DISTANCE_PER_WORD = 5
TRANSCRIPT_SUGGESTIONS_NECESSARY = 5

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
                students=[],
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
    def suggest_transcript(data, db):
        lecture = find_one_by_id(data['lecture_id'], Lecture.collection, db)
        def replace_transcript_elem(lecture, index, text, user_id):
            def push_onto_transcript_if_elected(transcript_elem):
                suggestions = defaultdict(int)
                for user, suggestion in transcript_elem['suggestions'].items():
                    suggestions[suggestion] += 1
                best_suggestion, most_votes = max(suggestions.items(), key=itemgetter(1))
                if most_votes > TRANSCRIPT_SUGGESTIONS_NECESSARY:
                    transcript_elem['text'] = best_suggestion
            is_playlist = data['playlist_number'] != 'None'
            transcripts = [lecture['transcript']] if not is_playlist else lecture['transcript']
            playlist_number = int(data['playlist_number']) if is_playlist else 0
            transcript = transcripts[playlist_number]
            transcript_elem = transcript[index]
            if 'suggestions' not in transcript_elem:
                transcript_elem['suggestions'] = dict()
            num_words = len(transcript_elem['text'].split(' '))
            if edit_distance(text, transcript_elem['text']) < (num_words * EDIT_DISTANCE_PER_WORD):
                transcript_elem['suggestions'][user_id] = text
            else:
                print('Suggestion too far off, rejected.')
            push_onto_transcript_if_elected(transcript_elem)
            transcripts[playlist_number] = transcript[:index] + [transcript_elem] + transcript[index+1:]
            return transcripts if is_playlist else transcripts[0]
        db[Lecture.collection].update_one(
            {
                '_id': ObjectId(data['lecture_id'])
            },
            {
                '$set': {
                    'transcript': replace_transcript_elem(lecture, int(data['index']), data['text'], data['user_id'])
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
                user=question['user_id'],
                lecture_id=question['lecture'],
                upvotes =[],
                playlist_number= question['playlist_num'],
                anon = question['anon']
            ),
            db
        ).inserted_id

    @staticmethod
    def edit_question(data, db, is_instructor):
        edit = data['text']
        question_id = data['questionId']
        question = find_one_by_id(question_id, Answer.collection, db)
        if question and (is_instructor or question['user'] == data['user_id']):
            return db[Question.collection].update_one(
                {'_id': ObjectId(data['questionId'])},
                {
                  '$set': {
                    'text': edit,
                  }
                })

    @staticmethod
    def delete_question(data, db, is_instructor):
        question_id = data['question_id']
        question = find_one_by_id(question_id, Answer.collection, db)
        if question and (is_instructor or question['user'] == data['user_id']):
            return db[Question.collection].delete_one(
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
                user=str(user['_id']),
                name=user['name'],
                upvotes=[],
                anon= answer['anon']
            ),
            db
        ).inserted_id

    @staticmethod
    def edit_answer(data, db, is_instructor):
        edit = data['text']
        answer = find_one_by_id(data['answerId'], Answer.collection, db)
        if answer and (is_instructor or answer['user'] == data['user_id']):
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
    def delete_answer(data, db, is_instructor):
        answer_id = data['answer_id']

        answer = find_one_by_id(answer_id, Answer.collection, db)
        if answer and (is_instructor or answer['user'] == data['user_id']):
            return db[Answer.collection].delete_one(
                {'_id': ObjectId(answer_id)}
            )


if __name__ == '__main__':
    client = MongoClient(os.environ.get('MONGODB_URI'))
    db = client[os.environ.get('DATABASE_NAME')]
