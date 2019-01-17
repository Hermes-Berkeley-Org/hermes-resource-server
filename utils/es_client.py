from elasticsearch import Elasticsearch

class ESClient:
    count = 0
    def __init__(self, eslink):
        self.eslink = eslink
        self.es = Elasticsearch([self.eslink], verify_certs=False)

    def upload_transcript(self, index, doc_type, body):
        res = self.es.create(index, doc_type, id=ESClient.count, body=body)
        #temporary id generation, need to figure out how we want to do this
        ESClient.count += 1

        return res

    def search_transcripts(self, params):
        res = self.es.search(index="transcripts", doc_type=[], body=params)

        return res
