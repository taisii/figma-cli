import os
import yaml
import dotenv
import google.generativeai as generativeai
from datetime import datetime

from .figma_client import FigmaClient
from .structure_parser import StructureParser
from .prompt_generator import PromptGenerator
from .cache_manager import CacheManager
from .diff_engine import DiffEngine

class MainController:
    def __init__(self):
        dotenv.load_dotenv()
        with open("config.yaml", "r") as f:
            self.config = yaml.safe_load(f)
        generativeai.configure(api_key=os.getenv("AI_API_KEY"))

        self.figma_client = FigmaClient()
        self.structure_parser = StructureParser(self.config)
        self.ai_model = generativeai.GenerativeModel(self.config["gemini_model_name"])

    def run(self):
        print("Step 1/6: Loading context and preparing files...")
        # 1. コンテキスト読込 & 旧アウトライン退避
        old_objects = CacheManager.load_cache("cache.json")
        old_outline = None
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") # timestampをここで定義
        if os.path.exists("outline.md"):
            with open("outline.md", "r") as f:
                old_outline = f.read()

        print("Step 2/6: Fetching data from Figma API...")
        # 2. Figmaデータ取得
        new_objects = self.figma_client.get_figma_objects()

        # 6. キャッシュ更新 (早期リターン前に実行)
        CacheManager.save_cache(new_objects, "cache.json")

        # 差分検出
        if old_objects is not None:
            diff_for_outline = DiffEngine.detect_changes(old_objects, new_objects)
            # 差分がない場合は早期リターン
            if not (diff_for_outline["added"] or diff_for_outline["modified"] or diff_for_outline["deleted"]):
                print("No changes detected. Skipping AI generation.")
                return
            prompt = PromptGenerator.generate_update_prompt(diff_for_outline, old_outline)
            structured_data_for_log = self.structure_parser.parse(new_objects)
            diff_for_log = diff_for_outline
        else:
            # 初回実行
            structured_data_for_outline = self.structure_parser.parse(new_objects)
            prompt = PromptGenerator.generate_initial_prompt(structured_data_for_outline)
            structured_data_for_log = structured_data_for_outline
            diff_for_log = None

        print("Step 3/6: Generating AI prompts for outline...")
        # 3. プロンプト生成
        # (プロンプト生成ロジックは上記で移動済み)

        print("Step 4/6: Generating research outline with AI...")
        print("--- Prompt for Outline Generation ---")
        print(prompt)
        print("-------------------------------------")
        # 4. AI実行 (アウトライン生成)
        response_outline = self.ai_model.generate_content(prompt)
        new_outline = response_outline.text

        log_prompt = PromptGenerator.generate_log_prompt(diff_for_log, structured_data_for_log, old_outline)
        print("Step 5/6: Generating daily log with AI...")
        print("--- Prompt for Log Generation ---")
        print(log_prompt)
        print("-----------------------------------")
        # 4. AI実行 (ログ生成)
        response_log = self.ai_model.generate_content(log_prompt)
        new_log_content = response_log.text

        print("Step 6/6: Saving generated files and updating cache...")
        # 5. 成果物保存
        if os.path.exists("outline.md"):
            if not os.path.exists("outline_history"):
                os.makedirs("outline_history")
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            os.rename("outline.md", f"outline_history/outline_{timestamp}.md")
        with open(f"logs/log_{timestamp}.md", "w") as f:
            f.write(new_log_content)
        with open("outline.md", "w") as f:
            f.write(new_outline)

        print("Outline generated successfully.")
