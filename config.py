import os

class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY')
    OK_SERVER = os.environ.get('OK_SERVER')
    DEV_TOKEN = os.environ.get('DEV_TOKEN')
    CLIENT_ID = os.environ.get('CLIENT_ID')
    CLIENT_SECRET = os.environ.get('CLIENT_SECRET')
