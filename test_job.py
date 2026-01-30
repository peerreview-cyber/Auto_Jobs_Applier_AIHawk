import os
import sys
import yaml
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from src.utils import chrome_browser_options
from src.llm.llm_manager import GPTAnswerer
from src.aihawk_authenticator import AIHawkAuthenticator
from src.aihawk_easy_applier import AIHawkEasyApplier
from src.job import Job
from src.resume_schemas.resume import Resume
from src.job_application_profile import JobApplicationProfile
from lib_resume_builder_AIHawk import FacadeManager, ResumeGenerator, StyleManager

# 1. Load Configuration
try:
    with open('data_folder/secrets.yaml', 'r') as f: 
        secrets = yaml.safe_load(f)
    with open('data_folder/config.yaml', 'r') as f: 
        parameters = yaml.safe_load(f)
    with open('data_folder/plain_text_resume.yaml', 'r', encoding='utf-8') as f: 
        ptr_text = f.read()
except FileNotFoundError as e:
    print(f"Error: Missing configuration file: {e}")
    sys.exit(1)

llm_key = secrets['llm_api_key']
parameters['uploads'] = {'plainTextResume': Path('data_folder/plain_text_resume.yaml')}
parameters['outputFileDirectory'] = Path('data_folder/output')
os.makedirs(parameters['outputFileDirectory'], exist_ok=True)

# 2. Setup Components
print("Initializing Browser...")
driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_browser_options())

print("Logging in...")
auth = AIHawkAuthenticator(driver)
auth.start()

print("Setting up AI components...")
resume_obj = Resume(ptr_text)
style_manager = StyleManager()

# Use the correct path for the style file
style_path = os.path.join(os.getcwd(), "src", "libs", "resume_and_cover_builder", "resume_style", "style_josylad_blue.css")
if os.path.exists(style_path):
    style_manager.set_style_path(style_path)
else:
    print(f"Warning: Style file not found at {style_path}. Trying to continue...")

facade = FacadeManager(llm_key, style_manager, ResumeGenerator(), resume_obj, parameters['outputFileDirectory'])
gpt = GPTAnswerer(parameters, llm_key)
gpt.set_job_application_profile(JobApplicationProfile(ptr_text))
gpt.set_resume(resume_obj)

applier = AIHawkEasyApplier(driver, None, [], gpt, facade)

# 3. Target Specific Job
job = Job(
    title='Software Engineer',
    company='Harmony (tryharmony.ai)',
    location='Remote',
    link='https://www.linkedin.com/jobs/view/4364631888/',
    apply_method='Easy Apply'
)

print(f"Starting application for: {job.link}")
try:
    applier.job_apply(job)
    print("Application attempt finished!")
except Exception as e:
    print(f"Error during application: {e}")

# Keep browser open for inspection
input("Press Enter to close the browser...")
driver.quit()
