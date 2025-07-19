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
        # 1. コンテキスト読込 & 旧アウトライン退避
        old_objects = CacheManager.load_cache("cache.json")
        if os.path.exists("outline.md"):
            if not os.path.exists("outline_history"):
                os.makedirs("outline_history")
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            os.rename("outline.md", f"outline_history/outline_{timestamp}.md")
            with open(f"outline_history/outline_{timestamp}.md", "r") as f:
                old_outline = f.read()
        else:
            old_outline = None

        # 2. Figmaデータ取得
        new_objects = self.figma_client.get_figma_objects()

        # 3. プロンプト生成
        if old_objects is None or old_outline is None:
            # 初回実行
            structured_data_for_outline = self.structure_parser.parse(new_objects)
            prompt = PromptGenerator.generate_initial_prompt(structured_data_for_outline)
            structured_data_for_log = structured_data_for_outline
            diff_for_log = None
        else:
            # 差分更新
            diff_for_outline = DiffEngine.detect_changes(old_objects, new_objects)
            prompt = PromptGenerator.generate_update_prompt(diff_for_outline, old_outline)
            structured_data_for_log = self.structure_parser.parse(new_objects)
            diff_for_log = diff_for_outline

        # 4. AI実行 (アウトライン生成)
        response_outline = self.ai_model.generate_content(prompt)
        new_outline = response_outline.text

        # 4. AI実行 (ログ生成)
        log_prompt = PromptGenerator.generate_log_prompt(diff_for_log, structured_data_for_log, old_outline)
        response_log = self.ai_model.generate_content(log_prompt)
        new_log_content = response_log.text

        # 5. 成果物保存
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        if not os.path.exists("logs"):
            os.makedirs("logs")
        with open(f"logs/log_{timestamp}.md", "w") as f:
            f.write(new_log_content)
        with open("outline.md", "w") as f:
            f.write(new_outline)

        # 6. キャッシュ更新
        CacheManager.save_cache(new_objects, "cache.json")

        print("Outline generated successfully.")
