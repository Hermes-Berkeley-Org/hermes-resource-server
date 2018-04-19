import re

from bs4 import BeautifulSoup
from gensim.models import Doc2Vec
from gensim.models.doc2vec import TaggedDocument
import requests
import nltk
from nltk.corpus import stopwords
import numpy as np

sw = set(stopwords.words('english'))
BASE_URL = 'http://composingprograms.com/'

class TranscriptionClassifier:

    model_name = 'textbook.doc2vec'

    def __init__(self, retrain=False):
        self.generate_documents()
        loaded = not retrain and self.load_model()
        if not loaded:
            self.model = Doc2Vec(alpha=.025, min_alpha=.025, min_count=1)
            self.train()

    def load_model(self):
        try:
            self.model = Doc2Vec.load(TranscriptionClassifier.model_name)
            return True
        except FileNotFoundError as e:
            return False

    def train(self):
        it = generate_tagged_documents(self.documents, self.links)
        self.model.build_vocab(it)
        self.model.train(it, total_examples=self.model.corpus_count, epochs=self.model.epochs)
        self.model.save(TranscriptionClassifier.model_name)

    def generate_documents(self):
        homesoup = BeautifulSoup(requests.get(BASE_URL).text, 'html.parser')
        self.pages = [a for a in homesoup.find_all('a') if './pages/' in a['href']] # generalize later
        self.documents = []
        self.links = []
        self.download_documents()

    def download_documents(self):
        documents = []
        links = []
        for i, page in enumerate(self.pages):
            running = True
            while running:
                try:
                    link = get_link(page)
                    new_documents, new_links = scrape(link)
                    self.documents.extend(new_documents)
                    self.links.extend(new_links)
                    running = False
                except:
                    print('Trying page', i, 'again')

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


def cosine_similarity(v1, v2):
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

def get_link(page):
    return page['href'].replace('./', BASE_URL)

def generate_tagged_documents(documents, links):
    return iter([TaggedDocument(get_words(document), [link]) for link, document in zip(links, documents)])

def get_words(document):
    return [word for word in re.split('\s+', re.sub('[^a-zA-Z]', ' ', document)) if word not in sw]

def scrape(page_url):
    soup = BeautifulSoup(requests.get(page_url).text, 'html.parser')
    documents = []
    links = []
    for div in soup.find_all('div', {'class': 'section'}):
        documents.append(div.get_text())
        links.append('{0}#{1}'.format(page_url, div['id']))
    return documents, links

if __name__ == '__main__':
    ts = TranscriptionClassifier()
    print(ts.predict('hello my name is what'.split(' ')))
