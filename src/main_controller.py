import os
import yaml
import dotenv
import json
from datetime import datetime

# google.generativeai as generativeai

from .figma_client import FigmaClient
from .structure_parser import StructureParser
from .reference_manager import ReferenceManager
# from .prompt_generator import PromptGenerator
# from .cache_manager import CacheManager
# from .diff_engine import DiffEngine

class MainController:
    def __init__(self):
        dotenv.load_dotenv()
        with open("config.yaml", "r") as f:
            self.config = yaml.safe_load(f)
        # generativeai.configure(api_key=os.getenv("AI_API_KEY"))

        self.figma_client = FigmaClient()
        self.structure_parser = StructureParser(self.config)
        self.reference_manager = ReferenceManager()
        # self.ai_model = generativeai.GenerativeModel(self.config["gemini_model_name"])

        # 出力ディレクトリの準備
        self.context_dir = "context"
        os.makedirs(self.context_dir, exist_ok=True)

    def run(self):
        print("Phase 1: Parsing core information sources...")

        # 1. Figmaからデータを取得し、解析する
        print("  - Fetching and parsing FigJam data...")
        figma_objects = self.figma_client.get_figma_objects()
        parsed_figma_data = self.structure_parser.parse(figma_objects)

        # 2. 参考文献ディレクトリからデータを読み込む
        print("  - Reading references...")
        references = self.reference_manager.read_references("references")

        # 3. コンテキストファイルを生成する
        print("  - Generating context files...")
        self._generate_structured_data(parsed_figma_data)
        self._generate_figma_snapshot(parsed_figma_data)

        # (フェーズ2以降で実装)
        # self._update_research_log(parsed_figma_data, references)
        # self._update_issues_and_hypotheses(parsed_figma_data)
        # self._generate_next_actions()

        print("\nPhase 1 completed successfully.")
        print(f"Context files generated in '{self.context_dir}' directory.")

    def _generate_structured_data(self, parsed_data):
        """03_STRUCTURED_DATA.jsonを生成する"""
        path = os.path.join(self.context_dir, "03_STRUCTURED_DATA.json")
        try:
            # JSONシリアライズ不可能なオブジェクトをフィルタリング
            serializable_data = self._make_serializable(parsed_data)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(serializable_data, f, indent=2, ensure_ascii=False)
            print(f"    - Generated {path}")
        except TypeError as e:
            print(f"Error serializing data for {path}: {e}")

    def _make_serializable(self, data):
        """JSONシリアライズのために再帰的にデータを変換する"""
        if isinstance(data, dict):
            return {key: self._make_serializable(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._make_serializable(element) for element in data]
        # ここに他の非シリアライズ可能型の処理を追加できる
        return data

    def _generate_figma_snapshot(self, parsed_data):
        """02_FIGJAM_SNAPSHOT.mdを生成する"""
        path = os.path.join(self.context_dir, "02_FIGJAM_SNAPSHOT.md")
        content = "# FigJam Snapshot\n\n"

        content += "## Clusters\n\n"
        if parsed_data.get("clusters"):
            for i, cluster in enumerate(parsed_data["clusters"]):
                content += f"### Cluster {i+1}\n"
                for obj in cluster:
                    content += f"- {obj.get('text', '[No Text]')} (ID: {obj.get('id')})\n"
                content += "\n"
        else:
            content += "No clusters found.\n\n"

        content += "## Connections\n\n"
        if parsed_data.get("connections"):
            for conn in parsed_data["connections"]:
                start_id = conn.get('start_node_id', 'N/A')
                end_id = conn.get('end_node_id', 'N/A')
                tags = ", ".join(conn.get('semantic_tags', []))
                content += f"- {start_id} -> {end_id} (Tags: {tags if tags else 'None'})\n"
        else:
            content += "No connections found.\n\n"
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"    - Generated {path}")