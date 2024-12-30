import logging
import pdb
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementClickInterceptedException,
    TimeoutException,
)
import requests
from bs4 import BeautifulSoup

from agents.file_manager import file_manager
from agents.job import Job
from agents.llm import llm_with_tools, PROMPTS
from agents.selenuim.agents.classic_agent import Agent

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

URL = "https://tipalti.com/company/jobs/"


class Tipalti_agent(Agent):
    def __init__(self, urls=None, name="tipalti_jobs"):
        if not urls:
            urls = URL
        super().__init__(urls, name)
        logging.info("Starting the browser and navigating to the URL.")
        self.jobs_filepath = file_manager.get_jobs_filepath(name)

    def get_jobs(self):
        stop = 0
        i = 1
        all_jobs = set()
        while stop <= 3:
            try:
                url = f"https://job-boards.greenhouse.io/embed/job_board?for=tipaltisolutions&page={i}"
                response = requests.get(url, timeout=10)
                if response.status_code != 200:
                    print(f"Failed to fetch page {i}, status code: {response.status_code}")
                    stop += 1
                    continue
                soup = BeautifulSoup(response.content, 'html.parser')
                table = soup.find("table")
                if not table:
                    print(f"No table found on page {i}")
                    stop += 1
                    continue
                rows = table.find_all("tr", class_="job-post")
                for row in rows:
                    # pdb.set_trace()
                    job = self.process_job_element(row)
                    if job:
                        Job.write_job_to_file(job.to_dict(), self.jobs_filepath)
                        all_jobs.add(job)
                print(f"Done processing page {i}, num of jobs: {len(all_jobs)}")
                i += 1
            except Exception as e:
                print(f"Error occurred on page {i}: {e}")
                stop += 1
        print("All jobs:", all_jobs)

    @staticmethod
    def process_job_element(row):
        stop = 0
        while stop <= 3:
            try:
                job_link = row.find("a", href=True)
                job_url = job_link['href'] if job_link else None
                job_title = job_link.find("p", class_="body--medium").text.strip() if job_link else None
                job_location = job_link.find("p", class_="body--metadata").text.strip() if job_link else None
                job = Job(job_title=job_title, location=job_location, source=job_url,
                          company="Tiplati")
                return job
            except:
                stop += 1


if __name__ == '__main__':
    agent = Tipalti_agent()
    jobs = agent.get_jobs()
