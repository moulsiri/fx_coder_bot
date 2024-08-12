import openai
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

open_ai_key=os.environ["OPENAI_API_KEY"]
model=os.environ["MODEL"]
Temperature=os.environ["TEMPERATURE"]
Max_tokens=os.environ["MAX_TOKENS"]

client=OpenAI(api_key=open_ai_key)

# Function to integrate new code using OpenAI GPT-4
def generate_FileName_and_extension(code):
    openai.api_key = open_ai_key
    messages = [
        {
            "role": "system",
            "content": (
            "You are a helpful AI assistant that generates relevant file name and extension based on the code provided"
            "Based on this code below,give me a relevant file name for the code and the extension in this format file_name,extension strictly excluding the '.' in extension")
        },
        {
            "role": "user",
            "content": f"Here is the code based on which filename and extention is to be generated: {code}"
        }
    ]
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=float(Temperature),
        max_tokens=int(Max_tokens),
    )
    return response.choices[0].message.content.split(",")