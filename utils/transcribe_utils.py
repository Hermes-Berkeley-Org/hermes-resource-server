from selenium import webdriver

def transcribe(lecture_id, link, db):
    driver = webdriver.Chrome()
    driver.get(link)
    more_actions_button = driver.find_element_by_xpath('//button[@aria-label="More actions"]')
    more_actions_button.click()
    open_transcript_button = driver.find_element_by_xpath('//yt-formatted-string[text()="Open transcript"]')
    open_transcript_button.click()
    transcript_elements = driver.find_elements_by_xpath('//ytd-transcript-body-renderer/div')
    transcript = []
    for transcript_elem in transcript_elements:
        line = transcript_elem.text.split('\n')
        transcript.append({'timestamp': line[0], 'text': line[1]})
    return transcript
