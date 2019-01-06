import os, sys
sys.path.append(".")
sys.path.append("..")
sys.path.append("../utils")
sys.path.append("./utils")
import lecture_utils as LectureUtils
from errors import InvalidLectureLinkError
from youtube_client import YoutubeClient

LINKS = [
    'https://www.youtube.com/watch?v=M4hXAZiiIZw&list=PLbh6KXqwIdGAsHxGlkb6sEVv1kXtBHuc2',
    'https://www.youtube.com/watch?v=M4hXAZiiIZw'
]

EXPECTED_ID = 'M4hXAZiiIZw'
EXPECTED_LIST = 'PLbh6KXqwIdGAsHxGlkb6sEVv1kXtBHuc2'
EXPECTED_LIST_IDS = ['M4hXAZiiIZw', 'HIgDFXeGOIg']

ACCESS_TOKEN = "ya29.GluJBq5pEbUHh28g16bNDEXyCBoX0XwcmkaTvJSUffAMqVvaac4EOpRzksJ5VxY0IJGx0m_4zMC2bruVl1ztOK_e3QeXH5_nzzJwPlihdsejrjz1A6ev3m-WMG8j"
youtube_client = YoutubeClient(ACCESS_TOKEN)

def test_get_youtube_id():
	for link in LINKS:
		assert EXPECTED_ID == YoutubeClient.get_youtube_id(link)

def test_get_link_metadata():
	metadata = YoutubeClient.get_link_metadata(LINKS[0])
	assert metadata['playlist_id'] == EXPECTED_LIST
	assert metadata['video_id'] == EXPECTED_ID

	metadata = YoutubeClient.get_link_metadata(LINKS[1])
	assert 'playlist_id' not in metadata
	assert metadata['video_id'] == EXPECTED_ID

def test_create_video_link():
	assert YoutubeClient.create_video_link(EXPECTED_ID, EXPECTED_LIST) == LINKS[0]
	assert YoutubeClient.create_video_link(EXPECTED_ID) == LINKS[1]

def test_get_playlist_video_ids():
	video_ids = youtube_client.get_playlist_video_ids(EXPECTED_LIST)
	assert len(video_ids) == len(EXPECTED_LIST_IDS)
	for i in range(len(video_ids)):
		assert EXPECTED_LIST_IDS[i] == video_ids[i]




if __name__ == '__main__':
	test_get_youtube_id()
	test_get_link_metadata()
	test_create_video_link()
	test_get_playlist_video_ids()
