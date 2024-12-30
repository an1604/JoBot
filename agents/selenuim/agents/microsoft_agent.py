import pdb
import time
import logging
from agents.job import Job
from agents.llm import llm_with_tools, PROMPTS
from agents.selenuim.agents.classic_agent import Agent
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    WebDriverException,
)

MSFT_URL = "https://jobs.careers.microsoft.com/global/en/search?lc=Israel&exp=Students%20and%20graduates&l=en_us&pg=1&pgSz=20&o=Relevance&flt=true"

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class MSFT_agent(Agent):
    def __init__(self, urls=None, name="MSFT_AGENT"):
        if not urls:
            urls = MSFT_URL
        super().__init__(urls, name)
        self.driver = None
        logging.info(f"Agent {name} initialized with URL: {urls}")
        self.jobs_set = set()

    def get_jobs(self):
        logging.info("Starting job extraction process...")
        try:
            self.driver = webdriver.Chrome()
            self.driver.get(self.urls)
            time.sleep(7)
            logging.info(f"Opened URL: {self.urls}")
        except WebDriverException as e:
            logging.error(f"Failed to load the URL: {e}")
            return []

        jobs = []
        stop = 0
        idx = 0
        while stop <= 10:
            try:
                job_elements = self.driver.find_elements(By.XPATH, "//*[@id='job-search-app']//div[@role='listitem']")
                if job_elements:
                    job_element = job_elements[idx]
                    while not job_element in self.jobs_set:
                        # Checks if the element is already been seen, to process each job once.
                        if not job_element in self.jobs_set:
                            self.jobs_set.add(job_element)
                            idx += 1
                            break
                        else:
                            idx += 1
                            job_element = job_elements[idx]

                    # Keeping the description for future processing before navigating.
                    job_desc = job_element.text
                    sanitized_job_desc = job_desc.encode('ascii', 'replace').decode('ascii')

                    # next, we need to find the button
                    button = job_element.find_element(By.XPATH, ".//button[contains(@class, 'ms-Link')]")
                    if button:
                        button.click()
                        WebDriverWait(self.driver, 10).until(
                            lambda driver: driver.current_url != self.urls
                        )
                        source_url = self.driver.current_url
                        response = llm_with_tools.get_llm_response(
                            PROMPTS.CREATE_JOB_PROMPT.format(source=source_url, job_desc=sanitized_job_desc))

                        job_obj = llm_with_tools.execute_function_from_response(response)
                        if job_obj:
                            jobs.append(job_obj)
                            logging.info("Job successfully processed and added to the list.")

                        self.driver.back()
                        WebDriverWait(self.driver, 10).until(
                            lambda driver: driver.current_url == self.urls
                        )
                        logging.info("Returned to the main page.")
            except Exception as e:
                logging.error(f"Exception occur {e}")
                stop += 1
        pdb.set_trace()
        Job.save_jobs_to_json(jobs, self.jobs_filepath)
        return jobs

    @staticmethod
    def get_btn(job_element):
        try:
            button = job_element.find_element(By.XPATH, ".//button[contains(@class, 'ms-Link')]")
            return button if button else None
        except Exception as e:
            logging.warning(f"Exception occur in get_btn() function: {e}")
            return None


if __name__ == '__main__':
    msft_agent = MSFT_agent()
    jobs = msft_agent.get_jobs()
