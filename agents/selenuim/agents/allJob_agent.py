import logging
import pdb
import threading
import time

from langchain_community.llms import Ollama
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    WebDriverException, ElementNotInteractableException
)

from agents.Server.db import job_contains_in_db, add_job_to_job_collection
from agents.file_manager import file_manager
from agents.job import Job
from agents.selenuim.agents.classic_agent import Agent


class AllJobsAgent(Agent):
    def __init__(self, urls=None, name="allJobs_agent"):
        self.prompt_to_llm = """
                Extract the company name from this job title: {job_title}, without providing any intro or
                outro to your answer, just sent the company name.
                """
        self.llm = Ollama(model='llama3')

        self.stop = False
        self.check_for_popup = False
        self.time_slice_handler_thread = None
        self.popup_handler_thread = None
        self.popup_handler_event = threading.Event()
        self.popup_handler_event.set()  # Allowing the main thread to run first

        self.login_url = "https://www.alljobs.co.il/access.aspx?Camefrom=top_bar_login"
        self.driver = None
        if not urls:
            urls = [
                'https://www.alljobs.co.il/SearchResultsGuest.aspx?page=1&position=235&type=4&source=&duration=0&exc=&region=',
                'https://www.alljobs.co.il/SearchResultsGuest.aspx?page=1&position=1998&type=4&source=&duration=0&exc=&region=',
                'https://www.alljobs.co.il/SearchResultsGuest.aspx?page=1&position=1541&type=4&source=&duration=0&exc=&region=',

            ]
        super().__init__(urls, name)

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

    def get_jobs(self):
        # self.run_popup_handler()  # Running the popup handler in a different thread
        for url in self.urls:
            self.initialize_driver()
            self.process_url(url)

    def run_popup_handler(self):
        def popup_handler_job():
            time.sleep(15)  # Wait 15 seconds before start running
            while True:
                self.popup_handler_event.wait()
                print("PopUp handler called, stopping the main thread until finished.")
                self.handle_popup()
                print("Done, back to the main thread.")
                self.popup_handler_event.set()

        self.popup_handler_thread = threading.Thread(target=popup_handler_job, daemon=True).start()

    def process_url(self, url):
        # self.handle_login()
        self.driver.get(url)

        success_counter = 0
        stop = 0
        while stop <= 10:
            try:
                time.sleep(10)
                paging_div = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'jobs-paging')]"))
                )
                visible_comps, success = self.process_visible_jobs(url)
                if success:
                    success_counter += 1
                    pdb.set_trace()
                    if not self.move_to_next_page(paging_div):
                        break

                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            except Exception as e:
                self.handle_popup(url)
                stop += 1
                continue

    def apply_for_job(self):
        # Step 1: wait for the popup to appear
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "job-sendcv-form"))
        )
        send_cv_form = self.driver.find_element(By.ID, "job-sendcv-form")

        # Step 2: apply the cv from the device
        if self.upload_cv(send_cv_form):
            # Step 3: locate the send cv button and press it
            if self.find_and_press_applyCV_btn(send_cv_form):
                # Last step: locate the close btn to close the popup
                close_btn = send_cv_form.find_element(By.XPATH, ".//div[@ng-click='CloseSendCV()']")
                self.driver.execute_script("arguments[0].scrollIntoView();", close_btn)
                self.driver.execute_script("arguments[0].click();", close_btn)
                # close_btn.click()
                time.sleep(4)
                return True
        return False

    def process_visible_jobs(self, url):
        self.handle_popup(url)
        stop = 0
        while stop <= 7:
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located((By.XPATH, "//div[starts-with(@id, 'job-box-container')]"))
                )
                visible_jobs = set()
                all_job_cards = self.driver.find_elements(By.XPATH, "//div[starts-with(@id, 'job-box-container')]")
                prev_job_card = None
                for i in range(len(all_job_cards)):
                    job_card = all_job_cards[i]
                    if prev_job_card and prev_job_card.text == job_card.text:
                        continue

                    time.sleep(3)
                    # pdb.set_trace()
                    job_obj = self.process_job_card(job_card, url)
                    if not job_obj in visible_jobs and not job_contains_in_db(job_obj):
                        visible_jobs.add(job_obj)
                        Job.write_job_to_file(job_obj.to_dict(), self.jobs_filepath)
                        add_job_to_job_collection(job_obj)
                        prev_job_card = job_card
                return visible_jobs, True
            except Exception as e:
                # self.popup_handler_event.clear()
                # self.wait_for_popup_handler()
                self.handle_popup(url)
                stop += 1
            return None, False

    def process_job_card(self, job_card, url):
        stop = 0
        while stop <= 5:
            try:
                self.handle_popup(url)
                # Scroll to the current job card
                self.driver.execute_script("arguments[0].scrollIntoView();", job_card)
                time.sleep(2)
                a_container = self.driver.find_element(By.XPATH,
                                                       "//div[contains(@class, 'job-content-top-title-highlight')]")
                a_tag = a_container.find_element(By.XPATH, ".//a")

                job_url = a_tag.get_attribute("href")
                job_title = a_tag.text
                company_name = self.llm.invoke(self.prompt_to_llm.format(job_title=job_title))

                job_location_element = WebDriverWait(job_card, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'job-content-top-location')]/a"))
                )
                job_description_element = WebDriverWait(job_card, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'job-content-top-desc')]"))
                )

                job_obj = Job(job_title=job_title, source=job_url, description=job_description_element.text,
                              company=company_name, location=job_location_element.text)

                return job_obj
            except Exception as e:
                self.handle_popup(url)
                stop += 1
            return None

    def wait_for_popup_handler(self):
        while not self.popup_handler_event.is_set():
            time.sleep(5)
        self.popup_handler_event.set()

    def handle_popup(self, url):
        stop = 0
        while stop <= 5:
            try:
                close_button = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//div[@id='cboxClose']"))
                )
                print("Popup detected.")
                try:
                    close_button.click()
                    print("Popup closed successfully.")
                    return
                except ElementNotInteractableException:
                    print("Element is not interactable. Retrying...")
                    return
            except Exception as e:
                print(f"An unexpected exception occurred: {e}")
                stop += 1
                if stop == 5:
                    self.driver.get(url)
                    stop -= 2

    def handle_login(self):
        self.driver.get(self.login_url)
        self.driver.implicitly_wait(10)
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//*[@id='inputEmail']"))
            )
            email_input = self.driver.find_element(By.XPATH, "//*[@id='inputEmail']")
            password_input = self.driver.find_element(By.XPATH, "//*[@id='inputPassword']")

            email_input.send_keys("nataf12386@gmail.com")
            password_input.send_keys("Avivnata10!")

            login_btn = self.driver.find_element(By.XPATH, "//*[@id='btn-submit-form']")
            self.driver.execute_script("arguments[0].scrollIntoView();", login_btn)
            self.driver.execute_script("arguments[0].click();", login_btn)
            return True
        except Exception as e:
            print(f"Failed in login --> {e}")
            return False

    @staticmethod
    def upload_cv(send_cv_form, cv_path=r'"C:\Users\אביב\Desktop\aviv_nataf_resume_13_last.pdf"'):
        stop = 0
        while stop <= 5:
            try:
                WebDriverWait(send_cv_form, 10).until(
                    EC.presence_of_element_located((By.ID, "AjaxFile_form"))
                )

                file_input = send_cv_form.find_element(By.ID, "txtFileNew")
                file_input.send_keys(cv_path)
                print(f"CV uploaded successfully from: {cv_path}")
                return True
            except Exception as e:
                print(f"Error uploading CV: {e}")
                stop += 1
        return False

    def find_and_press_applyCV_btn(self, send_cv_form):
        stop = 0
        while stop <= 5:
            try:
                WebDriverWait(send_cv_form, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "job-button-send"))
                )
                apply_cv_btn = send_cv_form.find_element(By.CLASS_NAME, "job-button-send")
                self.driver.execute_script("arguments[0].scrollIntoView();", apply_cv_btn)
                self.driver.execute_script("arguments[0].click();", apply_cv_btn)
                # apply_cv_btn.click()
                print("Apply CV button clicked successfully.")
                return True
            except Exception as e:
                stop += 1
        return False

    def move_to_next_page(self, paging_div):
        stop_call = 0
        while stop_call <= 5:
            try:
                self.driver.execute_script("arguments[0].scrollIntoView();", paging_div)
                next_page_link = WebDriverWait(paging_div, 10).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//div[contains(@class, 'jobs-paging-next')]/a"))
                )
                self.driver.execute_script("arguments[0].click();", next_page_link)
                return True
            except Exception as e:
                stop_call += 1
                continue
        # If we aren't pressed on the next page button, we can move on to the next URL.
        return False


if __name__ == '__main__':
    agent = AllJobsAgent()
    agent.get_jobs()
