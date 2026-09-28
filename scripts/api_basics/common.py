from dotenv import load_dotenv
import os
from openai import OpenAI

def new_client():
    load_dotenv()
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
