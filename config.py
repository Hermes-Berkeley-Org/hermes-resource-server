import os

class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY')
    OK_SERVER = os.environ.get('OK_SERVER')
    DEV_TOKEN = os.environ.get('DEV_TOKEN')
    CLIENT_ID = os.environ.get('CLIENT_ID')
    CLIENT_SECRET = os.environ.get('CLIENT_SECRET')
    OK_MODE = os.environ.get('OK_MODE')
    TESTING_OK_ID = os.environ.get('TESTING_OK_ID')
    TRANSCRIPTION_MODE = os.environ.get('TRANSCRIPTION_MODE')
