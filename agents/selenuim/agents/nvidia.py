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

from agents.file_manager import file_manager
from agents.job import Job
from agents.llm import llm_with_tools, PROMPTS
from agents.selenuim.agents.classic_agent import Agent

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class Nvidia_agent(Agent):
    def __init__(self, urls=None, name="nvidia_jobs"):
        if not urls:
            urls = [
                "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/jobs/details/Software-Engineer_JR1991613?jobFamilyGroup=0c40f6bd1d8f10ae43ffbd1459047e84&jobFamilyGroup=0c40f6bd1d8f10ae43ffaefd46dc7e78&jobFamilyGroup=0c40f6bd1d8f10ae43ffc3fc7d8c7e8a&timeType=5509c0b5959810ac0029943377d47364&locationHierarchy1=2fcb99c455831013ea52bbe14cf9326c",
                "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite?locationHierarchy2=0c3f5f117e9a0101f63dc469c3010000&locationHierarchy2=0c3f5f117e9a0101f6422f0fe79d0000&locationHierarchy1=2fcb99c455831013ea52bbe14cf9326c"]
        super().__init__(urls, name)
        logging.info("Starting the browser and navigating to the URL.")
        self.driver = webdriver.Chrome()
        self.jobs_filepath = file_manager.get_jobs_filepath(name)
        print(self.jobs_filepath)

    def get_jobs(self):
        for url in self.urls:
            self.driver.get(url)
            self.driver.implicitly_wait(4)

            stop = 0
            page_idx = 1
            jobs = set()
            while stop < 2:
                try:
                    next_page_btn = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='next']"))
                    )
                    logging.debug(f"Found the 'Next' button on page {page_idx}.")

                    self.driver.execute_script("arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });",
                                               next_page_btn)

                    job_items = self.get_job_items()
                    logging.info(f"Found {len(job_items)} jobs on page {page_idx}.")

                    for job_item in job_items:
                        try:
                            job = self.process_job_item(job_item)
                            if job:
                                Job.write_job_to_file(job.to_dict(), self.jobs_filepath)
                                jobs.add(job)
                        except Exception as e:
                            logging.error(f"Error processing job item: {e}", exc_info=True)

                    self.driver.execute_script("arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });",
                                               next_page_btn)
                    next_page_btn.click()
                    logging.info(f"Clicked 'Next' button to navigate to page {page_idx + 1}.")
                    page_idx += 1

                except TimeoutException:
                    logging.warning("Timeout waiting for the 'Next' button. Stopping pagination.")
                    stop += 1
                except NoSuchElementException as e:
                    logging.error(f"No such element exception: {e}", exc_info=True)
                    stop += 1
                except ElementClickInterceptedException as e:
                    logging.warning(f"Click intercepted: {e}. Retrying click with JavaScript.")
                    self.driver.execute_script("arguments[0].click();", next_page_btn)
                except Exception as e:
                    logging.error(f"Unexpected error: {e}", exc_info=True)
                    stop += 1

            self.driver.quit()
            return list(jobs)

    def get_job_items(self):
        stop = 0
        max_retries = 3
        while stop <= max_retries:
            try:
                time.sleep(1)
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//ul[@aria-label and @role='list']"))
                )
                ul_element = self.driver.find_element(By.XPATH, "//ul[@aria-label and @role='list']")
                job_items = WebDriverWait(ul_element, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "li.css-1q2dra3"))
                )
                return job_items
            except Exception as e:
                stop += 1
                print(f"Attempt {stop}/{max_retries + 1} failed. Error: {e}")
        return []

    def process_job_item(self, job_item):
        stop = 0
        max_retries = 3
        TIMEOUT = 10  # Configurable timeout value

        while stop <= max_retries:
            try:
                # Step 1: Scroll to the current item
                self.driver.execute_script("arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });",
                                           job_item)

                # Step 2: Locate the <h3> and click it
                time.sleep(2)
                job_title = job_item.find_element(By.TAG_NAME, "h3")
                WebDriverWait(self.driver, TIMEOUT).until(EC.element_to_be_clickable(job_title)).click()

                # Step 3: Wait for the section to open and collect it
                time.sleep(2)
                WebDriverWait(self.driver, TIMEOUT).until(EC.presence_of_element_located(
                    (By.XPATH, "//section[@data-automation-id='jobDetails' and @aria-label='Job Details']")
                ))
                job_desc_element = self.driver.find_element(By.XPATH,
                                                            "//section[@data-automation-id='jobDetails' and @aria-label='Job Details']")

                # Step 4: Collect the <a> element from the section
                time.sleep(2)
                link_to_job = job_desc_element.find_element(By.XPATH,
                                                            ".//a[@aria-label='Open in new window' and contains(@class, 'css-2zzt0z')]")
                link_to_job_href = link_to_job.get_attribute("href")
                if not link_to_job_href:
                    raise ValueError("Job link not found!")

                # Step 5: Interact with LLM and return the processed job
                response = llm_with_tools.get_llm_response(
                    PROMPTS.CREATE_JOB_PROMPT.format(source=link_to_job_href, job_desc=job_item.text)
                )
                job = llm_with_tools.execute_function_from_response(response)
                return job

            except Exception as e:
                print(f"Retry {stop}/{max_retries} failed: {e}")  # Log retries
                stop += 1
        print("Max retries exceeded for processing job item.")
        return None


if __name__ == '__main__':
    agent = Nvidia_agent()
    jobs = agent.get_jobs()
