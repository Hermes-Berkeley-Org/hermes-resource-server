import requests
from requests.exceptions import RequestException, ConnectionError
from urllib.parse import urlparse, parse_qs

from utils.errors import InvalidLectureLinkError, VideoParseError, NoCourseFoundError

from utils.youtube_client import YoutubeClient

from utils.db_utils import insert, create_reference
from utils.db_utils import Course, Lecture, Video, Transcript

from utils import transcribe_utils as TranscribeUtils

def create_lecture(course_ok_id, db, title, date, link, youtube_access_token):
    """Executes full lecture creation process, which includes:
    - Handling playlists and single videos
    - Creates and stores a Lecture object in the DB, with a lookup key to a Course
    - Creates and stores Video objects for each video in the YouTube link given,
        with a lookup key to a Lecture and Course
    - Creates and stores Transcript objects for each video,
        with a lookup key to a Course, Lecture, and Video
    """
    course = db[Course.collection].find_one({'ok_id': int(course_ok_id)})
    if not course:
        raise NoCourseFoundError(
            'Course associated with OK ID {0} does not exist in the database'
            .format(course_ok_id)
        )
    youtube_url = get_final_youtube_url(link)
    youtube_client = YoutubeClient(youtube_access_token)
    lecture_index = course['num_lectures']
    lecture = Lecture(
        name=title,
        date=date,
        lecture_index=lecture_index,
        course_ok_id=course_ok_id
    )
    insert(lecture, db)
    youtube_ids = get_youtube_ids(youtube_url, youtube_client)
    for video_index, youtube_id in enumerate(youtube_ids):
        title, duration = youtube_client.get_video_metadata(youtube_id)
        video = Video(
            title=title,
            duration=duration,
            youtube_id=youtube_id,
            course_ok_id=course_ok_id,
            lecture_index=lecture_index,
            video_index=video_index
        )
        insert(video, db)
        transcript = youtube_client.get_transcript(youtube_id)
        insert(
            Transcript(
                transcript=transcript,
                course_ok_id=course_ok_id,
                lecture_index=lecture_index,
                video_index=video_index
            ),
            db
        )


def get_final_youtube_url(link):
    ses = requests.Session()
    if not link.startswith('http'):
        link = 'http://{0}'.format(link)
    try:
        return ses.head(link, allow_redirects=True).url
    except RequestException or ConnectionError as e:
        raise InvalidLectureLinkError('Lecture YouTube link invalid')

def get_youtube_ids(youtube_url, youtube_client):
    metadata = youtube_client.get_link_metadata(youtube_url)
    if metadata.get('playlist_id'):
        return youtube_client.get_playlist_video_ids(metadata['playlist_id'])
    elif metadata.get('video_id'):
        return [metadata['video_id']]
    raise VideoParseError('Cannot get videos from lecture link')
