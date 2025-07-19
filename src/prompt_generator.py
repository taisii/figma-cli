class PromptGenerator:

    @staticmethod
    def generate_initial_prompt(structured_data):
        prompt = """
# FigJam ボードの現状

FigJam ボードにある情報を以下にすべてリストアップします。これらは構造化されていないブレインストーミングの断片です。
"""

        # 構造に関するヒント
        prompt += "\n## 構造に関するヒント\n"
        for cluster in structured_data["clusters"]:
            cluster_texts_str = ", ".join([obj['text'] if obj['text'] is not None else "" for obj in cluster])
            prompt += f"- 以下の付箋は視覚的に近く、1 つのグループを形成しているようです: [{cluster_texts_str}]\n"

        # すべての付箋とテキスト
        prompt += "\n## すべての付箋とテキスト\n"
        for obj in structured_data["objects"]:
            if obj.get("text"):
                tag_info = f" (タグ: {obj['tag']})" if obj.get("tag") else ""
                prompt += f"- 付箋{tag_info}: {obj['text']}\n"

        # すべての接続関係
        prompt += "\n## すべての接続関係 (矢印)\n"
        object_map = {obj["id"]: obj["text"] for obj in structured_data["objects"]}
        for start, end in structured_data["connections"]:
            start_text = object_map.get(start, "不明なオブジェクト")
            end_text = object_map.get(end, "不明なオブジェクト")
            prompt += f"- [{start_text}] -> [{end_text}]\n"

        prompt += """
# タスク

以上のすべての情報を整理・解釈し、論理的で分かりやすい、階層構造を持ったマークダウン形式の研究アウトラインをゼロから生成してください。
"""
        return prompt

    @staticmethod
    def generate_update_prompt(diff_data, old_outline):
        prompt = f"""
# 既存のアウトライン

これは前回あなたが作成したアウトラインです。議論の全体像と文脈を把握するために参照してください。

{old_outline}

# 今回の変更点

前回の状態から、FigJam ボードには以下の変更がありました。この差分情報を重点的に反映し、既存のアウトラインを更新・再構築してください。
"""

        if diff_data.get("added"):
            prompt += "\n## 追加された付箋:\n"
            for obj in diff_data["added"]:
                prompt += f"- {obj['text']}\n"

        if diff_data.get("modified"):
            prompt += "\n## テキストが変更された付箋:\n"
            for mod in diff_data["modified"]:
                prompt += f"- 付箋 ID [{mod['id']}]: \"{mod['old_text']}\" -> \"{mod['new_text']}\"\n"

        if diff_data.get("deleted"):
            prompt += "\n## 削除された付箋:\n"
            for obj in diff_data["deleted"]:
                prompt += f"- {obj['text']}\n"

        prompt += """
# タスク

以上の「既存のアウトライン」と「今回の変更点」を踏まえて、最も論理的で分かりやすい、最新のマークダウン形式アウトラインを生成してください。
"""
        return prompt
