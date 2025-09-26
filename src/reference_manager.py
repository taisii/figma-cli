import os
from pathlib import Path

class ReferenceManager:

    @staticmethod
    def read_references(references_dir: str) -> list[dict]:
        """
        指定されたディレクトリから、サポートされているファイル（.txt, .md）を読み込み、
        そのパスと内容を辞書のリストとして返す。
        """
        supported_extensions = [".txt", ".md"]
        references_data = []

        if not os.path.isdir(references_dir):
            return []

        for root, _, files in os.walk(references_dir):
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix in supported_extensions:
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        references_data.append({
                            "path": str(file_path),
                            "content": content
                        })
                    except Exception as e:
                        print(f"Error reading file {file_path}: {e}")
        
        return references_data
