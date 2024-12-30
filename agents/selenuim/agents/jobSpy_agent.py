import csv
from jobspy import scrape_jobs

jobs = scrape_jobs(
    site_name=["indeed"],
    search_term="Junior software engineer",
    google_search_term="software engineer jobs near San Francisco, CA since yesterday",
    location="Tel Aviv, Israel",
    results_wanted=20,
    hours_old=72,
    country_indeed='Israel',

    # linkedin_fetch_description=True # gets more info such as description, direct job url (slower)
    # proxies=["208.195.175.46:65095", "208.195.175.45:65095", "localhost"],
)
print(f"Found {len(jobs)} jobs")
print(jobs.head())
jobs.to_csv("jobs.csv", quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)  # to_excel
