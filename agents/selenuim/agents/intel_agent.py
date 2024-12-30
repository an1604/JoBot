import logging
import pdb
from typing import Any, Set

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)

from agents.job import Job
from agents.llm import llm_with_tools
from agents.selenuim.agents.classic_agent import Agent

# Constants
INTEL_URL = "https://intel.wd1.myworkdayjobs.com/en-US/External?locations=1e4a4eb3adf101ad7f35e278bf812cd1&locations=1e4a4eb3adf101aaeda8a474bf818ecd&locations=1e4a4eb3adf101cb242c9e74bf8189cd&locations=1e4a4eb3adf1013563ba9174bf817fcd&timeType=dc193d6170de10860883d9bf7c0e01a9&timeType=dc193d6170de10860883d9a5954a01a8&jobFamilyGroup=ace7a3d23b7e01a0544279031a0ec85c&jobFamilyGroup=dc8bf79476611087d67b36517cf17036"

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.DEBUG)


class IntelAgent(Agent):
    def __init__(self, urls=None, name="intel_agent"):
        urls = urls or INTEL_URL
        super().__init__(urls, name)
        try:
            self.driver = webdriver.Chrome()
            logging.info("Chrome WebDriver initialized successfully.")
        except WebDriverException as e:
            logging.error(f"Failed to initialize WebDriver: {e}")
            raise

    def get_jobs(self) -> Set[Job]:
        """Fetch job listings and process them into Job objects."""
        all_jobs = set()
        jobs_added = set()
        try:
            pdb.set_trace()
            logging.info(f"Navigating to URL: {self.urls}")
            self.driver.get(self.urls)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

            logging.info("Job list found. Extracting jobs.")
            jobs_ = self.driver.find_elements(By.XPATH, '//*[@id="mainContent"]//ul/li')

            for index, job in enumerate(jobs_):
                try:
                    logging.debug(f"Processing job #{index + 1}.")
                    a_element = job.find_element(By.XPATH, '//*[@id="mainContent"]//ul/li//h3/a')
                    source_url = a_element.get_attribute("href")
                    job_title = a_element.text
                    logging.info(f"Job Title: {job_title}, URL: {source_url}")

                    # Generate response and execute function
                    response = llm_with_tools.get_llm_response(
                        PROMPTS.CREATE_JOB_PROMPT.format(source=source_url, job_desc=job_title))
                    job_obj = llm_with_tools.execute_function_from_response(response)

                    if job_obj:
                        indication_tuple = (job_obj.job_title, job_obj.source)
                        if not indication_tuple in jobs_added:
                            all_jobs.add(job_obj)
                            jobs_added.add(indication_tuple)

                        logging.info(f"Job object created and added: {job_obj}")
                    else:
                        logging.warning("Job object creation failed.")

                except NoSuchElementException as e:
                    logging.warning(f"Missing <a> element for job #{index + 1}: {e}")
                except Exception as e:
                    logging.error(f"Error processing job #{index + 1}: {e}", exc_info=True)

        except TimeoutException:
            logging.error("Timed out waiting for the job list to load.")
        except WebDriverException as e:
            logging.critical(f"WebDriver error: {e}", exc_info=True)
        except Exception as e:
            logging.critical(f"Unexpected error: {e}", exc_info=True)
        finally:
            logging.info("Closing WebDriver.")
            self.driver.quit()

        logging.info(f"Total jobs processed: {len(all_jobs)}")
        return all_jobs


if __name__ == '__main__':
    intel_agent = IntelAgent()
    jobs = intel_agent.get_jobs()
    Job.save_jobs_to_json(jobs, "intel_jobs.json")
