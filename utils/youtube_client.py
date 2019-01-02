import requests
from utils.errors import YoutubeError
from urllib.parse import urlparse, parse_qs, urlencode

import google.oauth2.credentials
import googleapiclient.discovery
from googleapiclient.errors import HttpError

from bs4 import BeautifulSoup

class YoutubeClient:

    # TODO AY: some way to test this functionality in test_youtube_client.py

    def __init__(self, access_token):
        credentials = google.oauth2.credentials.Credentials(
            token=access_token
        )
        self.youtube = googleapiclient.discovery.build(
            'youtube',
            'v3',
            credentials=credentials,
            cache_discovery=False
        )

    @staticmethod
    def get_youtube_id(link):
        """Gets YouTube ID from a YouTube URL
        >>> YoutubeClient.get_youtube_id('http://youtube.com/watch?v=asdf')
        asdf
        """
        url = urlparse(link)
        params = parse_qs(url.query)
        return params['v'][0] if 'v' in params and len(params['v']) > 0 else None

    @staticmethod
    def get_link_metadata(link):
        """Gets relevant information from a YouTube URL:
        Returns:
        {
            "playlist_id": <playlist_id>
            "video_id": <video_id>
        }
        """
        url_components = urlparse(link)
        if url_components and 'youtube' in url_components.netloc:
            url_params = parse_qs(url_components.query)
            metadata = {}

            if 'list' in url_params and len(url_params['list']) > 0:
                metadata['playlist_id'] = url_params['list'][0]

            if 'v' in url_params and len(url_params['v']) > 0:
                metadata['video_id'] = url_params['v'][0]

            if metadata:
                return metadata
        raise YoutubeError('URL is not a valid YouTube link')

    @staticmethod
    def create_video_link(video_id, playlist_id=None):
        """Creates a YouTube link from a video_id and/or playlist_id
        >>> YoutubeClient.create_video_link('asdf', 'ghjk')
        https://www.youtube.com/watch?v=asdf&list=ghjk
        """
        params = {
            'v': video_id
        }
        if playlist_id:
            params['list'] = playlist_id
        return 'https://www.youtube.com/watch?{0}'.format(urlencode(params))

    def get_playlist_video_ids(self, playlist_id):
        """Gets all YouTube video IDs associated with a playlist ID"""
        response = self.youtube.playlistItems().list(
            part='contentDetails',
            maxResults=25,
            playlistId=playlist_id
        ).execute()
        items = response.get('items')
        if items:
            return [item['contentDetails']['videoId'] for item in items]

    def get_caption_id(self, video_id):
        """Retrieves caption ID associated with a video_id, or returns None
        if no caption track exists"""
        results = self.youtube.captions().list(
            part="id",
            videoId=video_id
        ).execute()
        if 'items' in results:
            for item in results["items"]:
                return item["id"]

    def get_transcript(self, video_id):
        """Retrieves transcript from a video_id by first getting the caption
        track associated, then downloading the caption track and parsing it from
        HTML into JSON"""
        try:
            caption_id = self.get_caption_id(video_id)
            if not caption_id:
                raise YoutubeError(
                    'Error retrieving caption track')
            subtitle_html = self.youtube.captions().download(
                id=caption_id,
                tfmt='ttml'
            ).execute()
            soup = BeautifulSoup(subtitle_html, 'html.parser')
            transcript = []
            for p in soup.find_all('p'):
                transcript.append({
                    'begin': p.get('begin'),
                    'end': p.get('end'),
                    'text': p.text,
                    'suggestions': {}
                })
            return transcript
        except HttpError as e:
            raise YoutubeError('Error retrieving the caption track')

    def get_video_metadata(self, youtube_id):
        """Returns the title and duration of a video"""
        def convert_youtube_timestamp(duration):
            """Converts a youtube duration into a readable duration:
            >>> convert_youtube_timestamp('1H4M5S')
            '01:04:05'
            """
            if duration:
                time_content = duration[2:]
                hours, minutes, seconds = 0, 0, 0
                i = 0
                while i < len(time_content):
                    value = ''
                    while time_content[i].isdigit():
                        value += time_content[i]
                        i += 1
                    label = time_content[i]
                    if label == 'H':
                        hours = int(value)
                    elif label == 'M':
                        minutes = int(value)
                    elif label == 'S':
                        seconds = int(value)
                    i += 1
                return '%02d:%02d:%02d' % (hours, minutes, seconds)
        youtube_resp = self.youtube.videos().list(
            id=youtube_id,
            part='snippet,contentDetails'
        ).execute()
        results = youtube_resp.get('items') or []
        if len(results) > 0:
            youtube_info = results[0]
            if youtube_info['kind'] == 'youtube#video':
                if 'snippet' in youtube_info and 'contentDetails' in youtube_info:
                    return youtube_info['snippet'].get('title'), \
                        convert_youtube_timestamp(
                            youtube_info['contentDetails'].get('duration')
                        )
