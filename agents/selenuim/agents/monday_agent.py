import os
import pdb
import time

from selenium.webdriver.support import expected_conditions as EC

from selenium.common.exceptions import NoSuchElementException
from selenium import webdriver
from selenium.webdriver.common.by import By
from deep_translator import GoogleTranslator

import logging

from selenium.webdriver.support.wait import WebDriverWait
import random

from agents.job import Job
from agents.llm import llm_with_tools, PROMPTS
from agents.selenuim.agents.classic_agent import Agent

from dotenv import load_dotenv

load_dotenv()
URL = "https://monday.com/careers?location=telaviv"


class MondayAgent(Agent):
    def __init__(self, urls=None, name="monday_agent"):
        if not urls:
            urls = URL
        super().__init__(urls, name)
        self.jobs = {}

    def get_jobs(self):
        self.initialize_driver()
        self.driver.get(self.urls)
        time.sleep(5)

        self.add_more_jobs()
        stop = 0
        while stop <= 10:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            pdb.set_trace()
            self.process_jobs_in_page()
            if not self.go_to_next_page():
                stop += 1
        return list(set(self.jobs))

    def add_more_jobs(self):
        stop = 0
        while stop < 4:
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//*[@id='main']/section[3]/div[4]/a"))
                )
                load_more = self.driver.find_element(By.XPATH, "//*[@id='main']/section[3]/div[4]/a")
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more)
                load_more.click()
                time.sleep(2)
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

                return True
            except Exception as e:
                print(f"Attempt {stop + 1}: Failed to load more jobs. Error: {e}")
                stop += 1

        return False

    def go_to_next_page(self):
        stop = 0
        while stop < 4:
            try:
                time.sleep(4)
                pagination_list = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//ul[contains(@class, 'pagination-list')]")
                    )
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", pagination_list)

                next_button = pagination_list.find_element(
                    By.XPATH, ".//a[contains(@class, 'directional-progress-link') and contains(@title, 'Next')]"
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                next_button.click()
                return True
            except Exception as e:
                print(f"Attempt {stop + 1}: Failed to click 'Next' button. Error: {e}")
                stop += 1
        return False

    def process_jobs_in_page(self):
        stop = 0
        while stop < 5:
            try:
                self.add_more_jobs()
                table = self.driver.find_element(By.XPATH, "//table[contains(@class, 'table')]")
                job_rows = table.find_elements(By.XPATH, ".//tr")

                for job in job_rows:
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", job)
                        job_element = job.find_element(By.XPATH, ".//td[@class='pos-name']")  # Relative XPath
                        job_title = job_element.find_element(By.XPATH, ".//span[@class='position-name']").text

                        if not job_title in self.jobs.keys() or not "software" in job_title.lower():
                            job_href = job_element.find_element(By.XPATH, ".//a").get_attribute("href")
                            job_desc = job_element.find_element(By.TAG_NAME, "small").text

                            response = llm_with_tools.get_llm_response(
                                PROMPTS.CREATE_JOB_PROMPT.format(source=job_href, job_desc=job_desc)
                            )
                            job_obj = llm_with_tools.execute_function_from_response(response)

                            if job_obj and not job_title in self.jobs.keys():
                                Job.write_job_to_file(job_obj.to_dict(), self.jobs_filepath)
                                print(f"Job '{job_title}' written successfully to {self.jobs_filepath}")
                                self.jobs[job_title] = job_obj
                        self.add_more_jobs()
                    except Exception as e:
                        print(f"Error processing job row: {e}")
                        continue
                stop += 1
            except Exception as e:
                print(f"Error in processing jobs: {e}")
                stop += 1


if __name__ == '__main__':
    agent = MondayAgent()
    jobs = agent.get_jobs()
