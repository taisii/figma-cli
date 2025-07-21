import os
import yaml
import google.generativeai as generativeai
from datetime import datetime

from .figma_client import FigmaClient
from .structure_parser import StructureParser
from .prompt_generator import PromptGenerator
from .cache_manager import CacheManager
from .diff_engine import DiffEngine
from .file_io import FileIO
from .dify_client import DifyClient


class MainController:
    def __init__(self):
        with open("config.yaml", "r") as f:
            self.config = yaml.safe_load(f)
        generativeai.configure(api_key=os.getenv("AI_API_KEY"))

        self.figma_client = FigmaClient()
        self.structure_parser = StructureParser(self.config)
        self.ai_model = generativeai.GenerativeModel(self.config["gemini_model_name"])
        self.dify_client = DifyClient()

    def run(self):
        if os.getenv("FIGMA_CLI_DEBUG_LOGGING") == "true":
            print("Step 1/6: Loading context and preparing files...")
        old_objects = CacheManager.load_cache("cache.json")
        old_outline = None
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        if os.path.exists("outline.md"):
            with open("outline.md", "r") as f:
                old_outline = f.read()

        if os.getenv("FIGMA_CLI_DEBUG_LOGGING") == "true":
            print("Step 2/6: Fetching data from Figma API...")
        new_objects = self.figma_client.get_figma_objects()
        CacheManager.save_cache(new_objects, "cache.json")

        diff_for_outline = {}
        if old_objects is not None:
            diff_for_outline = DiffEngine.detect_changes(old_objects, new_objects)
            if not any(diff_for_outline.values()):
                if os.getenv("FIGMA_CLI_DEBUG_LOGGING") == "true":
                    print("No changes detected. Skipping AI generation.")
                return
            prompt = PromptGenerator.generate_update_prompt(
                diff_for_outline, old_outline
            )
        else:
            structured_data_for_outline = self.structure_parser.parse(new_objects)
            prompt = PromptGenerator.generate_initial_prompt(
                structured_data_for_outline
            )

        if os.getenv("FIGMA_CLI_DEBUG_LOGGING") == "true":
            print("Step 3/6: Generating AI prompts for outline...")
            print("Step 4/6: Generating research outline with AI...")
            print("--- Prompt for Outline Generation ---")
            print(prompt)
            print("-------------------------------------")
        response_outline = self.ai_model.generate_content(prompt)
        new_outline = response_outline.text

        # --- 日報生成ロジックの修正 ---
        if os.getenv("FIGMA_CLI_DEBUG_LOGGING") == "true":
            print("Step 5/6: Generating daily log with AI...")
            log_prompt = PromptGenerator.generate_daily_report_prompt(
                str(diff_for_outline), new_outline
            )
            print("--- Prompt for Log Generation ---")
            print(log_prompt)
            print("-----------------------------------")
        else:
            log_prompt = PromptGenerator.generate_daily_report_prompt(
                str(diff_for_outline), new_outline
            )
        response_log = self.ai_model.generate_content(log_prompt)
        new_log_content = response_log.text

        if os.getenv("FIGMA_CLI_DEBUG_LOGGING") == "true":
            print("Step 6/6: Saving generated files and updating cache...")
        if os.path.exists("outline.md"):
            if not os.path.exists("outline_history"):
                os.makedirs("outline_history")
            history_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            os.rename("outline.md", f"outline_history/outline_{history_timestamp}.md")

        log_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        with open(f"logs/log_{log_timestamp}.md", "w") as f:
            f.write(new_log_content)
        with open("outline.md", "w") as f:
            f.write(new_outline)

        if os.getenv("FIGMA_CLI_DEBUG_LOGGING") == "true":
            print("Outline generated successfully.")

    def execute_strategy_cycle(self):
        if os.getenv("FIGMA_CLI_DEBUG_LOGGING") == "true":
            print("Executing strategy cycle...")
        # 1. Read outline and all logs
        with open("outline.md", "r") as f:
            outline_content = f.read()
        all_logs_content = FileIO.read_all_logs()

        # 2. Send prompt to Dify API (No need to generate a separate prompt)
        if os.getenv("FIGMA_CLI_DEBUG_LOGGING") == "true":
            print("--- Outline Content ---")
            print(outline_content)
            print("--- All Logs Content ---")
            print(all_logs_content)
            print("Invoking Dify workflow...")
        # Truncate outline_content to fit Dify API limit (e.g., 500 characters)
        # A more sophisticated solution would involve summarizing the content.
        truncated_outline_content = outline_content[:500]
        # Truncate all_logs_content to fit Dify API limit (e.g., 15000 characters)
        truncated_all_logs_content = all_logs_content[:15000]
        strategy_text = self.dify_client.invoke(truncated_outline_content, truncated_all_logs_content)

        # 3. Save the generated strategy
        if not os.path.exists("output/proposals"):
            os.makedirs("output/proposals")
        timestamp = datetime.now().strftime("%Y%m%d")
        file_path = f"output/proposals/strategy_{timestamp}.md"
        with open(file_path, "w") as f:
            f.write(strategy_text)
        if os.getenv("FIGMA_CLI_DEBUG_LOGGING") == "true":
            print(f"Strategy saved to {file_path}")