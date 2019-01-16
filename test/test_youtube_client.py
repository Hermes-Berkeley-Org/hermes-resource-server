import os, sys
sys.path.append(".")
sys.path.append("..")
sys.path.append("../utils")
sys.path.append("./utils")
import lecture_utils as LectureUtils
from errors import InvalidLectureLinkError
from urllib.error import URLError
from youtube_client import YoutubeClient
import unittest
from unittest.mock import MagicMock

LINKS = [
    'https://www.youtube.com/watch?v=M4hXAZiiIZw&list=PLbh6KXqwIdGAsHxGlkb6sEVv1kXtBHuc2',
    'https://www.youtube.com/watch?v=M4hXAZiiIZw'
]

EXPECTED_ID = 'M4hXAZiiIZw'
EXPECTED_LIST = 'PLbh6KXqwIdGAsHxGlkb6sEVv1kXtBHuc2'
EXPECTED_LIST_IDS = ['M4hXAZiiIZw', 'HIgDFXeGOIg']

youtube_client = MagicMock()
youtube_client.get_playlist_video_ids.return_value = EXPECTED_LIST_IDS

class TestYoutubeClientMethods(unittest.TestCase):
	def test_get_youtube_id(self):
		for link in LINKS:
			assert EXPECTED_ID == YoutubeClient.get_youtube_id(link)

	def test_get_link_metadata(self):
		metadata = YoutubeClient.get_link_metadata(LINKS[0])
		assert metadata['playlist_id'] == EXPECTED_LIST
		assert metadata['video_id'] == EXPECTED_ID

		metadata = YoutubeClient.get_link_metadata(LINKS[1])
		assert 'playlist_id' not in metadata
		assert metadata['video_id'] == EXPECTED_ID

	def test_create_video_link(self):
		assert YoutubeClient.create_video_link(EXPECTED_ID, EXPECTED_LIST) == LINKS[0]
		assert YoutubeClient.create_video_link(EXPECTED_ID) == LINKS[1]

	def test_get_playlist_video_ids(self):
		video_ids = youtube_client.get_playlist_video_ids(EXPECTED_LIST)
		self.assertEqual(len(video_ids), len(EXPECTED_LIST_IDS))
		youtube_client.get_playlist_video_ids.assert_called_once_with(EXPECTED_LIST)
		for i in range(len(video_ids)):
			self.assertEqual(EXPECTED_LIST_IDS[i], video_ids[i])




if __name__ == '__main__':
	unittest.main()
	# test_get_youtube_id()
	# test_get_link_metadata()
	# test_create_video_link()
	# test_get_playlist_video_ids()
	# youtube_client.get_transcript(EXPECTED_ID)
