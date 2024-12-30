import os.path
import pdb
import time

from langchain_community.llms import Ollama
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import json
from selenium.webdriver.support import expected_conditions as EC
import re

llm = Ollama(model='llama3')


# Classes to store company and section data
class Company:
    def __init__(self, company_name_, company_description_, company_links):
        self.company_name = company_name_
        self.company_desc = company_description_
        self.company_links = company_links
        self.file_path = r'C:\Users\אביב\PycharmProjects\jobFinder\agents\companies\all_companies.json'

    # Convert to dictionary
    def to_dict(self):
        return {
            "company_name": self.company_name,
            "company_desc": self.company_desc,
            "company_links": self.company_links,
        }

    # Convert to JSON
    def to_json(self):
        return json.dumps(self.to_dict())

    # Create from dictionary
    @classmethod
    def from_dict(cls, data):
        return cls(
            company_name_=data["company_name"],
            company_description_=data["company_desc"],
            company_links=data["company_links"],
        )

    # Create from JSON
    @classmethod
    def from_json(cls, json_data):
        return cls.from_dict(json.loads(json_data))

    def write_company_to_file(self):
        try:
            with open(self.file_path, 'a') as companies_file:
                companies_file.write(self.to_json() + '\n')
                return True
        except Exception as e:
            print(f'Exception occur while trying to write {self.company_name} to '
                  f'{self.file_path} --> {e}')
            return False


class JobSection:
    def __init__(self, section_name_: str, companies_: list):
        self.section_name = section_name_
        self.companies = companies_

    # Convert to dictionary
    def to_dict(self):
        return {
            "section_name": self.section_name,
            "companies": [company.to_dict() for company in self.companies],
        }

    # Convert to JSON
    def to_json(self):
        return json.dumps(self.to_dict())

    # Create from dictionary
    @classmethod
    def from_dict(cls, data):
        return cls(
            section_name_=data["section_name"],
            companies_=[Company.from_dict(company) for company in data["companies"]],
        )

    # Create from JSON
    @classmethod
    def from_json(cls, json_data):
        return cls.from_dict(json.loads(json_data))


driver = None


def initialize_webDriver(retries=3):
    global driver
    if not driver:
        for attempt in range(retries):
            try:
                driver = webdriver.Chrome()
                driver.get("https://maphub.net/mluggy/techmap")
                print("WebDriver initialized successfully.")
                return driver
            except Exception as e:
                print(f"Attempt {attempt + 1} to initialize WebDriver failed: {e}")
                time.sleep(3)  # Wait before retrying
    else:
        return driver


# Wait for job sections to load
def get_sections():
    driver = initialize_webDriver()
    try:
        scrollable_div = get_scrollable_div()
        driver.execute_script("arguments[0].scrollTop = 0;", scrollable_div)
        job_sections = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located(
                (By.XPATH, "//div[@role='treeitem' and @aria-level='1']")
            )
        )

        return job_sections
    except Exception as e:
        print(f"Error loading job sections: {e}")
        driver.quit()
        exit()


def close_job_section(section_name, index):
    print(f"Attempting to close job section: {section_name} at index: {index}")
    # First try to click on the same section element directly.
    sections = get_sections()
    try:
        print("Trying to click the section directly using the index.")
        sections[index].click()
        print(f"Successfully clicked the section at index: {index}.")
        return
    except Exception as e:
        print(f"Failed to click the section at index: {index}. Error: {e}")

    # If for some reason it didn't work, iterate through the sections
    # to find the correct element to click.
    for section in sections:
        if section.text == section_name:
            try:
                print(f"Found section matching name: {section_name}. Attempting to click it.")
                section.click()
                print(f"Successfully clicked the section: {section_name}.")
                return
            except Exception as e:
                print(f"Failed to click section: {section_name}. Error: {e}")

    # Try to press the last element in the list
    try:
        print("Attempting to click the last section in the list as a fallback.")
        sections[-1].click()
        print("Successfully clicked the last section.")
        return
    except Exception as e:
        print(f"Failed to click the last section in the list. Entering debugger. Error: {e}")


def company_name_is_job_section(company_name, section_name: str):
    try:
        print(
            f"Checking if company name '{company_name}' is a job section under '{section_name}' or in the provided sections.")
        if company_name == section_name:
            print(f"Company name '{company_name}' matches section name '{section_name}'.")
            return True

        sections = get_all_sections_names()
        for section in sections:
            if section in company_name:
                print(f"Company name '{company_name}' matches a section name in the list: '{section}'.")
                return True

        print(f"Company name '{company_name}' is not a job section.")
        return False

    except Exception as e:
        print(f"Error while checking if company name is a job section: {e}")
        raise


def close_popup(popup_content):
    print("Attempting to close popup...")
    stop = 0
    while stop <= 10:
        try:
            time.sleep(2)
            print(f"Attempt {stop + 1}: Trying to locate and click the close button.")
            close_button = popup_content.find_element(By.CSS_SELECTOR, ".mapboxgl-popup-close-button")
            close_button.click()
            print("Popup closed successfully.")
            return
        except Exception as e:
            print(f"Attempt {stop + 1} failed to close the popup. Error: {e}")
            stop += 1

    print("Failed to close popup after 10 attempts.")
    raise Exception("Unable to close the popup after multiple attempts.")


def process_visible_companies(job_section_text, sections_as_objs_list):
    global llm

    job_section_wrapper = collect_job_section_wrapper()
    visible_companies = get_visible_companies(job_section_wrapper)
    print(f"Found {len(visible_companies)} visible companies.")
    companies = set()
    for company in visible_companies:
        stop = 0
        while stop <= 5:
            try:
                print(f"Processing company: {company.text}")
                time.sleep(3)  # Simulate delay

                company_name = company.text
                if company_name_is_job_section(company_name, job_section_text):
                    print(f"Skipping company '{company_name}' as it matches a job section.")
                    break

                company_description = []
                print(f"Clicking on company: {company_name}")
                company.click()

                # Wait for the popup to appear
                popup_content = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".mapboxgl-popup-content"))
                )
                print(f"Popup content found for company: {company_name}")

                # Extract <p> elements and links
                p_elements_of_company = popup_content.find_elements(By.TAG_NAME, 'p')
                links = {}
                for p in p_elements_of_company:
                    try:
                        a_elements = p.find_elements(By.TAG_NAME, 'a')
                        if len(a_elements) == 0:
                            company_description.append(p.text)

                        for i, a in enumerate(a_elements):
                            link = a.get_attribute('href')
                            if i == 0 or i == 1:
                                links['website'] = link
                            elif i == 2:
                                links['linkedin'] = link
                            else:
                                break
                    except Exception as e:
                        print(f"Error extracting links from paragraph: {e}")
                        stop += 1
                        continue

                # Close the popup
                print(f"Closing popup for company: {company_name}")
                close_popup(popup_content)

                # Generate and add the company to the list
                company_description_str = llm.invoke(
                    f"Generate a short description about the company called {company_name}, "
                    f"given the following information:\n{' '.join(company_description)}"
                )

                comp = Company(company_name, company_description_str, links)
                if comp.write_company_to_file():
                    companies.add(comp)
                    print(f"Added company '{company_name}' to the list.")
                    break  # Exit retry loop if successful (the stop is holding the while loop to run)
                else:
                    stop += 1
            except Exception as e:
                print(f"Error processing company '{company.text if company else 'Unknown'}'. Error: {e}")
                stop += 1
                if stop > 5:
                    print(f"Failed to process company '{company.text if company else 'Unknown'}' after 3 attempts.")

    print(
        f"Finished processing companies for job section: '{job_section_text}'. Total companies processed: {len(companies)}.")
    return companies


def get_visible_companies(job_section_wrapper):
    try:
        print("Collecting visible companies from the current scroll position.")
        visible_companies = WebDriverWait(job_section_wrapper, 5).until(
            EC.presence_of_all_elements_located(
                (By.XPATH,
                 "//div[contains(@class, 'panel-itemtree-node') and contains(@class, 'node-hoverable')]")
            )
        )
        return visible_companies
    except Exception as e:
        print(f"Error collecting visible companies: {e}")


def collect_job_section_wrapper():
    try:
        print("Attempting to locate the job section wrapper...")
        # The container that wraps the job_section, to ensure that we can access more companies in the while loop.
        job_section_wrapper_xpath = (
            "//*[contains(@class, 'panel-itemtree-node')]/ancestor::div[contains(@style, 'overflow: auto') or contains(@style, 'position: relative')][1]"
        )
        job_section_wrapper = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, job_section_wrapper_xpath))
        )
        print("Job section wrapper located successfully.")
        return job_section_wrapper

    except Exception as e:
        print(f"Error locating the job section wrapper. Error: {e}")
        return None


def scroll_and_get_all_jobs_per_section(job_section, job_section_current_idx, section_list_size, sections_as_objs,
                                        job_section_text):
    driver_ = initialize_webDriver()
    print(f"Starting to scroll and collect jobs for section '{job_section.text}' (index: {job_section_current_idx}).")
    job_section_wrapper = collect_job_section_wrapper()  # The container that includes all job sections
    scrollable_div = get_scrollable_div()
    all_companies = set()
    last_height = 0

    while job_section_wrapper.is_displayed():
        try:
            visible_companies = process_visible_companies(job_section_text, sections_as_objs)
            print(f"Processed {len(visible_companies)} companies for section '{job_section.text}'.")

            all_companies.add(visible_companies)

            print("Scrolled down by 400 pixels.")
            driver_.execute_script("arguments[0].scrollTop += 400;", scrollable_div)
            time.sleep(4)

            new_height = driver_.execute_script("return arguments[0].scrollTop;", scrollable_div)
            if new_height == last_height:
                print("Reached the bottom of the scrollable div.")
                break
            last_height = new_height
            job_section_wrapper = collect_job_section_wrapper()
        except Exception as e:
            # Error while trying to scrape a company, regularly appear when
            # we need to scroll more down.
            print(f"Error during scrolling and collecting jobs: {e}")

            driver_.execute_script("arguments[0].scrollTop += 400;", scrollable_div)
            time.sleep(4)
            print("Scrolled down by 400 pixels.")
    return all_companies


def get_scrollable_div():
    driver_ = initialize_webDriver()
    stop = 0
    while stop <= 10:
        try:
            print("Attempting to locate the scrollable div...")
            scrollable_div = WebDriverWait(driver_, 10).until(
                EC.presence_of_element_located((By.XPATH, "//*[@id='panel-items-list']/div/div"))
            )
            print("Successfully located the scrollable div.")
            return scrollable_div
        except Exception as e:
            print(f"Error locating the scrollable div: {e}")
            stop += 1
    raise


all_sections_names = None


def get_all_sections_names():
    global all_sections_names

    if not all_sections_names:
        scrollable_div = get_scrollable_div()
        sections = scrollable_div.find_elements(By.XPATH,
                                                ".//div[@role='treeitem' and contains(@class, 'nofocusvisible')]")
        all_sections_names = set()
        for section in sections:
            all_sections_names.add(section.text)
    return all_sections_names


def get_data():
    # Initializing the driver...
    driver_ = initialize_webDriver()
    if not driver_:
        driver_ = initialize_webDriver()
    get_all_sections_names()
    print("Starting to gather data...")
    sections_as_objs = []
    index = 0
    try:
        while True:
            time.sleep(2)
            print(f"Fetching sections. Current index: {index}")
            sections_as_webelements = get_sections()
            print(f"Found {len(sections_as_webelements)} sections.")

            if index < len(sections_as_webelements):
                job_section = sections_as_webelements[index]
                print(f"Processing section: {job_section.text}")
            else:
                print(f"Index {index} is out of bounds. Breaking loop.")
                break

            try:
                section_name = job_section.text
                print(f"Section name: {section_name}")

                scrollable_div = get_scrollable_div()

                # Scroll to the target section before clicking it
                print(f"Scrolling to the section: {section_name}")
                driver_.execute_script("arguments[0].scrollTop = arguments[1].offsetTop;", scrollable_div, job_section)
                time.sleep(2)

                job_section.click()

                companies_per_section = scroll_and_get_all_jobs_per_section(
                    job_section, index, len(sections_as_webelements), sections_as_objs, job_section.text)
                print(f"Collected {len(companies_per_section)} companies for section: {section_name}.")

                # Add the section and its companies to the list
                job_section_obj = JobSection(section_name, companies_per_section)
                write_section_to_file(job_section_obj)
                sections_as_objs.append(job_section_obj)

                print(f"Closing section: {section_name}")
                close_job_section(section_name, index)  # Close the drop-down div and move on to the next section.
                index += 1

            except Exception as e:
                print(f"Error processing section {index + 1}: {e}")
                continue
    except Exception as e:
        print(f"Critical error in data gathering process: {e}")
    finally:
        print("Closing the driver...")
        driver_.quit()

    print("Data gathering completed.")
    return sections_as_objs


def sanitize_file_name(name):
    try:
        print(f"Sanitizing file name: {name}")
        sanitized_name = re.sub(r'[<>:"/\\|?*]', '_', name)
        print(f"Sanitized file name: {sanitized_name}")
        return sanitized_name
    except Exception as e:
        print(f"Error sanitizing file name: {name}. Error: {e}")
        raise


def write_section_to_file(section):
    base_path = r'C:\Users\אביב\PycharmProjects\jobFinder\agents\companies'
    try:
        print(f"Ensuring the base directory exists: {base_path}")
        os.makedirs(base_path, exist_ok=True)  # Create directory if it doesn't exist
    except Exception as e:
        print(f"Error creating base directory: {base_path}. Error: {e}")
        raise

    try:
        print(f"Preparing to write section: {section.section_name}")
        sanitized_section_name = sanitize_file_name(section.section_name)
        file_name = f'{sanitized_section_name}.json'
        file_path = os.path.join(base_path, file_name)

        print(f"Writing section '{section.section_name}' to file: {file_path}")
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(section.to_json())

        print(f"Successfully wrote section: {section.section_name} to {file_path}")
    except Exception as e:
        print(f"Error writing section {section.section_name}: {e}")


if __name__ == '__main__':
    if not driver:
        driver = initialize_webDriver()
    sections_data = get_data()
