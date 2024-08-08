import openai
import os
from openai import OpenAI
from dotenv import load_dotenv
import re

load_dotenv()

open_ai_key=os.environ["OPENAI_API_KEY"]
model=os.environ["MODEL"]
Temperature=os.environ["TEMPERATURE"]
Max_tokens=os.environ["MAX_TOKENS"]

client=OpenAI(api_key=open_ai_key)


def create_new_file(prompt, repo_dir):
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful AI assistant that creates new code files based on user prompts."
                "Create a new file with the functionality described in the prompt."
                "Strictly do not include the main function or any call to it in the new file."
                "Provide the full content of the file, including necessary imports and code structure."
                "Do not add any comments or code blocks that start with '''python''' or any other programming language."
            )
        },
        {
            "role": "user",
            "content": f"Create a new file with the following functionality: {prompt}"
        }
    ]
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=float(Temperature),
        max_tokens=int(Max_tokens),
    )
    new_file_content = response.choices[0].message.content

    # Remove the main function if it exists
    new_file_content = re.sub(r'\nif __name__ == "__main__":\n(    .+\n)+', '', new_file_content)

    # Determine the file name and extension based on the content
    file_name = "new_file"
    if "def " in new_file_content or "class " in new_file_content:
        file_extension = ".py"
    elif "<html>" in new_file_content.lower():
        file_extension = ".html"
    elif "function " in new_file_content or "const " in new_file_content:
        file_extension = ".js"
    else:
        file_extension = ".txt"

    # Use a meaningful file name based on the prompt if possible
    match = re.search(r'(\w+)', prompt)
    if match:
        file_name = match.group(1).lower()

    file_path = os.path.join(repo_dir, f"{file_name}{file_extension}")

    with open(file_path, "w") as f:
        f.write(new_file_content)

    return file_path