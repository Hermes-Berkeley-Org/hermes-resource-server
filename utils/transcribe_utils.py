from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

from urllib.parse import parse_qs, urlencode

def transcribe(link):
    driver = webdriver.Chrome()
    driver.get(clean_link(link))
    delay = 3 # seconds
    try:
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
