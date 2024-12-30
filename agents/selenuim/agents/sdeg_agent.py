import logging
import pdb
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from agents.job import Job
from agents.llm import llm_with_tools, PROMPTS
from agents.selenuim.agents.classic_agent import Agent

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

job_category_classname = "job-container-category"


class SDEG_Agent(Agent):
    def __init__(self, urls=None, name="sdeg_agent"):
        if not urls:
            urls = "https://corporate.solaredge.com/en/careers/open-positions"
        super().__init__(urls, name)
        try:
            logging.info("Initializing WebDriver.")
            self.driver = webdriver.Chrome()
        except Exception as e:
            logging.error(f"Failed to initialize WebDriver: {e}")
            raise

    def get_jobs(self):
        self.open_browser()
        jobs_ = []

        self.handle_choices()

        pdb.set_trace()
        try:
            categories = self.driver.find_elements(By.CLASS_NAME, job_category_classname)
            if not categories:
                logging.warning("No job categories found.")
                return jobs_

            for category in categories:
                logging.info(f"Processing category: {category.text}")
                available_jobs = category.find_elements(By.TAG_NAME, 'a')

                for a_tag_job in available_jobs:
                    try:
                        source = a_tag_job.get_attribute('href') or self.driver.current_url
                        response = llm_with_tools.get_llm_response(
                            PROMPTS.CREATE_JOB_PROMPT.format(source=source, job_desc=a_tag_job.text))
                        job = llm_with_tools.execute_function_from_response(response)
                        if job:
                            jobs_.append(job)
                            logging.info(f"Added job: {job.to_dict()}")
                    except Exception as e:
                        logging.error(f"Error processing job link: {e}", exc_info=True)
        except NoSuchElementException as e:
            logging.error(f"No such element exception: {e}", exc_info=True)
        except TimeoutException as e:
            logging.error(f"Timeout occurred: {e}", exc_info=True)
        except Exception as e:
            logging.error(f"Unexpected error during job fetching: {e}", exc_info=True)

        self.driver.quit()
        Job.save_jobs_to_json(jobs, self.jobs_filepath)
        return jobs_

    def handle_choices(self):
        # Handle the options choosing
        # 1. Country (Israel)
        dropdown = self.driver.find_element(By.XPATH,
                                            "/html/body/div[12]/div[2]/div/div[2]/article/div/div/div/div/div[1]/form/div/div[1]/div[1]/span/span[1]/span")

        self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", dropdown)
        dropdown.click()

        regions_ul_xpath = "/html/body/span/span/span[2]/ul"
        regions_ul = self.driver.find_element(By.XPATH, regions_ul_xpath)
        if regions_ul:
            regions = regions_ul.find_elements(By.TAG_NAME, 'li')
            if regions:
                for region in regions:
                    if 'israel' in region.text.lower():
                        region.click()
                        break

        # 2. Job Family
        select_element = self.driver.find_element(By.CLASS_NAME, "job-select-family")
        self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                                   select_element)

        select = Select(select_element)
        if select.is_multiple:
            # Clear any pre-selected options
            select.deselect_all()

        options_to_select = ["IT", "R&D Embedded", "R&D Software", "Research"]
        for option in options_to_select:
            option_element = self.driver.find_element(By.XPATH, f"//option[text()='{option}']")
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                                       option_element)

            select.select_by_visible_text(option)
            print(f"Selected option: {option}")

        time.sleep(5)

        submit = self.driver.find_element(By.ID, "searchPositions")
        self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", submit)

        if submit:
            submit.click()

    def open_browser(self):
        try:
            self.driver.get(self.urls)
            logging.info(f"Navigated to {self.urls}.")
            self.driver.implicitly_wait(4)
        except Exception as e:
            logging.error(f"Failed to load URL {self.urls}: {e}")
            self.driver.quit()
            return []


if __name__ == '__main__':
    agent = SDEG_Agent()
    jobs = agent.get_jobs()
