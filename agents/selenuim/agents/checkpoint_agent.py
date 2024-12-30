import logging

from dominate.tags import source
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
from agents.llm import llm_with_tools, PROMPTS
from agents.selenuim.agents.classic_agent import Agent

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

CP_URLS = [
    "https://careers.checkpoint.com/index.php?m=cpcareers&a=programs#programsSection",
    "https://careers.checkpoint.com/?q=&module=cpcareers&a=search&fa%5B%5D=country_ss%3AIsrael&fa%5B%5D=department_s%3AEmail%2520Security&fa%5B%5D=department_s%3AData%2520Security&fa%5B%5D=department_s%3ACloud%2520Security&fa%5B%5D=department_s%3AProducts%2520-%2520QA&sort=",
]


class CheckPoint_agent(Agent):
    def __init__(self, urls=None, name="checkpoint_agent"):
        if not urls:
            urls = CP_URLS
        super().__init__(urls, name)
        self.driver = webdriver.Chrome()
        logging.info(f"Initialized CheckPoint_agent with URLs: {urls}")

    def get_jobs(self):
        logging.info("Starting job scraping...")
        jobs = set()
        stop = 0

        try:
            self.driver.get(self.urls[1])
            logging.info(f"Loaded URL: {self.urls[1]}")
        except WebDriverException as e:
            logging.error(f"Error loading URL: {e}")
            return list(jobs)

        while stop <= 10:
            try:
                logging.info("Fetching position elements...")
                position_elements = self.driver.find_elements(By.XPATH, "//div[@class='position']")
                logging.info(f"Found {len(position_elements)} position elements.")

                for position in position_elements:
                    try:
                        job_obj = self.fetch_job_element(position)
                        if job_obj:
                            jobs.add(job_obj)
                            logging.info(f"Job added: {job_obj.job_title}")
                    except Exception as e:
                        logging.error(f"Error processing position element: {e}")

                # Click next page
                try:
                    next_page_btn = self.driver.find_element(By.XPATH, "//label[i[contains(@class, 'nextPage')]]")
                    if next_page_btn:
                        logging.info("Clicking 'Next Page' button...")
                        next_page_btn.click()
                        WebDriverWait(self.driver, 10).until(
                            EC.presence_of_all_elements_located((By.XPATH, "//div[@class='position']"))
                        )
                except NoSuchElementException:
                    logging.warning("No 'Next Page' button found. Stopping pagination.")
                    break
                except TimeoutException:
                    logging.error("Timeout waiting for the next page to load.")
                    break

            except Exception as e:
                logging.error(f"Unexpected error during job scraping: {e}")
                stop += 1

        logging.info(f"Job scraping completed. Total jobs found: {len(jobs)}")
        Job.save_jobs_to_json(jobs, f"../json_jobs/{self.name}.json")
        return list(jobs)

    def get_programs(self):
        logging.info("Starting program scraping...")
        jobs = set()

        try:
            self.driver.get(self.urls[0])
            logging.info(f"Loaded URL: {self.urls[0]}")
        except WebDriverException as e:
            logging.error(f"Error loading URL: {e}")
            return list(jobs)

        try:
            israel_programs_xpath = "/html/body/div[6]/ul/li[2]"
            israel_programs_btn = self.driver.find_element(By.XPATH, israel_programs_xpath)
            logging.info("Found 'Israel Programs' button. Scrolling into view...")
            self.driver.execute_script("arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });",
                                       israel_programs_btn)
            israel_programs_btn.click()

            programs = self.driver.find_elements(By.XPATH, "//div[@class='program']")
            logging.info(f"Found {len(programs)} program elements.")

            for program in programs:
                try:
                    job_obj = self.fetch_job_element(program)
                    if job_obj:
                        jobs.add(job_obj)
                        logging.info(f"Program job added: {job_obj.job_title}")
                except Exception as e:
                    logging.error(f"Error processing program element: {e}")

        except NoSuchElementException:
            logging.error("Could not find 'Israel Programs' button.")
        except Exception as e:
            logging.error(f"Unexpected error during program scraping: {e}")

        logging.info(f"Program scraping completed. Total jobs found: {len(jobs)}")
        return list(jobs)

    def fetch_job_element(self, job_element):
        try:
            a_element = job_element.find_element(By.XPATH, ".//a")
            source_url = a_element.get_attribute("href") if a_element else self.driver.current_url
            logging.info(f"Fetched job URL: {source_url}")

            response = llm_with_tools.get_llm_response(
                PROMPTS.CREATE_JOB_PROMPT.format(source=source_url, job_desc=job_element.text))
            job_obj = llm_with_tools.execute_function_from_response(response)

            if job_obj:
                logging.info(f"Created Job object: {job_obj.to_dict()}")
                return job_obj
        except NoSuchElementException as e:
            logging.error(f"Error fetching job element: {e}")
        except Exception as e:
            logging.error(f"Unexpected error in fetch_job_element: {e}")
        return None


if __name__ == "__main__":
    agent = CheckPoint_agent()
    jobs = agent.get_jobs()
    jobs.extend(agent.get_programs())
    logging.info(f"Scraped {len(jobs)} jobs from CheckPoint.")
