from google import genai
from google.genai import types
from dotenv import load_dotenv
load_dotenv()
# Configure the client
client = genai.Client()

# Define the grounding tool
grounding_tool = types.Tool(
    google_search=types.GoogleSearch()
)

# Configure generation settings
config = types.GenerateContentConfig(
    tools=[grounding_tool]
)

# Make the request
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Who won the euro 2024?",
    config=config,
)

# Print the grounded response
print(response.text)

from google import genai

client = genai.Client()

response = client.models.embed_content(
  model='text-embedding-004',
  contents='Hello world',
)