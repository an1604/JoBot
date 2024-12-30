import logging

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)

from agents.file_manager import file_manager
from agents.job import Job
from agents.llm import llm_with_tools, PROMPTS
from agents.selenuim.agents.classic_agent import Agent

AMZN_URL = "https://www.amazon.jobs/en/search?offset=0&result_limit=10&sort=relevant&category%5B%5D=software-development&category%5B%5D=machine-learning-science&category%5B%5D=operations-it-support-engineering&category%5B%5D=data-science&job_type%5B%5D=Full-Time&job_type%5B%5D=Part-Time&country%5B%5D=ISR&city%5B%5D=Tel%20Aviv-Yafo&city%5B%5D=Haifa&distanceType=Mi&radius=24km&industry_experience=one_to_three_years&latitude=&longitude=&loc_group_id=&loc_query=Israel&base_query=&city=&country=ISR&region=&county=&query_options=&"

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class Amzn_agent(Agent):
    def __init__(self, urls=None, name="amzn_agent"):
        if not urls:
            urls = AMZN_URL
        super().__init__(urls, name)
        self.driver = webdriver.Chrome()
        logging.info(f"Agent {name} initialized with URL: {urls}")

    def get_jobs(self):
        logging.info("Starting job extraction process...")
        self.driver.get(self.urls)
        jobs = set()
        page_number = 1
        stop = 0

        while stop <= 10:
            try:
                logging.info(f"Scraping jobs on page {page_number}...")

                # Locate job elements
                job_elements = self.driver.find_elements(By.XPATH, "//div[@class='job-tile']")
                logging.info(f"Found {len(job_elements)} job elements.")

                if job_elements:
                    for index, job_element in enumerate(job_elements):
                        try:
                            # Extract job link
                            job_link = job_element.find_element(By.XPATH, ".//a[@class='job-link']")
                            job_url = job_link.get_attribute("href")
                            job_desc = job_element.text

                            # Log job details for debugging
                            logging.debug(f"Job #{index + 1} - URL: {job_url}")
                            logging.debug(f"Job #{index + 1} - Description: {job_desc}")

                            # Process job details
                            response = llm_with_tools.get_llm_response(PROMPTS.CREATE_JOB_PROMPT.format(source=job_url,
                                                                                                        job_desc=job_desc))
                            job_obj = llm_with_tools.execute_function_from_response(response)
                            if job_obj:
                                jobs.add(job_obj)
                                logging.info(f"Job #{index + 1} successfully processed.")
                                Job.write_job_to_file(job_obj.to_dict(), self.jobs_filepath)
                        except NoSuchElementException as e:
                            logging.warning(f"No job link found for job element #{index + 1}: {e}")
                        except Exception as e:
                            logging.error(f"Error processing job element #{index + 1}: {e}")

                # Navigate to the next page
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                next_page_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Next page']"))
                )
                next_page_button.click()
                logging.info(f"Navigated to page {page_number + 1}")
                page_number += 1

            except TimeoutException:
                logging.warning("Next page button not found or timeout occurred.")
                stop += 1
            except WebDriverException as e:
                logging.error(f"WebDriver exception occurred: {e}")
                stop += 1
            except Exception as e:
                logging.error(f"An unexpected error occurred: {e}")
                stop += 1

        logging.info(f"Job extraction completed. Total jobs extracted: {len(jobs)}")
        return list(jobs)


if __name__ == '__main__':
    try:
        amzn_agent = Amzn_agent()
        jobs = amzn_agent.get_jobs()
        logging.info(f"Saved {len(jobs)} jobs to JSON file.")
    except Exception as e:
        logging.error(f"An error occurred in the main process: {e}")
    finally:
        if 'amzn_agent' in locals():
            amzn_agent.driver.quit()
            logging.info("Driver closed.")
