import os
import requests

class DifyClient:
    def __init__(self):
        self.api_key = os.getenv("DIFY_API_KEY")
        self.api_url = os.getenv("DIFY_API_URL")
        self.workflow_id = os.getenv("DIFY_WORKFLOW_ID")
        if not self.api_key or not self.api_url or not self.workflow_id:
            raise ValueError("DIFY_API_KEY, DIFY_API_URL, and DIFY_WORKFLOW_ID must be set in .env file")

    def invoke(self, outline_content, all_logs_content):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "inputs": {
                "outline_content": outline_content,
                "all_logs_content": all_logs_content
            },
            "response_mode": "blocking",
            "user": "figma-cli-user-01",
            "workflow_id": self.workflow_id
        }

        if os.getenv("FIGMA_CLI_DEBUG_LOGGING") == "true":
            print("--- Dify API Request ---")
            print(f"URL: {self.api_url}/workflows/run")
            print(f"Headers: {headers}")
            print(f"Data: {data}")

        response = requests.post(f"{self.api_url}/workflows/run", headers=headers, json=data)

        if response.status_code != 200:
            if os.getenv("FIGMA_CLI_DEBUG_LOGGING") == "true":
                print("--- Dify API Error Response ---")
                print(f"Status Code: {response.status_code}")
                print(f"Response Body: {response.text}")

        response.raise_for_status()
        return response.json()['data']['outputs']['text']
