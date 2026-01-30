import google.generativeai as genai

# Setup
api_key = "AIzaSyAucdEPHi-qfZo_nU9Y0DlfgNQUYakxaZ0"
genai.configure(api_key=api_key)

# USE THIS EXACT ID
model_id = "gemma-3-27b-it" 

print(f"--- Testing connection to {model_id} ---")

try:
    model = genai.GenerativeModel(model_id)
    response = model.generate_content("Hello, are you online? Respond with 'YES I AM ONLINE'.")
    print(f"✅ Success! Connected to {model_id}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"❌ Error: {e}")
    if "404" in str(e):
        print("\nNote: Still getting 404. Let's list available models to find the exact string.")
        print("Available models:")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(m.name)