import base64
import json
import os
import random
import re
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Any, Tuple

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from reportlab.pdfbase.pdfmetrics import stringWidth
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

import src.utils as utils
from loguru import logger


class AIHawkEasyApplier:
    def __init__(self, driver: Any, resume_dir: Optional[str], set_old_answers: List[Tuple[str, str, str]],
                 gpt_answerer: Any, resume_generator_manager, always_tailor_resume: bool = True,
                 output_dir: Optional[Path] = None):
        logger.debug("Initializing AIHawkEasyApplier")
        if resume_dir is None or not os.path.exists(resume_dir):
            resume_dir = None
        self.driver = driver
        self.resume_path = resume_dir
        self.set_old_answers = set_old_answers
        self.gpt_answerer = gpt_answerer
        self.resume_generator_manager = resume_generator_manager
        self.always_tailor_resume = always_tailor_resume
        self.output_dir = output_dir
        self.all_data = self._load_questions_from_json()
        self.current_job = None

        logger.debug(f"AIHawkEasyApplier initialized (always_tailor={always_tailor_resume})")

    def _load_questions_from_json(self) -> List[dict]:
        output_file = 'answers.json'
        logger.debug(f"Loading questions from JSON file: {output_file}")
        try:
            with open(output_file, 'r') as f:
                try:
                    data = json.load(f)
                    if not isinstance(data, list):
                        raise ValueError("JSON file format is incorrect. Expected a list of questions.")
                except json.JSONDecodeError:
                    logger.error("JSON decoding failed")
                    data = []
            logger.debug("Questions loaded successfully from JSON")
            return data
        except FileNotFoundError:
            logger.warning("JSON file not found, returning empty list")
            return []
        except Exception:
            tb_str = traceback.format_exc()
            logger.error(f"Error loading questions data from JSON file: {tb_str}")
            raise Exception(f"Error loading questions data from JSON file: \nTraceback:\n{tb_str}")

    def check_for_premium_redirect(self, job: Any, max_attempts=3):

        current_url = self.driver.current_url
        attempts = 0

        while "linkedin.com/premium" in current_url and attempts < max_attempts:
            logger.warning("Redirected to AIHawk Premium page. Attempting to return to job page.")
            attempts += 1

            self.driver.get(job.link)
            time.sleep(2)
            current_url = self.driver.current_url

        if "linkedin.com/premium" in current_url:
            logger.error(f"Failed to return to job page after {max_attempts} attempts. Cannot apply for the job.")
            raise Exception(
                f"Redirected to AIHawk Premium page and failed to return after {max_attempts} attempts. Job application aborted.")
            
    def apply_to_job(self, job: Any) -> None:
        """
        Starts the process of applying to a job.
        :param job: A job object with the job details.
        :return: None
        """
        logger.debug(f"Applying to job: {job}")
        try:
            self.job_apply(job)
            logger.info(f"Successfully applied to job: {job.title}")
        except Exception as e:
            logger.error(f"Failed to apply to job: {job.title}, error: {str(e)}")
            raise e

    def _find_easy_apply_button(self, job: Any) -> WebElement:
        logger.debug("Searching for 'Easy Apply' button")
        attempt = 0

        search_methods = [
            {
                'description': "find all 'Easy Apply' buttons using find_elements",
                'find_elements': True,
                'xpath': '//button[contains(@class, "jobs-apply-button") and contains(., "Easy Apply")]'
            },
            {
                'description': "button or anchor with data-view-name='job-apply-button'",
                'xpath': '//*[@data-view-name="job-apply-button" and contains(., "Easy Apply")]'
            },
            {
                'description': "'aria-label' containing 'Easy Apply to'",
                'xpath': '//*[contains(@aria-label, "Easy Apply to")]'
            },
            {
                'description': "text search for 'Easy Apply'",
                'xpath': '//*[contains(text(), "Easy Apply") or contains(text(), "Apply now")]'
            }
        ]

        while attempt < 2:

            self.check_for_premium_redirect(job)
            self._scroll_page()

            for method in search_methods:
                try:
                    logger.debug(f"Attempting search using {method['description']}")

                    if method.get('find_elements'):

                        buttons = self.driver.find_elements(By.XPATH, method['xpath'])
                        if buttons:
                            for index, button in enumerate(buttons):
                                try:

                                    WebDriverWait(self.driver, 10).until(EC.visibility_of(button))
                                    WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(button))
                                    logger.debug(f"Found 'Easy Apply' button {index + 1}, attempting to click")
                                    return button
                                except Exception as e:
                                    logger.warning(f"Button {index + 1} found but not clickable: {e}")
                        else:
                            raise TimeoutException("No 'Easy Apply' buttons found")
                    else:

                        button = WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, method['xpath']))
                        )
                        WebDriverWait(self.driver, 10).until(EC.visibility_of(button))
                        WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(button))
                        logger.debug("Found 'Easy Apply' button, attempting to click")
                        return button

                except TimeoutException:
                    logger.warning(f"Timeout during search using {method['description']}")
                except Exception as e:
                    logger.warning(
                        f"Failed to click 'Easy Apply' button using {method['description']} on attempt {attempt + 1}: {e}")

            self.check_for_premium_redirect(job)

            if attempt == 0:
                logger.debug("Refreshing page to retry finding 'Easy Apply' button")
                self.driver.refresh()
                time.sleep(random.randint(3, 5))
            attempt += 1

        page_source = self.driver.page_source
        logger.error(f"No clickable 'Easy Apply' button found after 2 attempts. Page source:\n{page_source}")
        raise Exception("No clickable 'Easy Apply' button found")

    def _get_job_description(self) -> str:
        logger.debug("Getting job description")
        try:
            try:
                # Try multiple possible "See more" buttons, including the new data-testid one
                see_more_button = self.driver.find_element(By.XPATH,
                                                           '//button[@data-testid="expandable-text-button"] | //button[contains(@aria-label, "see more description")] | //button[contains(@class, "jobs-description__footer-button")]')
                actions = ActionChains(self.driver)
                actions.move_to_element(see_more_button).click().perform()
                time.sleep(2)
            except NoSuchElementException:
                logger.debug("See more button not found, skipping")

            description_selectors = [
                (By.XPATH, '//*[@data-testid="expandable-text-box"]'),
                (By.CLASS_NAME, 'jobs-description-content__text'),
                (By.CLASS_NAME, 'job-details-about-the-job-module__description'),
                (By.ID, 'job-details'),
                (By.CLASS_NAME, 'jobs-description'),
                (By.CLASS_NAME, 'show-more-less-html__markup')
            ]

            for selector_type, selector_value in description_selectors:
                try:
                    description = self.driver.find_element(selector_type, selector_value).text
                    if description.strip():
                        logger.debug(f"Job description retrieved successfully using {selector_value}")
                        return description
                except NoSuchElementException:
                    continue

            raise NoSuchElementException("None of the job description selectors matched")

        except Exception:
            tb_str = traceback.format_exc()
            logger.error(f"Error getting Job description: {tb_str}")
            raise Exception(f"Job description not found: \nTraceback:\n{tb_str}")

    def _get_job_recruiter(self):
        logger.debug("Getting job recruiter information")
        try:
            # Try to find the hiring team section
            hiring_team_selectors = [
                '//h2[text()="Meet the hiring team"]',
                '//h2[contains(., "hiring team")]',
                '//div[contains(@class, "hiring-team")]'
            ]
            
            hiring_team_section = None
            for selector in hiring_team_selectors:
                try:
                    hiring_team_section = self.driver.find_element(By.XPATH, selector)
                    break
                except NoSuchElementException:
                    continue

            if hiring_team_section:
                recruiter_elements = hiring_team_section.find_elements(By.XPATH,
                                                                       './/following::a[contains(@href, "linkedin.com/in/")]')

                if recruiter_elements:
                    recruiter_link = recruiter_elements[0].get_attribute('href')
                    logger.debug(f"Job recruiter link retrieved successfully: {recruiter_link}")
                    return recruiter_link
            
            logger.debug("No recruiter link found")
            return ""
        except Exception as e:
            logger.warning(f"Failed to retrieve recruiter information: {e}")
            return ""

    def _scroll_page(self) -> None:
        logger.debug("Scrolling the page")
        try:
            scrollable_element = self.driver.find_element(By.TAG_NAME, 'html')
            utils.scroll_slow(self.driver, scrollable_element, step=300, reverse=False)
            utils.scroll_slow(self.driver, scrollable_element, step=300, reverse=True)
        except Exception as e:
            logger.warning(f"Failed to scroll page: {e}")

    def job_apply(self, job: Any):
        # Initialize job-specific logging
        self.job_log_path = None
        if self.output_dir:
            log_dir = self.output_dir / "job_logs"
            os.makedirs(log_dir, exist_ok=True)
            safe_name = re.sub(r'[^a-zA-Z0-9]', '_', f"{job.company}_{job.title}")
            self.job_log_path = log_dir / f"{safe_name}_{int(time.time())}.log"
        
        self._log_job("--- NEW APPLICATION START ---")
        self._log_job(f"Role: {job.title}")
        self._log_job(f"Company: {job.company}")
        self._log_job(f"Link: {job.link}")

        try:
            self.driver.get(job.link)
            time.sleep(random.uniform(3, 5))
            self.check_for_premium_redirect(job)

            self.driver.execute_script("document.activeElement.blur();")
            easy_apply_button = self._find_easy_apply_button(job)
            
            job_description = self._get_job_description()
            job.set_job_description(job_description)

            if self.always_tailor_resume:
                self._prepare_tailored_resume(job)
                self._log_job(f"Tailored Resume generated: {job.pdf_path}")

            recruiter_link = self._get_job_recruiter()
            job.set_recruiter_link(recruiter_link)

            self.current_job = job
            self._click_element(easy_apply_button)
            time.sleep(3) 

            self.gpt_answerer.set_job(job)
            self._fill_application_form(job)
            
            self._log_job("SUCCESS: Application submitted automatically.")

        except Exception as e:
            tb_str = traceback.format_exc()
            self._log_job("ABANDONED: Job failed or timed out. Leaving tab open for manual review.")
            self._log_job(f"Error Context: {str(e)}")
            self._log_job(f"Traceback Summary: {tb_str.splitlines()[-1]}")
            
            logger.error(f"Timeout/Error on {job.company}. Opening fresh tab for next job...")
            
            # Open a fresh tab and switch to it, leaving the current one open for the user
            try:
                self.driver.execute_script("window.open('');")
                self.driver.switch_to.window(self.driver.window_handles[-1])
                logger.debug("Switched to new empty tab.")
            except Exception as win_err:
                logger.error(f"Failed to open new tab: {win_err}")
            
            # We don't re-raise here so the outer loop in JobManager can continue to the next job
            return

    def _log_job(self, message: str) -> None:
        """Writes a message to both the main logger and the job-specific log file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_msg = f"[{timestamp}] {message}"
        logger.debug(full_msg)
        if self.job_log_path:
            with open(self.job_log_path, "a", encoding="utf-8") as f:
                f.write(full_msg + "\n")

    def _fill_application_form(self, job):
        self._log_job("Entering form-filling loop...")
        start_time = time.time()
        timeout_seconds = 60 # ONE MINUTE LIMIT
        
        while True:
            # Check for timeout
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                raise TimeoutError(f"Form filling exceeded {timeout_seconds}s limit.")

            self.fill_up(job)
            if self._next_or_submit():
                break

    def _next_or_submit(self):
        self._log_progress()
        logger.debug("Clicking 'Next' / 'Review' / 'Submit' button")
        
        try:
            # We use CSS selectors as much as possible for Shadow DOM support
            next_button_selectors = [
                (By.CSS_SELECTOR, "button[data-easy-apply-next-button]"),
                (By.CSS_SELECTOR, "button[data-live-test-easy-apply-next-button]"),
                (By.CSS_SELECTOR, "button[data-easy-apply-review-button]"),
                (By.CSS_SELECTOR, "button[data-live-test-easy-apply-review-button]"),
                (By.CSS_SELECTOR, "button[aria-label*='Review']"),
                (By.CSS_SELECTOR, "button[aria-label*='Submit']"),
                (By.CSS_SELECTOR, "button[aria-label*='Continue']"),
                (By.CSS_SELECTOR, "button.artdeco-button--primary"),
                (By.XPATH, "//button[contains(., 'Review')]"),
                (By.XPATH, "//button[contains(., 'Next') or contains(., 'Submit') or contains(., 'Continue')]")
            ]
            
            next_button, _ = self._find_element_recursive(next_button_selectors, timeout=10)

            if not next_button:
                self._save_page_source("failed_next_button")
                raise Exception("Next/Review/Submit button not found")
            
            button_text = (next_button.text or next_button.get_attribute("aria-label") or "").strip()
            button_text_lower = button_text.lower()
            is_submit = any(t in button_text_lower for t in ['submit application', 'submit', 'finish', 'send'])
            
            if is_submit:
                logger.info("Final Step: Submit detected.")
                self._unfollow_company()
                time.sleep(random.uniform(1.5, 2.5))
            
            # Safe JS click
            logger.info(f"Action: Clicking '{button_text}' button")
            self._click_element(next_button)

            if is_submit:
                 time.sleep(random.uniform(3.0, 5.0))
                 return True

            # Page transition wait
            wait_time = 5.0 if 'review' in button_text_lower else 3.0
            time.sleep(random.uniform(wait_time, wait_time + 2.0))
            
            # Verify if we actually moved or if there are errors
            self._check_for_errors()
        except Exception as e:
            logger.error(f"Failed to click Next/Submit button: {e}")
            raise

    def _log_progress(self):
        try:
            # Try to find the progress percentage in the modal
            progress_selectors = [
                (By.CSS_SELECTOR, "span[aria-label*='progress']"),
                (By.CLASS_NAME, "artdeco-completeness-meter-linear__progress-element"),
                (By.XPATH, "//*[contains(@aria-label, 'progress is at')]")
            ]
            
            for s_type, s_val in progress_selectors:
                elements = self.driver.find_elements(s_type, s_val)
                for el in elements:
                    text = el.text or el.get_attribute("aria-label") or ""
                    if "%" in text:
                        logger.info(f"Application Progress: {text.strip()}")
                        return
        except Exception:
            pass

    def _click_element(self, element: WebElement) -> None:
        """
        Robustly clicks an element using JavaScript to bypass 'element click intercepted'.
        """
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.2)
            self.driver.execute_script("arguments[0].click();", element)
        except Exception as e:
            logger.warning(f"JS click failed, falling back to standard click: {e}")
            element.click()

    def _unfollow_company(self) -> None:
        try:
            follow_checkbox = self.driver.find_element(
                By.XPATH, "//label[contains(.,'to stay up to date with their page.')] | //input[contains(@id, 'follow-company-checkbox')]" )
            
            # Check actual input state
            is_checked = False
            try:
                if follow_checkbox.tag_name == 'input':
                    is_checked = follow_checkbox.is_selected()
                else:
                    input_el = follow_checkbox.find_element(By.XPATH, ".//input")
                    is_checked = input_el.is_selected()
            except Exception:
                pass

            if is_checked:
                logger.debug("Unfollowing company...")
                self._click_element(follow_checkbox)
        except Exception:
            pass

    def _check_for_errors(self) -> None:
        logger.trace("Checking for form validation errors...")
        error_selectors = [
            (By.CLASS_NAME, 'artdeco-inline-feedback--error'),
            (By.CLASS_NAME, 'fb-dash-form-element__error-messages'),
            (By.CLASS_NAME, 'fb-dash-form-element__error-field'),
            (By.XPATH, "//*[contains(@class, 'error') and (contains(text(), 'required') or contains(text(), 'Select an option'))]")
        ]
        
        found_errors = []
        for s_type, s_val in error_selectors:
            errors = self.driver.find_elements(s_type, s_val)
            for e in errors:
                if e.is_displayed() and e.text.strip():
                    found_errors.append(e.text.strip())
        
        if found_errors:
            logger.warning(f"LinkedIn Form Errors Detected: {found_errors}")
            # We don't raise here anymore to allow the fill_up loop to try and fix them
            return

    def _handle_terms_of_service(self, element: WebElement) -> bool:
        """
        Handles Privacy Policy, Terms of Service, and Accuracy agreements.
        Supports both checkboxes and dropdowns (Yes/No).
        """
        section_text = element.text.lower()
        agreement_keywords = ['privacy policy', 'terms of service', 'terms of use', 'acknowledge', 'agree', 'accurate', 'honesty', 'accuracy']
        
        if not any(kw in section_text for kw in agreement_keywords):
            return False

        # 1. Handle Dropdowns (Modern LinkedIn Style - Yes/No)
        # We check for dropdowns FIRST because labels often wrap dropdowns
        dropdowns = element.find_elements(By.TAG_NAME, 'select')
        if not dropdowns:
            dropdowns = element.find_elements(By.CSS_SELECTOR, '[data-test-text-entity-list-form-select]')
            
        if dropdowns:
            dropdown = dropdowns[0]
            logger.info("Action: Selecting 'Yes' for agreement dropdown")
            self._select_dropdown_option(dropdown, "Yes")
            return True

        # 2. Handle Checkboxes (Traditional)
        # Look for labels that are specifically associated with an input
        labels = element.find_elements(By.TAG_NAME, 'label')
        for label in labels:
            text = label.text.lower()
            if any(term in text for term in agreement_keywords):
                try:
                    # Check if this label is actually a checkbox/radio
                    input_el = None
                    input_id = label.get_attribute("for")
                    if input_id:
                        input_el = self.driver.find_element(By.ID, input_id)
                    else:
                        # Check inside the label
                        internal_inputs = label.find_elements(By.XPATH, ".//input[@type='checkbox' or @type='radio']")
                        if internal_inputs:
                            input_el = internal_inputs[0]
                    
                    if input_el:
                        if not input_el.is_selected():
                            self._click_element(label)
                            logger.info(f"Action: Accepted agreement checkbox ('{text[:30]}...')")
                        else:
                            logger.debug(f"Checkbox '{text[:20]}...' already checked.")
                        return True
                except Exception:
                    pass

        return False

    def _discard_application(self) -> None:
        logger.debug("Discarding application")
        try:
            # Try multiple close button selectors
            close_selectors = [
                (By.CLASS_NAME, 'artdeco-modal__dismiss'),
                (By.XPATH, '//button[@aria-label="Dismiss"]'),
                (By.XPATH, '//li-icon[@type="cancel-icon"]/..')
            ]
            
            close_btn = None
            for selector_type, selector_value in close_selectors:
                try:
                    close_btn = self.driver.find_element(selector_type, selector_value)
                    if close_btn.is_displayed():
                        break
                except NoSuchElementException:
                    continue
            
            if close_btn:
                self._click_element(close_btn)
                time.sleep(random.uniform(2, 3))
                # Confirm discard
                confirm_selectors = [
                    (By.CLASS_NAME, 'artdeco-modal__confirm-dialog-btn'),
                    (By.XPATH, '//button[contains(., "Discard")]')
                ]
                for selector_type, selector_value in confirm_selectors:
                    try:
                        confirm_btn = self.driver.find_element(selector_type, selector_value)
                        self._click_element(confirm_btn)
                        break
                    except NoSuchElementException:
                        continue
                time.sleep(random.uniform(2, 3))
        except Exception as e:
            logger.warning(f"Failed to discard application: {e}")

    def _find_element_recursive(self, locators, timeout=10):
        """
        Deep search for an element across all nested iframes and Shadow DOMs.
        """
        end_time = time.time() + timeout
        while time.time() < end_time:
            self.driver.switch_to.default_content()
            
            # 1. Try standard iframe search
            result, handle = self._search_frames(locators)
            if result:
                return result, handle
            
            # 2. Try Shadow DOM search (new)
            # Only works for CSS-compatible locators
            self.driver.switch_to.default_content()
            logger.debug("Falling back to Shadow DOM scan...")
            result = self._search_shadow_dom(locators)
            if result:
                return result, self.driver.current_window_handle
            
            time.sleep(1)
        return None, None

    def _search_shadow_dom(self, locators):
        """
        Searches for an element inside Shadow DOMs using JS.
        Only works with CSS-compatible locators (ID, Class, CSS Selector, Tag Name).
        """
        logger.trace("Initiating deep Shadow DOM traversal via JS")
        script = """
        function findInShadows(selectors) {
            function traverse(root) {
                // Check selectors
                for (let selector of selectors) {
                    try {
                        let el = root.querySelector(selector);
                        if (el && (el.offsetWidth > 0 || el.offsetHeight > 0)) return el;
                    } catch(e) {}
                }
                
                // Traverse children for shadow roots
                // We use a TreeWalker to efficiently traverse the DOM
                let walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
                while (walker.nextNode()) {
                    let node = walker.currentNode;
                    if (node.shadowRoot) {
                        let found = traverse(node.shadowRoot);
                        if (found) return found;
                    }
                }
                return null;
            }
            return traverse(document.body);
        }
        return findInShadows(arguments[0]);
        """
        
        css_selectors = []
        for by, val in locators:
            if by == By.CSS_SELECTOR:
                css_selectors.append(val)
            elif by == By.CLASS_NAME:
                css_selectors.append(f".{val.replace(' ', '.')}")
            elif by == By.TAG_NAME:
                css_selectors.append(val)
            elif by == By.ID:
                css_selectors.append(f"#{val}")
            # XPath is not supported in this JS snippet
        
        if css_selectors:
            try:
                element = self.driver.execute_script(script, css_selectors)
                if element:
                    logger.info(f"Found element in Shadow DOM using selectors: {css_selectors}")
                    return element
            except Exception as e:
                logger.debug(f"Shadow DOM search failed: {e}")
        
        return None

    def _search_frames(self, locators):
        # 1. Check current context (Standard)
        for selector_type, selector_value in locators:
            elements = self.driver.find_elements(selector_type, selector_value)
            for element in elements:
                try:
                    if element.is_displayed():
                        return element, self.driver.current_window_handle
                except Exception:
                    continue
        
        # 2. Check current context (Shadow DOM)
        shadow_result = self._search_shadow_dom(locators)
        if shadow_result:
            return shadow_result, self.driver.current_window_handle

        # 3. Recursively check iframes
        iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        for i in range(len(iframes)):
            try:
                # Refresh iframes list because DOM might have changed
                current_iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                if i >= len(current_iframes):
                    break
                
                logger.trace(f"Entering iframe {i} for recursive element search")
                self.driver.switch_to.frame(current_iframes[i])
                result, handle = self._search_frames(locators)
                if result:
                    return result, handle
                self.driver.switch_to.parent_frame()
            except Exception:
                try:
                    self.driver.switch_to.parent_frame()
                except Exception:
                    self.driver.switch_to.default_content()
                continue
        return None, None


    def _save_page_source(self, prefix: str) -> None:
        try:
            debug_dir = 'debug_html'
            os.makedirs(debug_dir, exist_ok=True)
            timestamp = int(time.time())
            filename = f"{prefix}_{timestamp}.html"
            filepath = os.path.join(debug_dir, filename)
            with open(filepath, "w", encoding='utf-8') as f:
                f.write(self.driver.page_source)
            logger.info(f"Saved page source to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save page source: {e}")

    def fill_up(self, job) -> None:
        logger.debug(f"Filling up form sections for job: {job}")

        try:
            # Always reset to default content to handle iframe reloads/navigation
            self.driver.switch_to.default_content()

            form_selectors = [
                (By.CLASS_NAME, 'jobs-easy-apply-modal__content'),
                (By.CLASS_NAME, 'jobs-easy-apply-content'),
                (By.CLASS_NAME, 'jobs-easy-apply-form-container'),
                (By.CLASS_NAME, 'artdeco-modal__content'),
                (By.CSS_SELECTOR, 'div.artdeco-modal__content'),
                (By.CSS_SELECTOR, 'div.ph5 form'),
                (By.XPATH, '//div[contains(@class, "jobs-easy-apply-content")]'),
                (By.XPATH, '//div[contains(@class, "artdeco-modal__content")]'),
                (By.TAG_NAME, 'form')
            ]
            
            # Modal might be animating. Retry a few times.
            easy_apply_content = None
            for attempt in range(3):
                easy_apply_content, context = self._find_element_recursive(form_selectors, timeout=5)
                if easy_apply_content:
                    break
                time.sleep(1)

            if not easy_apply_content:
                # If we are on the "Review" page, there might not be a 'form' but the Next/Submit button is still there.
                # We shouldn't necessarily fail here, just log and return.
                logger.info("Could not find form content. This might be a review or confirmation page.")
                return
            
            logger.debug(f"Found form content in context: {context}")

            # Find all form elements within the discovered context
            form_elements = easy_apply_content.find_elements(By.XPATH, './/*[@data-test-form-element=""] | .//div[contains(@class, "pb4")] | .//div[contains(@class, "jobs-easy-apply-form-section")] | .//div[contains(@class, "fb-dash-form-element")]')
            
            if not form_elements:
                logger.debug("No standard form elements found, trying to find all inputs/selects")
                form_elements = easy_apply_content.find_elements(By.XPATH, './/div[.//input or .//select or .//textarea]')

            if not form_elements:
                 logger.debug("No form elements found in the current container.")
                 return

            for element in form_elements:
                self._process_form_element(element, job)
        except Exception as e:
            logger.error(f"Error in fill_up: {e}")

    def _process_form_element(self, element: WebElement, job) -> None:
        logger.debug("Processing form element")
        if self._is_upload_field(element):
            self._handle_upload_fields(element, job)
        else:
            self._fill_additional_questions(element)

    def _handle_dropdown_fields(self, element: WebElement) -> bool:
        logger.trace("Checking for dropdown fields in section")

        try:
            dropdowns = element.find_elements(By.TAG_NAME, 'select')
            if not dropdowns:
                dropdowns = element.find_elements(By.CSS_SELECTOR, '[data-test-text-entity-list-form-select]')
            
            if not dropdowns:
                return False
                
            dropdown = dropdowns[0]
            select = Select(dropdown)
            
            # Try to find label in current element or parent
            label_text = ""
            try:
                label_text = element.find_element(By.TAG_NAME, 'label').text.lower()
            except Exception:
                try:
                    label_text = element.find_element(By.XPATH, '..//label').text.lower()
                except Exception:
                    label_text = "unknown dropdown"

            # Check for error state (very aggressive check)
            has_error = "error" in (dropdown.get_attribute("class") or "").lower() or \
                        "error" in (element.get_attribute("class") or "").lower()

            logger.info(f"Processing Dropdown: '{label_text.strip()}'" + (" (fixing error)" if has_error else ""))

            # Optimization: Check if already filled with a valid value
            current_selection = select.first_selected_option.text
            if current_selection and "select an option" not in current_selection.lower() and not has_error:
                logger.debug(f"Dropdown '{label_text.strip()}' already filled with: {current_selection}")
                return True

            dropdown_id = (dropdown.get_attribute('id') or "").lower()
            
            if 'phonenumber-country' in dropdown_id:
                country = None
                try:
                    # Attempt to retrieve country from resume object
                    if hasattr(self.resume_generator_manager, 'get_resume_country'):
                         country = self.resume_generator_manager.get_resume_country()
                    elif hasattr(self.resume_generator_manager, 'resume_generator'):
                         rg = self.resume_generator_manager.resume_generator
                         if hasattr(rg, 'resume_object'):
                             ro = rg.resume_object
                             if hasattr(ro, 'personal_information') and ro.personal_information:
                                 country = ro.personal_information.country
                except Exception as ex:
                    logger.debug(f"Could not retrieve resume country: {ex}")

                if country:
                    try:
                        select.select_by_value(country)
                        logger.debug(f"Selected phone country: {country}")
                        return True
                    except NoSuchElementException:
                        logger.warning(f"Country {country} not found in dropdown options")

            options = [option.text for option in select.options]
            logger.debug(f"Available options for '{label_text.strip()}': {options}")

            question_text = label_text
            existing_answer = None
            for item in self.all_data:
                if self._sanitize_text(question_text) in item['question'] and item['type'] == 'dropdown':
                    existing_answer = item['answer']
                    break

            if existing_answer:
                logger.debug(f"Using cached answer for '{question_text.strip()}': {existing_answer}")
            else:
                logger.info(f"Querying LLM for dropdown: '{question_text.strip()}'")
                existing_answer = self.gpt_answerer.answer_question_from_options(question_text, options)
                self._save_questions_to_json({'type': 'dropdown', 'question': question_text, 'answer': existing_answer})

            # Exact or fuzzy match for options
            best_match = self.gpt_answerer.find_best_match(existing_answer, options)
            self._select_dropdown_option(dropdown, best_match)
            return True
        except Exception as e:
            logger.warning(f"Error in _handle_dropdown_fields: {e}")
            return False

    def _is_upload_field(self, element: WebElement) -> bool:
        is_upload = bool(element.find_elements(By.XPATH, ".//input[@type='file']"))
        return is_upload

    def _handle_upload_fields(self, element: WebElement, job) -> None:
        logger.info("Processing Upload Field")

        try:
            # Try to show all resumes if some are hidden
            show_more_button = self.driver.find_elements(By.XPATH, "//button[contains(@aria-label, 'Show more resumes')]")
            if show_more_button:
                self._click_element(show_more_button[0])
                logger.debug("Expanded resume list")
        except Exception:
            pass

        # Find all file inputs within the discovered context or globally if section is small
        file_inputs = element.find_elements(By.XPATH, ".//input[@type='file']")
        if not file_inputs:
            # Fallback to searching the whole modal context if the section didn't contain the input
            file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")

        for file_input in file_inputs:
            try:
                # Try to get context from the label or parent container
                container_text = ""
                try:
                    # Look for a label or header nearby
                    container_text = file_input.find_element(By.XPATH, "./preceding-sibling::label").text.lower()
                except Exception:
                    try:
                        container_text = file_input.find_element(By.XPATH, "./ancestor::div[1]").text.lower()
                    except Exception:
                        container_text = "upload"

                # Ask LLM if this is for resume or cover letter
                field_type = self.gpt_answerer.resume_or_cover(container_text)
                
                # Make input visible so Selenium can interact with it
                self.driver.execute_script("arguments[0].classList.remove('hidden'); arguments[0].style.display='block'; arguments[0].style.visibility='visible';", file_input)

                if 'resume' in field_type:
                    if self.resume_path is not None and self.resume_path.resolve().is_file() and not self.always_tailor_resume:
                        logger.info(f"Action: Uploading Existing Resume from {self.resume_path.name}")
                        file_input.send_keys(str(self.resume_path.resolve()))
                    else:
                        logger.info("Action: Generating and Uploading Tailored Resume")
                        self._create_and_upload_resume(file_input, job)
                
                elif 'cover' in field_type:
                    logger.info("Action: Generating and Uploading Tailored Cover Letter")
                    self._create_and_upload_cover_letter(file_input, job)
            except Exception as e:
                logger.warning(f"Failed to handle specific upload field: {e}")

        logger.debug("Finished processing upload fields")

    def _prepare_tailored_resume(self, job: Any) -> None:
        logger.info(f"Action: Generating tailored resume for {job.company}...")
        
        # Determine save directory
        resumes_dir = self.output_dir / "resumes" if self.output_dir else Path("generated_cv")
        os.makedirs(resumes_dir, exist_ok=True)
        
        # Create a clean filename
        safe_company = re.sub(r'[^a-zA-Z0-9]', '_', job.company)
        safe_title = re.sub(r'[^a-zA-Z0-9]', '_', job.title)
        timestamp = int(time.time())
        file_path_pdf = resumes_dir / f"Resume_{safe_company}_{safe_title}_{timestamp}.pdf"

        try:
            resume_pdf_base64 = self.resume_generator_manager.pdf_base64(job_description_text=job.description)
            with open(file_path_pdf, "wb") as f:
                f.write(base64.b64decode(resume_pdf_base64))
            
            job.pdf_path = str(file_path_pdf.absolute())
            logger.info(f"Resume saved successfully to: {file_path_pdf}")
        except Exception as e:
            logger.error(f"Failed to generate tailored resume: {e}")
            # We don't raise here, the bot will try to use the default resume later if this fails

    def _create_and_upload_resume(self, file_input: WebElement, job: Any) -> None:
        # If we already generated a tailored one, use it
        if job.pdf_path and os.path.exists(job.pdf_path):
            logger.info("Action: Uploading pre-generated tailored resume")
            file_input.send_keys(job.pdf_path)
            time.sleep(2)
            return

        # Fallback to default logic if tailoring failed or was skipped
        logger.debug("No pre-generated resume found, checking for default...")
        if self.resume_path is not None and self.resume_path.resolve().is_file():
            logger.info("Action: Uploading default resume")
            file_input.send_keys(str(self.resume_path.resolve()))
            time.sleep(2)
        else:
            logger.warning("No resume available to upload (neither tailored nor default).")

    def _create_and_upload_cover_letter(self, element: WebElement, job) -> None:
        logger.debug("Starting the process of creating and uploading cover letter.")

        cover_letter_text = self.gpt_answerer.answer_question_textual_wide_range("Write a cover letter")

        folder_path = 'generated_cv'

        try:

            if not os.path.exists(folder_path):
                logger.debug(f"Creating directory at path: {folder_path}")
            os.makedirs(folder_path, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create directory: {folder_path}. Error: {e}")
            raise

        while True:
            try:
                timestamp = int(time.time())
                file_path_pdf = os.path.join(folder_path, f"Cover_Letter_{timestamp}.pdf")
                logger.debug(f"Generated file path for cover letter: {file_path_pdf}")

                c = canvas.Canvas(file_path_pdf, pagesize=A4)
                page_width, page_height = A4
                text_object = c.beginText(50, page_height - 50)
                text_object.setFont("Helvetica", 12)

                max_width = page_width - 100
                bottom_margin = 50

                def split_text_by_width(text, font, font_size, max_width):
                    wrapped_lines = []
                    for line in text.splitlines():

                        if stringWidth(line, font, font_size) > max_width:
                            words = line.split()
                            new_line = ""
                            for word in words:
                                if stringWidth(new_line + word + " ", font, font_size) <= max_width:
                                    new_line += word + " "
                                else:
                                    wrapped_lines.append(new_line.strip())
                                    new_line = word + " "
                            wrapped_lines.append(new_line.strip())
                        else:
                            wrapped_lines.append(line)
                    return wrapped_lines

                lines = split_text_by_width(cover_letter_text, "Helvetica", 12, max_width)

                for line in lines:
                    text_height = text_object.getY()
                    if text_height > bottom_margin:
                        text_object.textLine(line)
                    else:

                        c.drawText(text_object)
                        c.showPage()
                        text_object = c.beginText(50, page_height - 50)
                        text_object.setFont("Helvetica", 12)
                        text_object.textLine(line)

                c.drawText(text_object)
                c.save()
                logger.debug(f"Cover letter successfully generated and saved to: {file_path_pdf}")

                break
            except Exception as e:
                logger.error(f"Failed to generate cover letter: {e}")
                tb_str = traceback.format_exc()
                logger.error(f"Traceback: {tb_str}")
                raise

        file_size = os.path.getsize(file_path_pdf)
        max_file_size = 2 * 1024 * 1024  # 2 MB
        logger.debug(f"Cover letter file size: {file_size} bytes")
        if file_size > max_file_size:
            logger.error(f"Cover letter file size exceeds 2 MB: {file_size} bytes")
            raise ValueError("Cover letter file size exceeds the maximum limit of 2 MB.")

        allowed_extensions = {'.pdf', '.doc', '.docx'}
        file_extension = os.path.splitext(file_path_pdf)[1].lower()
        logger.debug(f"Cover letter file extension: {file_extension}")
        if file_extension not in allowed_extensions:
            logger.error(f"Invalid cover letter file format: {file_extension}")
            raise ValueError("Cover letter file format is not allowed. Only PDF, DOC, and DOCX formats are supported.")

        try:

            logger.debug(f"Uploading cover letter from path: {file_path_pdf}")
            element.send_keys(os.path.abspath(file_path_pdf))
            job.cover_letter_path = os.path.abspath(file_path_pdf)
            time.sleep(2)
            logger.debug(f"Cover letter created and uploaded successfully: {file_path_pdf}")
        except Exception:
            tb_str = traceback.format_exc()
            logger.error(f"Cover letter upload failed: {tb_str}")
            raise Exception(f"Upload failed: \nTraceback:\n{tb_str}")

    def _fill_additional_questions(self, element=None) -> None:
        logger.debug("Filling additional questions")
        if element:
            form_sections = [element]
        else:
            form_sections = self.driver.find_elements(By.CLASS_NAME, 'jobs-easy-apply-form-section__grouping')
        
        for section in form_sections:
            self._process_form_section(section)

    def _process_form_section(self, section: WebElement) -> None:
        try:
            # Audit log the section text for visibility
            section_text = section.text.split('\n')[0][:50]
            self._log_job(f"Scanning section: '{section_text}...'" )

            if self._handle_terms_of_service(section):
                return
            if self._handle_dropdown_fields(section):
                return
            if self._find_and_handle_radio_question(section):
                return
            if self._find_and_handle_dropdown_question(section):
                return
            if self._find_and_handle_textbox_question(section):
                return
            if self._find_and_handle_date_question(section):
                return
        except Exception as e:
            self._log_job(f"Warning: Section processing error: {e}")
            logger.warning(f"Error processing form section: {e}")

    def _find_and_handle_radio_question(self, section: WebElement) -> bool:
        try:
            question_elements = section.find_elements(By.CLASS_NAME, 'jobs-easy-apply-form-element')
            if not question_elements:
                return False
            question = question_elements[0]
            radios = question.find_elements(By.CLASS_NAME, 'fb-text-selectable__option')
            if radios:
                question_text = section.text.split('\n')[0].lower()
                logger.info(f"Processing Radio Question: '{question_text.strip()}'")
                
                options = [radio.text.lower() for radio in radios]

                existing_answer = None
                for item in self.all_data:
                    if self._sanitize_text(question_text) in item['question'] and item['type'] == 'radio':
                        existing_answer = item
                        break
                
                if existing_answer:
                    logger.debug(f"Using cached radio answer for '{question_text.strip()}': {existing_answer['answer']}")
                    self._select_radio(radios, existing_answer['answer'])
                    return True

                answer = self.gpt_answerer.answer_question_from_options(question_text, options)
                self._save_questions_to_json({'type': 'radio', 'question': question_text, 'answer': answer})
                self._select_radio(radios, answer)
                return True
        except Exception:
            pass
        return False

    def _find_and_handle_textbox_question(self, section: WebElement) -> bool:
        # We only want actual text-entry fields. 
        # Exclude radios, checkboxes, and hidden fields which often get misidentified.
        all_inputs = section.find_elements(By.TAG_NAME, 'input') + section.find_elements(By.TAG_NAME, 'textarea')
        text_fields = []
        for inp in all_inputs:
            itype = (inp.get_attribute('type') or 'text').lower()
            # Explicitly exclude non-text inputs
            if itype in ['radio', 'checkbox', 'file', 'hidden', 'submit', 'button']:
                continue
            if itype in ['text', 'number', 'email', 'tel', 'password'] or inp.tag_name == 'textarea':
                text_fields.append(inp)

        if text_fields:
            text_field = text_fields[0]
            
            # Try multiple label selectors
            label_selectors = [
                (By.TAG_NAME, 'label'),
                (By.XPATH, './/*[contains(@class, "label")]'),
                (By.XPATH, './/span[@aria-hidden="true"]')
            ]
            
            question_text = ""
            for s_type, s_val in label_selectors:
                try:
                    question_text = section.find_element(s_type, s_val).text.strip()
                    if question_text:
                        break
                except Exception:
                    continue
            
            if not question_text:
                question_text = "unknown text field"

            # Check for error state
            has_error = "error" in (section.get_attribute("class") or "").lower() or \
                        "error" in (text_field.get_attribute("class") or "").lower()

            # Optimization: Check if already filled
            current_val = text_field.get_attribute('value')
            if current_val and current_val.strip() and not has_error:
                logger.debug(f"Textbox '{question_text.strip()}' already filled with: {current_val}")
                return True

            logger.info(f"Processing Textbox: '{question_text.strip()}'" + (" (fixing error)" if has_error else ""))

            is_numeric = self._is_numeric_field(text_field)
            question_type = 'numeric' if is_numeric else 'textbox'

            # Check if it's a cover letter field (case-insensitive)
            is_cover_letter = 'cover letter' in question_text.lower()

            # Look for existing answer if it's not a cover letter field
            existing_answer = None
            if not is_cover_letter:
                for item in self.all_data:
                    if self._sanitize_text(item['question']) == self._sanitize_text(question_text) and item.get('type') == question_type:
                        existing_answer = item['answer']
                        break

            if existing_answer and not is_cover_letter:
                answer = existing_answer
                logger.debug(f"Using cached answer for '{question_text.strip()}': {answer}")
            else:
                if is_numeric:
                    answer = self.gpt_answerer.answer_question_numeric(question_text)
                else:
                    answer = self.gpt_answerer.answer_question_textual_wide_range(question_text)

            self._enter_text(text_field, answer)

            # Save non-cover letter answers
            if not is_cover_letter:
                self._save_questions_to_json({'type': question_type, 'question': question_text, 'answer': answer})

            time.sleep(1)
            text_field.send_keys(Keys.ARROW_DOWN)
            text_field.send_keys(Keys.ENTER)
            return True

        return False

    def _find_and_handle_date_question(self, section: WebElement) -> bool:
        date_fields = section.find_elements(By.CLASS_NAME, 'artdeco-datepicker__input ')
        if date_fields:
            date_field = date_fields[0]
            question_text = section.text.split('\n')[0].lower()
            logger.info(f"Processing Date Field: '{question_text.strip()}'")
            
            answer_date = self.gpt_answerer.answer_question_date()
            answer_text = answer_date.strftime("%Y-%m-%d")

            existing_answer = None
            for item in self.all_data:
                if self._sanitize_text(question_text) in item['question'] and item['type'] == 'date':
                    existing_answer = item
                    break
            if existing_answer:
                logger.debug(f"Using cached date for '{question_text.strip()}': {existing_answer['answer']}")
                self._enter_text(date_field, existing_answer['answer'])
                return True

            self._save_questions_to_json({'type': 'date', 'question': question_text, 'answer': answer_text})
            self._enter_text(date_field, answer_text)
            return True
        return False

    def _find_and_handle_dropdown_question(self, section: WebElement) -> bool:
        try:
            question_elements = section.find_elements(By.CLASS_NAME, 'jobs-easy-apply-form-element')
            if not question_elements:
                return False
            question = question_elements[0]

            dropdowns = question.find_elements(By.TAG_NAME, 'select')
            if not dropdowns:
                dropdowns = section.find_elements(By.CSS_SELECTOR, '[data-test-text-entity-list-form-select]')

            if dropdowns:
                dropdown = dropdowns[0]
                select = Select(dropdown)
                
                question_text = question.find_element(By.TAG_NAME, 'label').text.lower()
                
                # Check for error state
                has_error = "error" in (dropdown.get_attribute("class") or "").lower() or \
                            "error" in (section.get_attribute("class") or "").lower()

                logger.info(f"Processing Combobox: '{question_text.strip()}'" + (" (fixing error)" if has_error else ""))

                # Optimization: Check if already filled
                current_selection = select.first_selected_option.text
                if current_selection and "select an option" not in current_selection.lower() and not has_error:
                    logger.debug(f"Combobox '{question_text.strip()}' already filled with: {current_selection}")
                    return True

                options = [option.text for option in select.options]

                existing_answer = None
                for item in self.all_data:
                    if self._sanitize_text(question_text) in item['question'] and item['type'] == 'dropdown':
                        existing_answer = item['answer']
                        break

                if existing_answer:
                    logger.debug(f"Using cached answer for '{question_text.strip()}': {existing_answer}")
                    self._select_dropdown_option(dropdown, existing_answer)
                    return True

                answer = self.gpt_answerer.answer_question_from_options(question_text, options)
                self._save_questions_to_json({'type': 'dropdown', 'question': question_text, 'answer': answer})
                self._select_dropdown_option(dropdown, answer)
                return True

            else:
                return False

        except Exception as e:
            logger.warning(f"Failed to handle dropdown or combobox question: {e}")
            return False

    def _select_dropdown_option(self, element: WebElement, text: str) -> None:
        logger.debug(f"Selecting dropdown option: {text}")
        try:
            select = Select(element)
            select.select_by_visible_text(text)
            
            # Force trigger a suite of events so the website registers the selection
            # Including 'blur' which is often the key to locking in an answer
            self.driver.execute_script("""
                var el = arguments[0];
                ['change', 'input', 'blur'].forEach(function(evType) {
                    var ev = new Event(evType, { bubbles: true });
                    el.dispatchEvent(ev);
                });
            """, element)
            time.sleep(0.5)
        except Exception as e:
            logger.warning(f"Failed to select dropdown option '{text}': {e}")

    def _select_radio(self, radios: List[WebElement], answer: str) -> None:
        logger.debug(f"Selecting radio option: {answer}")
        for radio in radios:
            if answer in radio.text.lower():
                label = radio.find_element(By.TAG_NAME, 'label')
                self._click_element(label)
                return
        label = radios[-1].find_element(By.TAG_NAME, 'label')
        self._click_element(label)

    def _save_questions_to_json(self, question_data: dict) -> None:
        output_file = 'answers.json'
        question_data['question'] = self._sanitize_text(question_data['question'])

        logger.debug(f"Saving question data to JSON: {question_data}")
        try:
            try:
                with open(output_file, 'r') as f:
                    try:
                        data = json.load(f)
                        if not isinstance(data, list):
                            raise ValueError("JSON file format is incorrect. Expected a list of questions.")
                    except json.JSONDecodeError:
                        logger.error("JSON decoding failed")
                        data = []
            except FileNotFoundError:
                logger.warning("JSON file not found, creating new file")
                data = []
            data.append(question_data)
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=4)
            logger.debug("Question data saved successfully to JSON")
        except Exception:
            tb_str = traceback.format_exc()
            logger.error(f"Error saving questions data to JSON file: {tb_str}")
            raise Exception(f"Error saving questions data to JSON file: \nTraceback:\n{tb_str}")

    def _is_numeric_field(self, field: WebElement) -> bool:
        field_type = (field.get_attribute('type') or 'text').lower()
        field_id = (field.get_attribute("id") or "").lower()
        return 'numeric' in field_id or field_type == 'number' or ('text' == field_type and 'numeric' in field_id)

    def _enter_text(self, element: WebElement, text: str) -> None:
        logger.debug(f"Entering text: {text}")
        element.clear()
        element.send_keys(text)

    def _sanitize_text(self, text: str) -> str:
        sanitized_text = text.lower().strip().replace('"', '').replace('\\', '')
        sanitized_text = re.sub(r'[\x00-\x1F\x7F]', '', sanitized_text).replace('\n', ' ').replace('\r', '').rstrip(',')
        return sanitized_text