import os
import sys
from src.libs.resume_and_cover_builder.llm.llm_job_parser import LLMParser
import config as cfg
from langchain_core.messages import HumanMessage

# Mocking the config for the test
cfg.LLM_MODEL_TYPE = 'gemini'
cfg.LLM_MODEL = 'gemma-3-27b'

# We need to make sure we can import from src
sys.path.append(os.getcwd())

api_key = "AIzaSyAucdEPHi-qfZo_nU9Y0DlfgNQUYakxaZ0"

print(f"Initializing LLMParser with {cfg.LLM_MODEL}...")
try:
    parser = LLMParser(api_key=api_key)
    print("LLMParser initialized.")
    
    print("Testing LoggerChatModel invocation...")
    messages = [HumanMessage(content="Hello, are you working? Respond with only 'YES'")]
    
    # parser.llm is a LoggerChatModel instance, which is a callable
    response = parser.llm(messages)
    
    print(f"Response type: {type(response)}")
    print(f"Response content: {getattr(response, 'content', response)}")

    if "YES" in str(response).upper():
        print("\nSUCCESS: Gemini 3 Flash is working correctly!")
    else:
        print("\nPARTIAL SUCCESS: Received a response, but it didn't contain 'YES'.")

except Exception as e:
    print(f"\nFAILURE: {e}")
    import traceback
    traceback.print_exc()
