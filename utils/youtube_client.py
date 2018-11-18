import requests
from utils.errors import YoutubeError
from urllib.parse import urlparse, parse_qs, urlencode

import google.oauth2.credentials
import googleapiclient.discovery
from googleapiclient.errors import HttpError

from bs4 import BeautifulSoup

class YoutubeClient:

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
        url = urlparse(link)
        params = parse_qs(url.query)
        return params['v'][0] if 'v' in params and len(params['v']) > 0 else None

    @staticmethod
    def get_link_metadata(link):
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
        params = {
            'v': video_id
        }
        if playlist_id:
            params['list'] = playlist_id
        return 'https://www.youtube.com/watch?{0}'.format(urlencode(params))

    def get_playlist_video_ids(self, playlist_id):
        response = self.youtube.playlistItems().list(
            part='contentDetails',
            maxResults=25,
            playlistId=playlist_id
        ).execute()
        items = response.get('items')
        if items:
            return [item['contentDetails']['videoId'] for item in items]

    def get_caption_id(self, video_id):
        results = self.youtube.captions().list(
            part="id",
            videoId=video_id
        ).execute()
        if 'items' in results:
            for item in results["items"]:
                return item["id"]

    def get_transcript(self, video_id):
        try:
            caption_id = self.get_caption_id(video_id)
            if not caption_id:
                raise YoutubeError(
                    'Error retrieving caption track: not a valid video ID')
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
        def convert_youtube_timestamp(duration):
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
