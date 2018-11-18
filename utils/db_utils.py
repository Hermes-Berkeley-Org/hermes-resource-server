import os
from datetime import datetime

from collections import defaultdict
from operator import itemgetter

from pymongo import MongoClient
from bson.objectid import ObjectId

from utils.app_utils import edit_distance
from urllib.parse import urlparse, parse_qs

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

def create_reference(ref_collection, id):
    return {
        '$ref': ref_collection,
        '$id': id,
        '$db': os.environ.get('DATABASE_NAME')
    }

## Seconds to timestamp helper function
def convert_seconds_to_timestamp(ts):
    return '%d:%02d' % (ts // 60, ts % 60)

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


class Course(DBObject):

    collection = 'Classes'

    def __init__(self, **attr):
        DBObject.__init__(self, **attr)

    @staticmethod
    def add_lecture(course_ok_id, lecture, db):
        def change_date_format(lecture):
            british_date = lecture.get('date')
            date = datetime.strptime(british_date, "%Y-%m-%d")
            lecture.set('date', date.strftime("%m/%d/%y"))
        change_date_format(lecture)
        id = insert(lecture, db).inserted_id
        db[Course.collection].update_one(
            {
              'course_ok_id': course_ok_id
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
    def create_course(display_name, data, db):
        data['display_name'] = display_name
        data['ok_id'] = data.pop('id', None)
        return insert(
            Course(
                lectures=[],
                semester=Course.get_semester(data['offering']),
                students=[],
                **data
            ),
            db
        )

    @staticmethod
    def save_textbook(documents, links, db, class_ok_id):
        db[Course.collection].update_one(
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

class Lecture(DBObject):
    collection = 'Lectures'

    def __init__(self, **attr):
        DBObject.__init__(self, **attr)

class Video(DBObject):
    collection = 'Videos'

    def __init__(self, **attr):
        DBObject.__init__(self, **attr)

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
            is_playlist = lecture['is_playlist']
            transcripts = lecture.get('transcripts') if is_playlist else [lecture.get('transcript')]
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
        if 'transcripts' in lecture or 'transcript' in lecture:
            key = 'transcripts' if lecture.get('is_playlist') else 'transcript'
            db[Lecture.collection].update_one(
                {
                    '_id': ObjectId(data['lecture_id'])
                },
                {
                    '$set': {
                        key: replace_transcript_elem(lecture, int(data['index']), data['text'], data['user_id'])
                    }
                }
            )



class Vitamin(DBObject):

    collection = 'Vitamins'

    def __init__(self, **attr):
        DBObject.__init__(self, **attr)

    @staticmethod
    def add_vitamin(data, db):
        timestamp = convert_seconds_to_timestamp(float(data['seconds']) // 1)
        choices = [data['choice' + str(i)] for i in range(1, 5) if len(data['choice' + str(i)]) > 0]
        return insert(
            Vitamin(
                question = data['question'],
                answer = data['answer'],
                choices = choices,
                seconds = data['seconds'],
                timestamp = timestamp,
                lecture_id = data['lecture_id'],
                playlist_number = data['playlist_number']
            ),
            db
        )

    @staticmethod
    def delete_vitamin(vitamin, db):
        vitamin_id = vitamin['vitamin_id']
        db[Vitamin.collection].delete_one(
            {'_id': ObjectId(vitamin_id)}
        )



class Resource(DBObject):

    collection = 'Resources'

    def __init__(self, **attr):
        DBObject.__init__(self, **attr)

    @staticmethod
    def add_resource(data, db):
        return insert(
            Resource(
                link = data['link'],
                lecture_id = data['lecture_id'],
                playlist_number = data['playlist_number']
            ),
            db
        )

    @staticmethod
    def delete_resource(resource, db):
        resource_id = resource['resource_id']
        db[Resource.collection].delete_one(
            {'_id': ObjectId(resource_id)}
        )

class Transcript(DBObject):

    collection = 'Transcripts'

    def __init__(self, **attr):
        DBObject.__init__(self, **attr)


if __name__ == '__main__':
    client = MongoClient(os.environ.get('MONGODB_URI'))
    db = client[os.environ.get('DATABASE_NAME')]
