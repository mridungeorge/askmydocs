import requests, os
from dotenv import load_dotenv
load_dotenv()

url = "https://ai.api.nvidia.com/v1/retrieval/nvidia/reranking"
headers = {
    "Authorization": f"Bearer {os.getenv('NVIDIA_API_KEY')}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}
payload = {
    "model": "nvidia/rerank-qa-mistral-4b",
    "query": {"text": "test query"},
    "passages": [{"text": "this is a test passage"}],
}

resp = requests.post(url, json=payload, headers=headers)
print("Status:", resp.status_code)
print("Body:", resp.text[:500])