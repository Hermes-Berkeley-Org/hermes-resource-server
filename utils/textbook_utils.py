import re
import os

from bs4 import BeautifulSoup
from gensim.models import Doc2Vec
from gensim.models.doc2vec import TaggedDocument
from utils.db_utils import Class
import requests
import nltk
from nltk.corpus import stopwords
import numpy as np

sw = set(stopwords.words('english'))
MODEL_DIR = 'transcription_models'

class TranscriptionClassifier:

    model_name = 'textbook.doc2vec'

    def __init__(self, base_url, db, class_ok_id, retrain=True):
        self.base_url = base_url
        self.class_ok_id = class_ok_id
        self.documents = []
        self.links = []
        self.generate_documents(db)
        Class.save_textbook(self.documents, self.links, db, self.class_ok_id)
        loaded = not retrain and self.load_model()
        if not loaded:
            self.model = Doc2Vec(alpha=.025, min_alpha=.025, min_count=1)
            self.train()

    def load_model(self):
        file_name = '{0}/{1}'.format(MODEL_DIR, self.model_name)
        if os.path.exists(file_name):
            self.model = Doc2Vec.load(file_name)
            return True
        else:
            return False

    def generate_documents(self, db):
        raise NotImplementedError

    def train(self):
        it = generate_tagged_documents(self.documents, self.links)
        self.model.build_vocab(it)
        self.model.train(it, total_examples=self.model.corpus_count, epochs=self.model.epochs)
        self.model.save('{0}/{1}'.format(MODEL_DIR, self.model_name))

    def predict(self, words):
        new_doc_vector = self.model.infer_vector(words)
        arg_best, best = -1, -1

        try:
            for i, vector in enumerate(self.model.docvecs):
                sim = cosine_similarity(vector, new_doc_vector)
                if sim > best:
                    arg_best, best = i, sim
        except:
            pass
        return (self.links[arg_best], best)


class CS61ATranscriptionClassifier(TranscriptionClassifier):

    def __init__(self, db, class_ok_id, retrain=False):
        self.model_name = 'cs61a.doc2vec'
        super().__init__('http://composingprograms.com/', db, class_ok_id)

    def generate_documents(self, db):
        homesoup = BeautifulSoup(requests.get(self.base_url).text, 'html.parser')
        self.pages = [a for a in homesoup.find_all('a') if './pages/' in a['href']] # generalize later
        self.download_documents(db)

    def download_documents(self, db):
        cls = db[Class.collection].find_one({'ok_id': self.class_ok_id})
        if cls and 'documents' in cls and 'links' in cls:
            self.documents = cls['documents']
            self.links = cls['links']
        else:
            for i, page in enumerate(self.pages):
                running = True
                while running:
                    try:
                        link = get_link(page, self.base_url)
                        new_documents, new_links = self.scrape(link)
                        self.documents.extend(new_documents)
                        self.links.extend(new_links)
                        running = False
                    except:
                        print('Trying page', i, 'again')

    def scrape(self, page_url):
        soup = BeautifulSoup(requests.get(page_url).text, 'html.parser')
        documents = []
        links = []
        for div in soup.find_all('div', {'class': 'section'}):
            documents.append(div.get_text())
            links.append('{0}#{1}'.format(page_url, div['id']))
        return documents, links


def cosine_similarity(v1, v2):
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

def get_link(page, base_url):
    return page['href'].replace('./', base_url)

def generate_tagged_documents(documents, links):
    return [TaggedDocument(get_words(document), [link]) for link, document in zip(links, documents)]

def get_words(document):
    return [word for word in re.split('\s+', re.sub('[^a-zA-Z]', ' ', document)) if word not in sw]

CLASSIFIERS = {
    'CS 61A': CS61ATranscriptionClassifier
}

# if __name__ == '__main__':
#     ts = CS61ATranscriptionClassifier()
#     print(ts.predict('lists are mutable data types'.split(' ')))
