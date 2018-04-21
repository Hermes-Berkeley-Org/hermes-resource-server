from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

from bs4 import BeautifulSoup

from urllib.parse import parse_qs, urlencode, urlparse

import pafy

def get_youtube_id(link):
    url = urlparse(link)
    params = parse_qs(url.query)
    return params['v'][0] if 'v' in params else None

def transcribe(link, mode, youtube=None):
    try:
        if mode == 'api':
            return read_from_youtube(link, youtube)
        elif mode == 'scrape':
            return scrape(link)
    except:
        print('Transcribe failed') # @Kian: logger statement here!
        return []

def read_from_youtube(link, youtube):
    video_id = get_youtube_id(link)
    def get_caption_id(video_id):
        results = youtube.captions().list(
            part="snippet",
            videoId=video_id
        ).execute()

        print(results['items'])

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

def get_video_duration(link):
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
