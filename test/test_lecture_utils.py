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
import warnings
from unittest.mock import MagicMock

VALID_LINKS = [
    'https://www.youtube.com/watch?v=M4hXAZiiIZw',
    'youtu.be/M4hXAZiiIZw'
]

EXPECTED_IDS = [
    ['M4hXAZiiIZw'],
    ['M4hXAZiiIZw']
]

INVALID_LINKS = ['asdf']

youtube_client = MagicMock()
youtube_client.get_link_metadata.return_value = {'video_id': 'M4hXAZiiIZw'}

class TestLectureUtils(unittest.TestCase):
    def test_get_final_youtube_url(self):
        warnings.simplefilter("ignore", "ResourceWarning")
        for valid_link in VALID_LINKS:
            url = LectureUtils.get_final_youtube_url(valid_link)
            self.assertIn('https://www.youtube.com/watch?v=M4hXAZiiIZw', url)
        for invalid_link in INVALID_LINKS:
            try:
                url = LectureUtils.get_final_youtube_url(invalid_link)
                self.assertFalse(True) # Should not reach here
            except Exception as e:
                self.assertIsNotNone(e)

    def test_get_youtube_ids(self):
        for valid_link, expected_ids in zip(VALID_LINKS, EXPECTED_IDS):
            url = LectureUtils.get_final_youtube_url(valid_link)
            video_ids = LectureUtils.get_youtube_ids(url, youtube_client)
            self.assertEqual(video_ids, expected_ids)

if __name__ == '__main__':
    unittest.main()
