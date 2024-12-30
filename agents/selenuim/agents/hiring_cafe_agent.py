import pdb
import time
from ast import Index

from google.api_core.exceptions import OutOfRange

from agents.Server.db import job_contains_in_db, add_job_to_job_collection
from agents.file_manager import file_manager
from agents.job import Job
from agents.selenuim.agents.classic_agent import Agent
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class HiringCafe_agent(Agent):
    def __init__(self, urls=None, name='hiring_cafe_jobs'):
        self.links_filepath = file_manager.get_path_from_companies('company_links.txt')
        self.new_jobs_filepath = file_manager.get_jobs_filepath('hiring_cafe_jobs1.json')

        if not urls:
            urls = 'https://hiring.cafe/'
        super().__init__(urls, name)

    def get_all_links(self):
        self.initialize_driver()
        self.driver.get(self.urls)
        stop = 0
        company_links = set()
        while stop <= 10:
            try:
                time.sleep(5)
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                job_cards = self.get_job_cards()
                for job_card in job_cards:
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", job_card)
                        see_all_jobs_link = WebDriverWait(job_card, 10).until(
                            EC.presence_of_element_located(
                                (By.XPATH, ".//a[contains(@class, 'text-xs') and contains(text(), 'See all jobs')]"))
                        )
                        href = see_all_jobs_link.get_attribute("href")
                        print("Company Link:", href)
                        company_links.add(href)
                        self.write_link_to_file(href)

                    except Exception as e:
                        print(f"Job card skipped: {e}")

            except Exception as e:
                stop += 1
                print(f"Error occurred during scraping: {e}")
        return company_links

    def get_jobs(self, company_links=None):
        if not company_links:
            company_links = self.get_all_links()
        self.initialize_driver()
        for link in company_links:
            try:
                self.driver.get(link)
                company_name = self.get_company_name()
                if company_name:
                    self.process_company(company_name, link)
            except Exception as e:
                print(f"Failed to process link {link}: {e}")
                continue

    def get_company_name(self):
        stop = 0
        while stop <= 5:
            try:
                job_div = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(
                        (By.XPATH,
                         "//div[contains(@class, 'flex') and contains(@class, 'justify-center') and contains(@class, 'items-center') and contains(@class, 'flex-col')]//span[contains(text(), 'Jobs at')]")
                    )
                )
                button = job_div.find_element(By.XPATH,
                                              ".//button[contains(@class, 'font-bold') and contains(@class, 'text-purple-500')]")
                return button.text
            except:
                stop += 1

    def process_company(self, company_name, link):
        stop = 0
        scroll_down_counter = 0
        while stop <= 5 and self.is_scrollable():
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            scroll_down_counter += 1
            job_cards = self.get_job_cards()

            already_seen_jobs = set()
            for i in range(len(job_cards)):
                try:
                    job_card = job_cards[i]
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", job_card)

                    # Click twice, to open the job tab
                    job_card.click()
                    job_card.click()

                    job_title = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located(
                            (By.XPATH,
                             "//h2[contains(@class, 'font-extrabold') and contains(@class, 'text-3xl')]")
                        )
                    ).text

                    job_source_element = self.driver.find_element(By.XPATH,
                                                                  "//a[contains(@class, 'text-xs') and span[text()='Full View']]")
                    job_source = job_source_element.get_attribute("href")
                    if not job_source in already_seen_jobs:
                        already_seen_jobs.add(job_source)
                        job_obj = Job(
                            job_title=job_title,
                            source=job_source,
                            company=company_name
                        )
                        if not job_contains_in_db(job_obj):
                            Job.write_job_to_file(job_obj.to_dict(), self.jobs_filepath)
                            if add_job_to_job_collection(job_obj):
                                print("Job added to the DB!")

                    # Close the job tab
                    self.close_job_tab(job_card)
                    time.sleep(2)
                except IndexError:
                    print(f"IndexError occur, breaking the for loop...")
                    break
                except Exception as e:
                    print(f"Failed to extract job title for this card: {e}")
                    self.driver.get(link)
                    time.sleep(5)
                    self.scroll_down(scroll_down_counter)
                    job_cards = self.get_job_cards_after_exception(already_seen_jobs)
                    continue
        # pdb.set_trace()
        return

    def is_scrollable(self):
        return self.driver.execute_script(
            "return document.documentElement.scrollHeight > document.documentElement.scrollTop + document.documentElement.clientHeight;"
        )

    def write_link_to_file(self, href):
        with open(self.links_filepath, 'a') as links_file:
            links_file.write(f'{href}\n')

    def close_job_tab(self, job_card):
        try:
            close_btn_container = job_card.find_element(
                By.XPATH, "//header[contains(@class, 'chakra-modal__header')]"
            )
            # Try to get the close button and close it.
            try:
                close_btn = close_btn_container.find_elements(By.XPATH, ".//button")[2]
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", close_btn)
                self.driver.execute_script("arguments[0].click();", close_btn)
                return True
            except:
                return False
        except Exception as e:
            print(
                f"Failed to interact with the close button: {e} - Container HTML: {job_card.get_attribute('outerHTML')}")
            return False

    def get_job_cards_after_exception(self, already_seen_job_cards):
        job_cards = self.get_job_cards()

        for job_card in job_cards:
            if job_card in already_seen_job_cards:
                job_cards.remove(job_card)
        return list(job_cards)

    def get_job_cards(self):
        stop = 0
        while stop <= 7:
            try:
                job_cards = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located((By.XPATH, "//div[contains(@class, 'relative')]"))
                )
                job_cards = list(set(job_cards))

                if len(job_cards) > 5:
                    return job_cards

            except Exception as e:
                stop += 1
        return None

    def filter_jobs(self):
        all_jobs = Job.load_jobs_from_json(self.jobs_filepath)
        jobs = set()
        for job in all_jobs:
            job_element = (job.get('job_title', ''), job.get('source', ''))
            job_obj = Job.from_dict(job)
            if not job_element in jobs:
                jobs.add(job_obj)
        Job.save_jobs_to_json(jobs, self.new_jobs_filepath)

    def scroll_down(self, scroll_down_counter):
        try:
            for i in range(scroll_down_counter):
                time.sleep(1)
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            return
        except:
            return


if __name__ == '__main__':
    agent = HiringCafe_agent()
    links_set = set()
    with open(agent.links_filepath, 'r') as links_file:
        for line in links_file:
            links_set.add(line.strip())

    agent.get_jobs(links_set)
