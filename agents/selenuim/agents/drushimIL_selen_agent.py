import os
import time

from selenium.webdriver.support import expected_conditions as EC

from selenium import webdriver
from selenium.webdriver.common.by import By
from deep_translator import GoogleTranslator

import logging

from selenium.webdriver.support.wait import WebDriverWait
import random

from agents.job import Job
from agents.llm import llm_with_tools, PROMPTS
from agents.selenuim.agents.classic_agent import Agent
from config import config

MY_MAIL = config.MY_EMAIL
MY_PASSWORD = config.MY_PASSWORD

CYBERSEC_OPP = "https://www.drushim.co.il/jobs/cat30/"
QA_OPP = "https://www.drushim.co.il/jobs/cat24/"
SOFTWARE_OPP = "https://www.drushim.co.il/jobs/cat6/"
GENERAL = "https://www.drushim.co.il/jobs/search/%D7%9E%D7%AA%D7%9B%D7%A0%D7%AA%20%D7%92'%D7%95%D7%A0%D7%99%D7%95%D7%A8/"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class DrushimIL_agent(Agent):
    def __init__(self, url=None):
        if not url:
            url = [CYBERSEC_OPP, QA_OPP, SOFTWARE_OPP, GENERAL]
        super().__init__(url, 'drushimIL_jobs')
        self.translator = GoogleTranslator(source='iw', target='en')
        self.driver = None

    def get_jobs(self):
        random.shuffle(self.urls)
        for url in self.urls:
            jobs = self.scrape_jobs(url)
            print(f"Finished scraping URL: {url}")
        return jobs

    def scrape_jobs(self, url_):
        jobs = set()
        try:
            self.driver = webdriver.Chrome()
            self.driver.get(url_)
            self.driver.implicitly_wait(4)

            logging.info(f"Navigated to {url_} --> from Drushim job search page.")
            if self.handle_login(url_):
                logging.info("Logged in successfully.")

            self.process_load_more_btn()
            stop = 0
            while stop < 2:
                try:
                    job_elements = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_all_elements_located(
                            (By.XPATH, "//div[contains(@class, 'job-item-main') and contains(@class, 'job-hdr')]"))
                    )

                    logging.info(f"Found {len(job_elements)} job elements.")
                    for job_element in job_elements:
                        # Processing and extracting the Job object from the HTML element.
                        job = self.process_job_element(job_element)
                        if job:
                            # Check if the job is already in the DB.
                            from agents.Server.db import job_contains_in_db, add_job_to_pending_jobs

                            if not job_contains_in_db(job):
                                # If not, we apply for this job, and store it in the DB.
                                if self.apply_for_job(job_element):
                                    logging.info(f"Applied for job: {job.job_title}")
                                    add_job_to_pending_jobs(job)  # Adding it to the pending jon collection.
                                else:
                                    logging.info(f"Failed to apply for job: {job.job_title}")
                            # Check for missing type in jobs set
                            if isinstance(jobs, list):
                                jobs = set(jobs)
                            jobs.add(job)
                            Job.write_job_to_file(job.to_dict(), self.jobs_filepath)
                    self.process_load_more_btn()
                    logging.info("Clicked 'Load More' button.")
                except Exception as e:
                    logging.error("Unexpected exception occurred while clicking 'Load More' button.", exc_info=True)
                    stop += 1
            logging.info(f"Scraping completed for URL: {url_}")
        except Exception as e:
            logging.error(f"Error occurred while scraping URL: {url_}", exc_info=True)
        finally:
            self.driver.quit()
        return list(jobs)

    @staticmethod
    def get_source(job_element):
        try:
            a_element = job_element.find_element(By.XPATH, ".//a[contains(@class, 'no-underline-all')]")
            source = a_element.get_attribute("href")
            return source
        except Exception as e:
            print(f"Exception occur {e}")

    def process_job_element(self, job_element):
        translation_job = self.translator.translate(job_element.text)
        source = self.get_source(job_element)
        response = llm_with_tools.get_llm_response(
            PROMPTS.CREATE_JOB_PROMPT.format(source=source, job_desc=translation_job))
        job = llm_with_tools.execute_function_from_response(response)
        if job:
            job.set_job_element(job_element)
            return job
        return None

    def process_load_more_btn(self):
        load_more_btn_xpath = "//button[contains(@class, 'load_jobs_btn') and span[contains(text(), 'משרות נוספות')]]"
        load_more_btn_obj = self.driver.find_element(By.XPATH, load_more_btn_xpath)

        if load_more_btn_obj:
            logging.info("Load More button found.")
            self.driver.execute_script("arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });",
                                       load_more_btn_obj)
            load_more_btn_obj.click()

    def handle_login(self, url):
        stop = 0
        while stop <= 10:
            try:
                login_button = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//button[contains(@class, 'login-btn') and contains(@class, 'v-btn--text')]")
                    )
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", login_button)
                login_button.click()
                logging.info("Clicked login button.")

                login_box = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//*[@id='app']/div[6]")
                    )
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", login_box)

                # Interact with login elements
                email_input = login_box.find_element(By.XPATH, "//*[@id='email-login-field']")
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", email_input)
                email_input.send_keys("nataf12386@gmail.com")

                password_input = login_box.find_element(By.XPATH, "//*[@id='password-login-field']")
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", password_input)
                password_input.send_keys("Avivnata10!")

                login_btn = login_box.find_element(By.ID, "submit-login-btn")
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", login_btn)
                login_btn.click()

                time.sleep(6)

                # Check if logged in successfully
                greetings_xpath = "//*[@id='app']/div[6]/div/div[1]/div[1]/p"
                greetings_element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, greetings_xpath))
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", greetings_element)

                if greetings_element and 'היי' in greetings_element.text:
                    logging.info("Logged in successfully.")
                    return True

                # Refresh the page if login failed
                stop += 1
                self.driver.get(url)

            except Exception as e:
                print(f"Exception occurred: {e}")
                stop += 1
                self.driver.get(url)

        logging.error("Failed to log in after multiple attempts.")
        return False

    def apply_for_job(self, job_element):
        try:
            cv_send_container = WebDriverWait(job_element, 10).until(EC.presence_of_element_located(
                (By.ID, "cv-send-btn")
            ))
            self.driver.implicitly_wait(5)

            if cv_send_container:
                send_cv_btn = WebDriverWait(cv_send_container, 10).until(EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(., 'שלח/י קורות חיים')]")
                ))
                self.driver.execute_script("arguments[0].scrollIntoView(true);", send_cv_btn)
                self.driver.execute_script("arguments[0].click();", send_cv_btn)

                self.ensure_logged_in()  # Ensuring we logged into the account, to make the apply action
                logging.info("Clicked 'CV Send' button.")

                # Find and click on the submit cv button, to complete the process.
                submit_apply_btn = WebDriverWait(job_element, 10).until(EC.presence_of_element_located(
                    (By.XPATH,
                     "//button[@type='button' and contains(@class, 'v-btn') "
                     "and contains(@class, 'v-btn--contained') and contains(@class, 'v-btn--rounded') "
                     "and @id='submitApply']")))

                self.driver.execute_script("arguments[0].scrollIntoView(true);", submit_apply_btn)
                self.driver.execute_script("arguments[0].click();", submit_apply_btn)

                time.sleep(8)
                if self.close_job_popup():  # Trying to close the popup for the job, and move on to the next job element.
                    return True
                return False
        except Exception as e:
            print(f"Exception occur {e}")
            return False

    def close_job_popup(self):
        time.sleep(4)
        stop = 0
        while stop <= 10:
            try:
                close_btn_container = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(
                        (By.XPATH,
                         "//div[contains(@class, 'flex') and contains(@class, 'x-close') and contains(@class, 'pc-view')]")
                    )
                )
                close_button = close_btn_container.find_element(By.XPATH,
                                                                ".//button[@type='button' and contains(@class, 'v-btn')]")
                close_button.click()
                print("Popup closed successfully.")
                return True
            except Exception as e:
                print(f"Attempt {stop + 1}: No popup to close or error occurred: {e}")
                stop += 1
        print("Failed to close popup after 10 attempts.")
        return False

    def ensure_logged_in(self):
        try:
            login_dialog_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[contains(@class, 'v-dialog') and contains(@class, 'v-dialog--active')]")
                )
            )

            if login_dialog_element:
                email_input = WebDriverWait(login_dialog_element, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//*[@id='email-login-field']"))
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", email_input)
                email_input.send_keys(MY_MAIL)

                password_input = WebDriverWait(login_dialog_element, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//*[@id='password-login-field']"))
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", password_input)
                password_input.send_keys(MY_PASSWORD)

                login_btn = WebDriverWait(login_dialog_element, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//*[@id='submit-login-btn']"))
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", login_btn)
                login_btn.click()

                return True
            else:
                print("Login dialog not visible.")
                return False
        except Exception as e:
            print(f"Failed to interact with login elements: {e}")
            return False


if __name__ == '__main__':
    try:
        agent = DrushimIL_agent()
        agent.get_jobs()
    except Exception as e:
        logging.error("Unexpected error in main execution.", exc_info=True)
