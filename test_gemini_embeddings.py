import os
import sys
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# We need to make sure we can import from src
sys.path.append(os.getcwd())

api_key = "AIzaSyAucdEPHi-qfZo_nU9Y0DlfgNQUYakxaZ0"
model_name = "models/text-embedding-004"

print(f"Testing GoogleGenerativeAIEmbeddings with model: {model_name}...")

try:
    embeddings = GoogleGenerativeAIEmbeddings(google_api_key=api_key, model=model_name)
    print("Embeddings object initialized.")
    
    text = "This is a test sentence."
    print(f"Embedding text: '{text}'")
    
    vector = embeddings.embed_query(text)
    print(f"Vector generated. Length: {len(vector)}")
    print("SUCCESS: Embeddings are working.")

except Exception as e:
    print(f"\nFAILURE: {e}")
    import traceback
    traceback.print_exc()
