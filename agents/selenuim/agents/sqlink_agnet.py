import pdb
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import random

from agents.Server.app import file_manager
from agents.Server.db import job_contains_in_db, add_job_to_pending_jobs
from agents.job import Job
from agents.llm import llm_with_tools, PROMPTS
from agents.selenuim.agents.classic_agent import Agent

LINKS = [
    "https://www.sqlink.com/career/student/",
    "https://www.sqlink.com/career/bidbabig-data/",
    "https://www.sqlink.com/career/devops/",
    "https://www.sqlink.com/career/web/",
    "https://www.sqlink.com/career/%D7%A4%D7%99%D7%AA%D7%95%D7%97-%D7%AA%D7%95%D7%9B%D7%A0%D7%94-webmobile/",
    "https://www.sqlink.com/career/hardware/"
    "https://www.sqlink.com/career/ebay-outsource-positions/"]


class SqlinkAgent(Agent):
    def __init__(self, urls=None, name="sqlink_agent"):
        # pdb.set_trace()
        if not urls:
            urls = LINKS
        super().__init__(urls, name)
        self.cv_path = file_manager.resume_pdf_filepath
        self._jobs_from_file = [
            Job.from_json(job) for job in open(self.jobs_filepath, 'r', encoding='utf-8').readlines()
        ]

    def get_jobs(self):
        self.initialize_driver()
        random.shuffle(self.urls)
        for url in self.urls:
            self.process_url(url)
            print(f"Done process url: {url}")

    def process_url(self, url):
        # Step 1: Get the page
        self.driver.get(url)
        time.sleep(5)
        stop = 0
        current_url = url
        processed_jobs = set()
        while stop <= 10:
            # Step 2: scroll to the bottom of the page
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            # Step 3: get all job elements from the specific page
            job_elements = self.get_job_elements()
            # Step 4: process each job element
            current_url = self.driver.current_url
            try:
                for i in range(len(job_elements)):
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    job_elements = self.get_job_elements()
                    job_element = job_elements[i]

                    if job_element in processed_jobs:
                        continue

                    processed_jobs.add(job_element)
                    job_obj = self.process_job_element(job_element, current_url)
                    if job_obj and not job_contains_in_db(job_obj):
                        # Navigating back to the current page.
                        self.driver.get(current_url)
                        time.sleep(5)
                        # Write job to the DB and to a file_manager.py.
                        Job.write_job_to_file(job_obj.to_dict(), self.jobs_filepath)
                        if add_job_to_pending_jobs(job_obj):
                            print("Job added to the DB!")
                            processed_jobs.add(job_element)  # to ignore multiple processing steps
            except Exception as e:
                print(f"Exception from process_url(): {e}")
                return
            # Get the next page button
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            next_page_btn = self.get_next_page_btn()
            if next_page_btn:
                self.driver.execute_script("arguments[0].click();", next_page_btn)
                time.sleep(2)

    def get_next_page_btn(self):
        stop = 0
        while stop <= 5:
            try:
                next_page_btn = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH,
                                                    "//li[contains(@class, 'arrow') and contains(@class, 'arrowLeft') and @id='rightLeft']/a"))
                )
                return next_page_btn
            except Exception as e:
                print(f"In get_next_page_btn(), Error occurred: {e}")
                stop += 1
                time.sleep(2)

    def get_job_elements(self):
        stop = 0
        while stop <= 5:
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located((By.XPATH,
                                                         "//div[contains(@class, 'col10')]//div[contains(@class, 'article') and starts-with(@id, 'id-')]/a"))
                )
                job_elements = self.driver.find_elements(By.XPATH,
                                                         "//div[contains(@class, 'col10')]//div[contains(@class, 'article') and starts-with(@id, 'id-')]")
                return job_elements
            except Exception as e:
                print(f"In get_job_elements(), Error occurred: {e}")
                stop += 1

    def process_job_element(self, job_element, current_url):
        stop = 0
        while stop <= 5:
            try:
                # Scroll to the job element to ensure visibility
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", job_element)
                time.sleep(1)

                job_link_element = job_element.find_element(By.XPATH, "./a")
                job_source = job_link_element.get_attribute("href")
                job_title = job_link_element.text.strip()
                description_element = WebDriverWait(job_element, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//section[contains(@class, 'description')]/p"))
                )
                job_description = description_element.text

                job_obj = Job(
                    job_title=job_title,
                    source=job_source,
                    description=job_description,
                    company='None'
                )

                if job_obj in self._jobs_from_file:
                    self.driver.get(current_url)
                    time.sleep(5)
                    return None

                if self.apply_for_job(job_element):
                    return job_obj
            except Exception as e:
                stop += 1

    def apply_for_job(self, job_element):
        stop = 0
        while stop <= 5:
            try:
                send_cv_button = WebDriverWait(job_element, 10).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//a[@id='sendPopupCVinner' and contains(@class, 'sendPopupCVinner')]"))
                )
                self.driver.execute_script("arguments[0].click();", send_cv_button)
                time.sleep(1)

                popup_element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//div[@id='popupSendCV' and contains(@class, 'popupSendCV')]"))
                )
                if popup_element:
                    file_input = WebDriverWait(popup_element, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//input[@id='fileCV' and @type='file']"))
                    )
                    file_input.send_keys(self.cv_path)
                    time.sleep(1)

                    submit_button = WebDriverWait(popup_element, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//input[@id='sendButton' and @type='submit']"))
                    )
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_button)
                    self.driver.execute_script("arguments[0].click();", submit_button)
                    return True
            except Exception as e:
                stop += 1
                time.sleep(2)
        return False


if __name__ == '__main__':
    sqlink_agent = SqlinkAgent()
    sqlink_agent.get_jobs()
