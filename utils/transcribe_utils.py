from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

from utils.textbook_utils import get_words

from bs4 import BeautifulSoup

from urllib.parse import parse_qs, urlencode, urlparse

import pafy

LENGTH_REQUIRED = 100
THRESHOLD = 0.0

def get_youtube_id(link):
    url = urlparse(link)
    params = parse_qs(url.query)
    return params['v'][0] if 'v' in params else None

def transcribe(link, mode, is_playlist = False,youtube=None, transcription_classifier=None, error_on_failure=False, ):
    try:
        transcription = None
        if mode == 'api':
            transcription = read_from_youtube(link, youtube, is_playlist)
        elif mode == 'scrape':
            transcription = scrape(link)

        preds = None
        if transcription_classifier:
            preds = list(classify(transcription, transcription_classifier))

        return transcription, preds

    except Exception as e:
        if error_on_failure:
            raise e
        else:
            return [], []

def classify(transcription, transcription_classifier):
    curr_text = []
    last = 0
    for i, transcript_elem in enumerate(transcription):
        curr_text += get_words(transcript_elem['text'])
        if len(curr_text) >= LENGTH_REQUIRED and ((i % 2 == 1) or i == len(transcription) - 1):
            link, sim = transcription_classifier.predict(curr_text)
            if sim < THRESHOLD:
                link = None
            yield (link, (last, i // 2)) # note i is now the row number in the transcription table
            last = (i // 2) + 1
            curr_text = []

def read_from_youtube(link, youtube, is_playlist):
    """ Gets the transcript from a youtube video
    :param str link: Either a video id if the initial link was a playlist
    or video link if a video link was passed in
    :param youtube: Youtube API
    :param boolean is_playlist: Tells if link passed in is an id or video link
    based off if it came from a list of ids (playlist) or not
    :return: A list of dictionaries used as the transcript for a video
    """
    if is_playlist:
        video_id = link
    else:
        video_id = get_youtube_id(link)
    def get_caption_id(video_id):
        results = youtube.captions().list(
            part="snippet",
            videoId= video_id
        ).execute()
        for item in results["items"]:
            return item["id"]
    caption_id = get_caption_id(video_id)
    tfmt = "ttml"
    subtitle_html = youtube.captions().download(
        id=caption_id,
        tfmt=tfmt
    ).execute()
    soup = BeautifulSoup(subtitle_html, 'html.parser')
    transcript = []
    for p in soup.find_all('p'):
        transcript.append({
            'begin': p.get('begin'),
            'end': p.get('end'),
            'text': p.text
        })
    return transcript

def get_video_duration(link, is_playlist):
    """Gets the duration of a video
    :param: str link: Either a video id if the initial link was a playlist
    or video link if a video link was passed in
    :param boolean is_playlist: Tells if link passed in is an id or video link
    based off if it came from a list of ids (playlist) or not
    :return: Duration of the video
    """
    if(is_playlist):
        return ([pafy.new(vid).duration for vid in link])
    return pafy.new(link).duration


def scrape(link):
    try:
        driver = webdriver.Chrome()
        driver.get(clean_link(link))
        delay = 3 # seconds
        more_actions_button = WebDriverWait(driver, delay).until(
            EC.presence_of_element_located(
                (By.XPATH, '//button[@aria-label=\'More actions\']')))
        more_actions_button.click()
        open_transcript_button = WebDriverWait(driver, delay).until(
            EC.presence_of_element_located(
                (By.XPATH, '//yt-formatted-string[text()=\'Open transcript\']')))
        open_transcript_button.click()
        transcript_renderer = WebDriverWait(driver, delay).until(
            EC.presence_of_element_located(
                (By.XPATH, '//ytd-transcript-body-renderer')))
        transcript_elements = transcript_renderer.find_elements_by_tag_name("div")
        transcript = []
        for transcript_elem in transcript_elements:
            line = transcript_elem.text.split('\n')
            if len(line) == 2:
                transcript.append({'timestamp': line[0], 'text': line[1]})
        driver.quit()
        return transcript
    except TimeoutException:
        driver.quit()
        return []

def clean_link(link):
    res = link.split('?')
    qs = parse_qs(res[1])
    cleaned_qs = {'v': qs['v'][0]}
    return '{0}?{1}'.format(res[0], urlencode(cleaned_qs))
