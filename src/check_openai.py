import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize OpenAI client with config from .env
client = OpenAI(
    api_key=os.getenv('OPENAI_API_KEY'),
    base_url=os.getenv('OPENAI_BASE_URL')
)
model = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')

def check_openai_availability():
    """Check if the OpenAI-compatible API is available."""
    try:
        # Send a simple test message
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Hello, can you respond with 'OK' if you are available?"}],
            max_tokens=10,
            temperature=0.0
        )
        # Check if we got a response
        if response.choices and response.choices[0].message.content:
            return True, "API is available."
        else:
            return False, "API responded but with empty content."
    except Exception as e:
        return False, f"API check failed: {str(e)}"

if __name__ == '__main__':
    available, message = check_openai_availability()
    if available:
        print("[OK] OpenAI兼容接口可用。")
    else:
        print(f"[FAIL] OpenAI兼容接口不可用: {message}")