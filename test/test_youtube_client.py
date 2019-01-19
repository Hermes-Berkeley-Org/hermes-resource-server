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
from unittest.mock import MagicMock, call
from utils.errors import YoutubeError

LINKS = [
    'https://www.youtube.com/watch?v=M4hXAZiiIZw&list=PLbh6KXqwIdGAsHxGlkb6sEVv1kXtBHuc2',
    'https://www.youtube.com/watch?v=M4hXAZiiIZw'
]

EXPECTED_ID = 'M4hXAZiiIZw'
EXPECTED_LIST = 'PLbh6KXqwIdGAsHxGlkb6sEVv1kXtBHuc2'
EXPECTED_LIST_IDS = ['M4hXAZiiIZw', 'HIgDFXeGOIg']
CAPTIONED_VIDEO = "5B5tJWrCtoI"

class MockExecute:
    def __init__(self, items):
        self.items = items

    def execute(self):
        return self.items


youtube_client = YoutubeClient(None)
youtube_client.youtube = MagicMock()
youtube_client.youtube.playlistItems.return_value.list.return_value.execute.return_value = {
    'items': [
        {'contentDetails': {'videoId': EXPECTED_LIST_IDS[0]}},
        {'contentDetails': {'videoId': EXPECTED_LIST_IDS[1]}}
    ]
}

def caption_side_effect(part, videoId):
    if videoId == CAPTIONED_VIDEO:
        return MockExecute({
            'items': [{'id': 1}]
        })
    else:
        return MockExecute({})
youtube_client.youtube.captions.return_value.list.side_effect = caption_side_effect

def transcript_side_effect(arg):
    if arg == CAPTIONED_VIDEO:
        return "let's look at a famous example"
    else:
        raise YoutubeError("Error retrieving caption track")
youtube_client.youtube.get_transcript.side_effect = transcript_side_effect

def metadata_side_effect(id, part):
    if id == EXPECTED_ID:
        ret = {'items': [{'kind': 'youtube#video'}]}
        if 'snippet' in part:
            ret['items'][0]['snippet'] = {'title': 'Prancakes'}
        if 'contentDetails' in part:
            ret['items'][0]['contentDetails'] = {'duration': '0H1M2S'}
        return MockExecute(ret)
    else:
        return MockExecute({})

youtube_client.youtube.videos.return_value.list.side_effect = metadata_side_effect

class TestYoutubeClientMethods(unittest.TestCase):
    def test_get_youtube_id(self):
        for link in LINKS:
            self.assertEqual(EXPECTED_ID, YoutubeClient.get_youtube_id(link))

    def test_get_link_metadata(self):
        metadata = YoutubeClient.get_link_metadata(LINKS[0])
        self.assertEqual(metadata['playlist_id'], EXPECTED_LIST)
        self.assertEqual(metadata['video_id'], EXPECTED_ID)

        metadata = YoutubeClient.get_link_metadata(LINKS[1])
        self.assertNotIn('playlist_id', metadata)
        self.assertEqual(metadata['video_id'], EXPECTED_ID)

    def test_create_video_link(self):
        self.assertEqual(YoutubeClient.create_video_link(EXPECTED_ID, EXPECTED_LIST), LINKS[0])
        self.assertEqual(YoutubeClient.create_video_link(EXPECTED_ID), LINKS[1])

    def test_get_playlist_video_ids(self):
        video_ids = youtube_client.get_playlist_video_ids(EXPECTED_LIST)
        self.assertEqual(len(video_ids), len(EXPECTED_LIST_IDS))
        youtube_client.youtube.playlistItems.assert_called_once()
        for i in range(len(video_ids)):
            self.assertEqual(EXPECTED_LIST_IDS[i], video_ids[i])

    def test_get_caption_id(self):
        self.assertIsNone(youtube_client.get_caption_id(EXPECTED_ID))
        self.assertIsNotNone(youtube_client.get_caption_id(CAPTIONED_VIDEO))
        youtube_client.youtube.captions.return_value.list.assert_has_calls([
            call(part="id", videoId=EXPECTED_ID),
            call(part="id", videoId=CAPTIONED_VIDEO)
        ])

    def test_get_transcript(self):
        self.assertRaises(YoutubeError, youtube_client.get_transcript, EXPECTED_ID)
        self.assertEqual(youtube_client.get_transcript(CAPTIONED_VIDEO)[:10], "let's look")

    def test_get_video_metadata(self):
        title, duration = youtube_client.get_video_metadata(EXPECTED_ID)
        self.assertEqual(title, "Prancakes")
        self.assertEqual(duration, "00:01:02")


if __name__ == '__main__':
    unittest.main()
