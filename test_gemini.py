import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

resume_text = """
Name: Rahul
Education: B.Tech Computer Science
Skills: Python, Flask, SQL, HTML, CSS
Projects: AI Career Copilot
"""

prompt =prompt = f"""
Analyze this resume:

Name: Rahul
Education: B.Tech CSE
Skills: Python, Flask, SQL

Give me 3 suitable job roles.
"""

response = client.models.generate_content(
    model="gemini-flash-lite-latest",
    contents=prompt
)

print(response.text)