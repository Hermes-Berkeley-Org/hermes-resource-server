import requests
from requests.exceptions import RequestException, ConnectionError
from urllib.parse import urlparse, parse_qs

from utils.errors import (
    InvalidLectureLinkError, VideoParseError, NoCourseFoundError, YoutubeError,
    LectureAlreadyExists
)
from utils.youtube_client import YoutubeClient
from utils.db_utils import insert, create_reference, encode_url
from utils.db_utils import Course, Lecture, Video, Transcript

def create_lecture(course_ok_id, db, lecture_title,
                   date, link, youtube_access_token):
    """Executes full lecture creation process, which includes:
    - Handling playlists and single videos
    - Creates and stores a Lecture object in the DB, with a lookup key to a Course
    - Creates and stores Video objects for each video in the YouTube link given,
        with a lookup key to a Lecture and Course
    - Creates and stores Transcript objects for each video,
        with a lookup key to a Course, Lecture, and Video
    """
    course = db[Course.collection].find_one({'course_ok_id': course_ok_id})
    if not course:
        raise NoCourseFoundError(
            'Course associated with OK ID {0} does not exist in the database'
            .format(course_ok_id)
        )
    # check for duplicate title
    lecture_url_name = encode_url(lecture_title)
    if db[Lecture.collection].find_one(
        {
            'lecture_url_name': lecture_url_name,
            'course_ok_id': course_ok_id
        }
    ):
        raise LectureAlreadyExists(
            'A lecture with title {0} in course OK ID {1} has already been created'
            .format(lecture_title, course_ok_id)
        )
    lecture_index = course['num_lectures']

    youtube_url = get_final_youtube_url(link)
    youtube_client = YoutubeClient(youtube_access_token)
    youtube_ids = get_youtube_ids(youtube_url, youtube_client)
    # populate data first, so that on error objects aren't created
    video_titles = []
    videos = []
    transcripts = []
    no_transcript_videos = []
    for video_index, youtube_id in enumerate(youtube_ids):
        title, duration = youtube_client.get_video_metadata(youtube_id)
        videos.append(
            Video(
                title=title,
                duration=duration,
                youtube_id=youtube_id,
                course_ok_id=course_ok_id,
                lecture_url_name=lecture_url_name,
                video_index=video_index,
                num_vitamins=0,
                num_resources=0
            )
        )
        video_titles.append(title)
        try:
            transcript = youtube_client.get_transcript(youtube_id)
            transcripts.append(
                Transcript(
                    transcript=transcript,
                    course_ok_id=course_ok_id,
                    lecture_url_name=lecture_url_name,
                    video_index=video_index
                )
            )
        except YoutubeError as e:
            # support for videos without a transcript
            no_transcript_videos.append(video_index)
    for video in videos:
        insert(video, db)
    for transcript in transcripts:
        insert(transcript, db)
    lecture = Lecture(
        name=lecture_title,
        date=date,
        lecture_url_name=lecture_url_name,
        lecture_index=lecture_index,
        course_ok_id=course_ok_id,
        video_titles=video_titles,
        lecture_piazza_id=""
    )
    insert(lecture, db)
    db[Course.collection].update_one(
        {'course_ok_id': course_ok_id},
        {
            '$set': {
                'num_lectures': course['num_lectures'] + 1
            }
        }
    )
    return {
        'no_transcript_videos': no_transcript_videos
    }, lecture_url_name

def get_final_youtube_url(link):
    """Checks if YouTube link is a valid URL and gets the final redirected
    link (e.g. youtu.be --> youtube.com)
    """
    ses = requests.Session()
    if not link.startswith('http'):
        link = 'http://{0}'.format(link)
    try:
        return ses.head(link, allow_redirects=True).url
    except RequestException or ConnectionError as e:
        raise InvalidLectureLinkError('Lecture YouTube link invalid')

def get_youtube_ids(youtube_url, youtube_client):
    """Retrieves YouTube IDs (youtube.com/watch?v=<youtube_id>) associated
    with a YouTube URL
    """
    metadata = youtube_client.get_link_metadata(youtube_url)
    if metadata.get('playlist_id'):
        return youtube_client.get_playlist_video_ids(metadata['playlist_id'])
    elif metadata.get('video_id'):
        return [metadata['video_id']]
    raise VideoParseError('Cannot get videos from lecture link')
