import os, sys
sys.path.append(".")
sys.path.append("..")
sys.path.append("../utils")
sys.path.append("./utils")
import lecture_utils as LectureUtils
# from errors import InvalidLectureLinkError
from urllib.error import URLError
from youtube_client import YoutubeClient

VALID_LINKS = [
    'https://www.youtube.com/watch?v=M4hXAZiiIZw',
    'youtu.be/M4hXAZiiIZw'
]

EXPECTED_IDS = [
    ['M4hXAZiiIZw'],
    ['M4hXAZiiIZw']
]

INVALID_LINKS = ['asdf']

ACCESS_TOKEN = 'ya29.GltnBl_0TZT5AH_ZTFQt9XNRW3Qthq1KeMAbEqX4PrkAywM_bHleU1CObe7E0LcsBM_O5cOwG7e154aJk5ZqUDrE4Bbvqk5Fib-LaDLpxcMeSh6BxMmG1UKgLLVY'
youtube_client = YoutubeClient(ACCESS_TOKEN)
# TODO AY: Mock this for tests: see https://docs.python.org/3/library/unittest.mock.html

def test_get_final_youtube_url():
    for valid_link in VALID_LINKS:
        url = LectureUtils.get_final_youtube_url(valid_link)
        assert 'https://www.youtube.com/watch?v=M4hXAZiiIZw' in url
    for invalid_link in INVALID_LINKS:
        try:
            url = LectureUtils.get_final_youtube_url(invalid_link)
            assert False
        except URLError as e:
            assert e is not None

def test_get_youtube_ids():
    for valid_link, expected_ids in zip(VALID_LINKS, EXPECTED_IDS):
        url = LectureUtils.get_final_youtube_url(valid_link)
        video_ids = LectureUtils.get_youtube_ids(url, youtube_client)
        assert video_ids == expected_ids

if __name__ == '__main__':
    test_get_final_youtube_url()
    test_get_youtube_ids()
