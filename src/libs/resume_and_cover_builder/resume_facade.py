"""
This module contains the FacadeManager class, which is responsible for managing the interaction between the user and other components of the application.
"""
import inquirer
import json
import time
from pathlib import Path
from loguru import logger

from .config import global_config

class FacadeManager:
    def __init__(self, api_key, style_manager, resume_generator, resume_object, output_path):
        lib_directory = Path(__file__).resolve().parent
        global_config.STRINGS_MODULE_RESUME_PATH = lib_directory / "resume_prompt/strings_feder-cr.py"
        global_config.STRINGS_MODULE_RESUME_JOB_DESCRIPTION_PATH = lib_directory / "resume_job_description_prompt/strings_feder-cr.py"
        global_config.STRINGS_MODULE_COVER_LETTER_JOB_DESCRIPTION_PATH = lib_directory / "cover_letter_prompt/strings_feder-cr.py"
        global_config.STRINGS_MODULE_NAME = "strings_feder_cr"
        global_config.STYLES_DIRECTORY = lib_directory / "resume_style"
        global_config.LOG_OUTPUT_FILE_PATH = output_path
        global_config.API_KEY = api_key
        
        self.style_manager = style_manager
        self.resume_generator = resume_generator
        self.resume_generator.set_resume_object(resume_object)
        self.driver = None

    def _set_driver(self):
        if not self.driver:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service as ChromeService
            from webdriver_manager.chrome import ChromeDriverManager
            
            # Create isolated options for PDF rendering
            options = webdriver.ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("window-size=1200x800")
            
            # CRITICAL: We do NOT use the main bot's profile here to avoid "SessionNotCreated" conflict
            self.driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)

    def choose_style(self):
        styles_dict = self.style_manager.get_styles()
        if not styles_dict:
            raise ValueError("No styles found in the styles directory.")
        
        choices = list(styles_dict.keys())
        choice = self.prompt_user(choices, "Which resume style would you like to use?")
        
        self.style_manager.set_selected_style(choice)
        logger.info(f"Selected style: {choice}")

    def pdf_base64(self, job_description_text: str) -> str:
        style_path = self.style_manager.get_style_path()
        if style_path is None:
            raise ValueError("You must choose a style before generating the PDF.")

        html_resume = self.resume_generator.create_resume_job_description_text(style_path, job_description_text)
        
        self._set_driver()
        
        # Define CDP endpoint
        resource = "/session/%s/chromium/send_command_and_get_result" % self.driver.session_id
        url = self.driver.command_executor._url + resource

        # Load a blank page first
        self.driver.get("about:blank")
        
        # Inject the HTML content safely using JS to avoid URL length limits
        escaped_html = html_resume.replace('`', '\\`').replace('$', '\\$')
        self.driver.execute_script(f"document.write(`{escaped_html}`); document.close();")
        time.sleep(1) # Allow CSS/Fonts to render
        
        # Use Chrome DevTools Protocol to print to PDF
        
        body = json.dumps({
            'cmd': 'Page.printToPDF',
            'params': {
                'printBackground': True,
                'preferCSSPageSize': True
            }
        })
        
        response = self.driver.command_executor._request('POST', url, body)
        if not response or 'value' not in response or 'data' not in response['value']:
            raise RuntimeError(f"Failed to generate PDF via Chrome: {response}")
            
        return response['value']['data']

    def prompt_user(self, choices: list[str], message: str) -> str:
        questions = [
            inquirer.List('selection', message=message, choices=choices),
        ]
        return inquirer.prompt(questions)['selection']

    def prompt_for_text(self, message: str) -> str:
        questions = [
            inquirer.Text('text', message=message),
        ]
        return inquirer.prompt(questions)['text']