import os
import sys
import yaml
import base64
from pathlib import Path
from src.libs.resume_and_cover_builder import FacadeManager, ResumeGenerator, StyleManager
from src.libs.resume_and_cover_builder.config import global_config
from src.resume_schemas.resume import Resume
from loguru import logger

# Configure logger to see what's happening
logger.remove()
logger.add(sys.stderr, level="DEBUG")

def test_resume_generation():
    print("\n--- Starting Resume Generation Test ---\n")
    
    # 1. Load Secrets and Config
    try:
        with open('data_folder/secrets.yaml', 'r') as f:
            secrets = yaml.safe_load(f)
        with open('data_folder/config.yaml', 'r') as f:
            parameters = yaml.safe_load(f)
        with open('data_folder/plain_text_resume.yaml', 'r', encoding='utf-8') as f:
            ptr_text = f.read()
    except FileNotFoundError as e:
        print(f"Error: Missing configuration file: {e}")
        return

    llm_api_key = secrets.get('llm_api_key')
    if not llm_api_key:
        print("Error: llm_api_key not found in secrets.yaml")
        return

    # 2. Setup Global Config
    global_config.LLM_MODEL_TYPE = parameters.get('llm_model_type', 'gemini')
    global_config.LLM_MODEL = parameters.get('llm_model', 'gemma-3-27b-it')
    output_dir = Path("data_folder/output/test_resumes")
    os.makedirs(output_dir, exist_ok=True)

    # 3. Initialize Components
    print(f"Initializing Resume Builder with model: {global_config.LLM_MODEL}")
    resume_obj = Resume(ptr_text)
    style_manager = StyleManager()
    
    # Set a default style for the test
    style_path = os.path.join(os.getcwd(), "src", "libs", "resume_and_cover_builder", "resume_style", "style_josylad_blue.css")
    if not os.path.exists(style_path):
        print(f"Error: Style file not found at {style_path}")
        return
    style_manager.set_selected_style("Modern Blue") # Name from the CSS file header

    resume_gen = ResumeGenerator()
    facade = FacadeManager(llm_api_key, style_manager, resume_gen, resume_obj, output_dir)

    # 4. Generate Resume
    test_job_description = """
    We are looking for a Senior Software Engineer with expertise in Python, AWS, and AI. 
    The ideal candidate has experience building scalable systems and working with LLMs.
    """
    
    print("Calling LLM to tailor resume (this might take a minute)...")
    try:
        # Note: FacadeManager.pdf_base64 handles HTML generation and PDF conversion
        pdf_base64 = facade.pdf_base64(test_job_description)
        
        # 5. Save Output
        file_path = output_dir / "test_tailored_resume.pdf"
        with open(file_path, "wb") as f:
            f.write(base64.b64decode(pdf_base64))
        
        print(f"\n✅ SUCCESS! Resume generated and saved to: {file_path}")
        print("Please open the PDF to verify the content and formatting.")
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if facade.driver:
            facade.driver.quit()

if __name__ == "__main__":
    test_resume_generation()
