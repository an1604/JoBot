import logging
import os.path
import pdb
import time

from pymongo import MongoClient
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException
)

from agents.file_manager import file_manager
from agents.selenuim.agents.classic_agent import Agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

LOGON_URLS = [
    "https://b.log-on.com/%d7%97%d7%99%d7%a4%d7%95%d7%a9-%d7%9e%d7%a9%d7%a8%d7%95%d7%aa-%d7%91%d7%94%d7%99%d7%99%d7%98%d7%a7/?areas=789%2C779%2C777%2C773%2C772%2C785%2C305%2C618%2C786%2C568%2C513%2C131%2C126%2C135%2C221%2C139%2C575%2C132%2C155%2C151%2C153%2C154%2C559%2C656%2C565%2C566%2C567%2C530%2C668%2C329&places=99%2C109",
    "https://b.log-on.com/%d7%97%d7%99%d7%a4%d7%95%d7%a9-%d7%9e%d7%a9%d7%a8%d7%95%d7%aa-%d7%91%d7%94%d7%99%d7%99%d7%98%d7%a7/?areas=789%2C779%2C777%2C773%2C772%2C785%2C305%2C616%2C618%2C786%2C571%2C143%2C568%2C666%2C569%2C513%2C131%2C126%2C135%2C425%2C221%2C575%2C132%2C155%2C151%2C153%2C154%2C311%2C561%2C559%2C656%2C551%2C550%2C549%2C565%2C566%2C529%2C530%2C532%2C533%2C668%2C329&places="]


class Logon_agent(Agent):
    def __init__(self, urls=None):
        self.pending_jobs_collection = None
        self.db = None
        self.client = None
        self.initialize_DB_variables_()

        self.jobs_filepath = os.path.join(r'C:\Users\אביב\PycharmProjects\jobFinder\agents\selenuim\json_jobs',
                                          'logon_jobs.json')
        if not urls:
            urls = LOGON_URLS

        super().__init__(urls, "Logon")
        self.driver = None

    def initialize_driver(self):
        stop = 0
        while stop <= 5:
            try:
                logging.info("Initializing WebDriver.")
                self.driver = webdriver.Chrome()
                return
            except WebDriverException as e:
                logging.error(f"WebDriver initialization failed: {e}")
                stop += 1

    def initialize_DB_variables_(self):
        try:
            self.client = MongoClient('mongodb://localhost:27017/')
            self.db = self.client.job_database
            self.pending_jobs_collection = self.db["pending_jobs"]

            self.pending_jobs_collection.create_index(
                [("job_title", 1), ("company", 1), ("description", 1), ("requirements", 1)],
                unique=True
            )
        except Exception as e:
            print(f"Error connecting to MongoDB: {e}")
            return

    def get_jobs(self):
        self.initialize_driver()

        for url in self.urls:
            self.driver.get(url)
            logging.info("Navigated to the URL.")
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            logging.debug("Scrolled to the bottom of the page.")
            stop = 0
            scroll_down_counter = 0
            while stop < 2:
                try:
                    if not self.is_popup_exist():
                        self.load_more_jobs()

                    # Process all the jobs in the current section, and apply the CV foreach job.
                    self.process_al_potential_jobs(url)
                    scroll_down_counter += 1

                    # Getting the same page again, and scroll down to the current state that we need to be on
                    self.driver.get(url)
                    for i in range(scroll_down_counter):
                        self.load_more_jobs()
                    logging.debug("Scrolled to the bottom of the page.")
                except TimeoutException:
                    logging.warning("Timeout while waiting for an element.")
                    if not self.is_popup_exist():
                        logging.info("Stopping the loop due to consecutive failures.")
                        stop += 1
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    else:
                        logging.debug("Retrying after handling popup.")
                except Exception as e:
                    logging.error(f"Unexpected exception occurred: {e}")
                    stop += 1
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        self.driver.quit()

    def is_popup_exist(self):
        try:
            popup_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "poptinDraggableContainer"))
            )
            logging.info("Popup found!")

            close_popup_btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.CLASS_NAME, "close-icon"))
            )
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                                       close_popup_btn)
            close_popup_btn.click()
            logging.info("Popup closed successfully.")
            return True
        except Exception as e:
            logging.error(f"Error interacting with popup: {e}")
            return False

    def load_more_jobs(self):
        # pdb.set_trace()
        stop = 0
        load_more_job_btn_xpath = "//button[contains(@class, 'alm-load-more-btn')]"
        while stop <= 10:
            try:
                load_more_btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, load_more_job_btn_xpath))
                )
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                    load_more_btn)
                load_more_btn.click()
            except:
                stop += 1

    def get_potential_jobs(self):
        stop = 0
        while stop <= 10:
            try:
                potential_jobs = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located((By.CLASS_NAME, 'job'))
                )
                logging.info(f"Found {len(potential_jobs)} available jobs.")
                return potential_jobs
            except:
                stop += 1
        return None

    @staticmethod
    def get_element_by_classname(job, classname, timeout=15):
        try:
            return WebDriverWait(job, timeout).until(
                lambda j: j.find_element(By.CLASS_NAME, classname)
            )
        except:
            return None

    def is_job_exists_in_DB(self, job):
        existing_job = self.pending_jobs_collection.find_one(job)
        existing_job_is_none = existing_job is None
        return not existing_job_is_none

    def process_al_potential_jobs(self, url):
        potential_jobs = self.get_potential_jobs()
        if not potential_jobs:
            print("No potential jobs found.")
            return

        for job_idx in range(len(potential_jobs)):
            try:
                self.driver.get(url)
                potential_jobs = self.get_potential_jobs()
                job = potential_jobs[job_idx]
                job_title_elem = self.get_element_by_classname(job, 'job-name')
                job_title = job_title_elem.text if job_title_elem else "Unknown Title"
                job_info = self.get_job_information(job)

                job_desc_elem = self.get_element_by_classname(job, 'desc')
                job_description = job_desc_elem.text if job_desc_elem else "No description available."

                job_req_elem = self.get_element_by_classname(job, 'list')
                job_requirements = job_req_elem.text if job_req_elem else "No requirements listed."

                # Open the job popup before submitting to the specific job
                if self.open_job_popup():
                    # Placeholder for LLM Analysis (TODO)
                    # response = llm_with_tools.get_llm_response(source=self.driver.current_url, job_desc=job_description)
                    # job_obj = llm_with_tools.execute_function_from_response(response)

                    job_obj = {
                        "source": url,
                        "job_title": job_title,
                        "company": job_info,
                        "description": job_description,
                        "requirements": job_requirements,
                    }

                    if self.execute_submit_cv(job_obj):
                        self.pending_jobs_collection.insert_one(job_obj)
                        print(f"Job successfully saved: {job_title}")
                else:
                    print(f"Failed to submit CV for job: {job_title}")
            except Exception as e:
                print(f"Unexpected error: {e}")

    def execute_submit_cv(self, job_obj):
        if self.send_cv_popup_exist():
            full_name_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//*[@id='fullNameSender']"))
            )
            email_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//*[@id='emailSender']"))
            )

            full_name_input.send_keys('Aviv Nataf')
            email_input.send_keys("nataf12386@gmail.com")

            resume_file_path = file_manager.resume_pdf_filepath
            if self.upload_resume(resume_file_path):
                submit_cv_btn = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//*[@id='job-form']/button"))
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_cv_btn)
                submit_cv_btn.click()
                time.sleep(3)
            return True
        return False

    def send_cv_popup_exist(self):
        stop = 0
        while stop <= 10:
            try:
                apply_cv_container = WebDriverWait(self.driver, 10).until(
                    EC.text_to_be_present_in_element((By.CLASS_NAME, "modal-title"), "שלח/י קו\"ח")
                )
                return True
            except:
                stop += 1
        return False

    def get_job_information(self, job, timeout=15):
        try:
            job_information_obj = self.get_element_by_classname(job, 'info')

            job_information_text = job_information_obj.text if job_information_obj.text else ""

            info = [job_information_text]

            list_items = WebDriverWait(job_information_obj, timeout).until(
                lambda j: j.find_elements(By.TAG_NAME, 'li')
            )
            for li in list_items:
                info.append(li.text)

            return ' '.join(info)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return "Job description not available due to an unexpected error."

    def open_job_popup(self):
        max_attempts = 5
        attempts = 0
        while attempts < max_attempts:
            try:
                try:  # Handle intercepting popup if it exists
                    popup_close_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.ID, "closeXButton"))
                    )
                    popup_close_button.click()
                    print("Popup closed successfully.")
                except TimeoutException:
                    print("No popup found or popup already dismissed.")

                # Then, we can move on to the button management.
                submit_cv_btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'send-your-cv')]"))
                )
                self.driver.execute_script(
                    "window.scrollBy(0, arguments[0].getBoundingClientRect().top - arguments[1]);",
                    submit_cv_btn, 50
                )
                submit_cv_btn.click()
                print("Submit CV button clicked successfully.")
                return True
            except Exception as e:
                print(f"Unexpected error: {e}")
                attempts += 1
        print("Failed to click Submit CV button after multiple attempts.")
        return False

    def upload_resume(self, file_path_):
        stop = 0
        while stop <= 10:
            try:
                file_input_container = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "upload-file"))
                )

                file_input = WebDriverWait(file_input_container, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "input"))
                )
                file_input.send_keys(file_path_)

                print("Resume uploaded successfully.")
                return True
            except Exception as e:
                print(f"Error uploading resume: {e}")
                stop += 1
        return False


if __name__ == '__main__':
    agent = Logon_agent()
    agent.get_jobs()
