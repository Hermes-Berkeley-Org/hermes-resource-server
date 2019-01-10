from elasticsearch import Elasticsearch

class ESClient:

    def __init__(self, eslink):
        self.eslink = eslink
        self.es = Elasticsearch([self.eslink], verify_certs=False)

    def upload_transcript(self, index, doc_type, id, body):
        res = self.es.create(index, doc_type, id, body)

        return res

    def search_transcripts(self, params):
        res = self.es.search(index="", doc_type=[], body=params)
        return res
