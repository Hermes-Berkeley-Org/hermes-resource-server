from pymongo import MongoClient
import pysolr

CORE_URL = 'http://localhost:8983/solr/default'

class SearchClient:

    def __init__(self, core_url):
        self.solr = pysolr.Solr(core_url)

    def add_documents(self, docs):
        self.solr.add(docs)
        self.solr.commit()

    def create_transcript_document(self, transcript, lecture_title):
        transcript['_doc'] = transcript.pop('transcript')
        transcript['node_type'] = 'transcript'
        for i, elem in enumerate(transcript['_doc']):
            elem['id'] = f'transcript_element_{i}'
            elem['node_type'] = 'transcript_element'
            elem['course_ok_id'] = transcript['course_ok_id']
            elem['video_index'] = transcript['video_index']
            elem['lecture_url_name'] = transcript['lecture_url_name']
            elem['lecture_title'] = lecture_title
        return transcript

    def add_transcript(self, transcript, lecture_title):
        return self.add_documents([self.create_transcript_document(transcript, lecture_title)])

    def search(self, query, course_ok_ids):
        course_ok_ids_clause = ' OR '.join(
            map(
                lambda course_ok_id: f'course_ok_id:{course_ok_id}',
                course_ok_ids
            )
        )
        text_clause = ' OR '.join(map(lambda word: f'text:{word}', query.split(' ')))
        return list(self.solr.search(
            q=('{!parent which="' + f'({text_clause})' + ' AND ' + f'({course_ok_ids_clause})' + '"}'),
            fl='course_ok_id,video_index,lecture_url_name,lecture_title,begin,end,text',
            limit=50))

    def clear(self):
        self.solr.delete(q='*:*')
        self.solr.commit()

if __name__ == '__main__':
    client = MongoClient('mongodb://heroku_kfcpzsz2:jj5ieg0th7dgdvbl3uvrgmmo9q@ds147518.mlab.com:47518/heroku_kfcpzsz2')
    db = client['heroku_kfcpzsz2']
    search_client = SearchClient(CORE_URL)
    search_client.clear()
    for transcript in db['Transcripts'].find():
        search_client.add_transcript(transcript, 'Playlist Test')
