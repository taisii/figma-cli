import os
import yaml
import dotenv
import google.generativeai as generativeai
import requests
from datetime import datetime

from .figma_client import FigmaClient
from .structure_parser import StructureParser
from .prompt_generator import PromptGenerator
from .cache_manager import CacheManager
from .diff_engine import DiffEngine
from .file_io import FileIO

class DifyClient:
    def __init__(self):
        self.api_key = os.getenv("DIFY_API_KEY")
        self.workflow_id = os.getenv("DIFY_WORKFLOW_ID")
        self.api_url = "https://api.dify.ai/v1/workflows/run"

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

        response = requests.post(self.api_url, headers=headers, json=data)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json()['data']['outputs']['text']

class MainController:
    def __init__(self):
        dotenv.load_dotenv()
        with open("config.yaml", "r") as f:
            self.config = yaml.safe_load(f)
        generativeai.configure(api_key=os.getenv("AI_API_KEY"))

        self.figma_client = FigmaClient()
        self.structure_parser = StructureParser(self.config)
        self.ai_model = generativeai.GenerativeModel(self.config["gemini_model_name"])
        self.dify_client = DifyClient()

    def run(self):
        print("Step 1/6: Loading context and preparing files...")
        old_objects = CacheManager.load_cache("cache.json")
        old_outline = None
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        if os.path.exists("outline.md"):
            with open("outline.md", "r") as f:
                old_outline = f.read()

        print("Step 2/6: Fetching data from Figma API...")
        new_objects = self.figma_client.get_figma_objects()
        CacheManager.save_cache(new_objects, "cache.json")

        diff_for_outline = {}
        if old_objects is not None:
            diff_for_outline = DiffEngine.detect_changes(old_objects, new_objects)
            if not any(diff_for_outline.values()):
                print("No changes detected. Skipping AI generation.")
                return
            prompt = PromptGenerator.generate_update_prompt(diff_for_outline, old_outline)
        else:
            structured_data_for_outline = self.structure_parser.parse(new_objects)
            prompt = PromptGenerator.generate_initial_prompt(structured_data_for_outline)

        print("Step 3/6: Generating AI prompts for outline...")
        print("Step 4/6: Generating research outline with AI...")
        print("--- Prompt for Outline Generation ---")
        print(prompt)
        print("-------------------------------------")
        response_outline = self.ai_model.generate_content(prompt)
        new_outline = response_outline.text

        # --- 日報生成ロジックの修正 ---
        print("Step 5/6: Generating daily log with AI...")
        log_prompt = PromptGenerator.generate_daily_report_prompt(str(diff_for_outline), new_outline)
        print("--- Prompt for Log Generation ---")
        print(log_prompt)
        print("-----------------------------------")
        response_log = self.ai_model.generate_content(log_prompt)
        new_log_content = response_log.text

        print("Step 6/6: Saving generated files and updating cache...")
        if os.path.exists("outline.md"):
            if not os.path.exists("outline_history"):
                os.makedirs("outline_history")
            history_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            os.rename("outline.md", f"outline_history/outline_{history_timestamp}.md")
        
        log_timestamp = datetime.now().strftime("%Y-%m-%d")
        with open(f"logs/log_{log_timestamp}.md", "w") as f:
            f.write(new_log_content)
        with open("outline.md", "w") as f:
            f.write(new_outline)

        print("Outline generated successfully.")

    def execute_strategy_cycle(self):
        print("Executing strategy cycle...")
        # 1. Read outline and all logs
        with open("outline.md", "r") as f:
            outline_content = f.read()
        all_logs_content = FileIO.read_all_logs()

        # 2. Send prompt to Dify API (No need to generate a separate prompt)
        print("Invoking Dify workflow...")
        strategy_text = self.dify_client.invoke(outline_content, all_logs_content)

        # 3. Save the generated strategy
        if not os.path.exists("output/proposals"):
            os.makedirs("output/proposals")
        timestamp = datetime.now().strftime("%Y%m%d")
        file_path = f"output/proposals/strategy_{timestamp}.md"
        with open(file_path, "w") as f:
            f.write(strategy_text)
        print(f"Strategy saved to {file_path}")
