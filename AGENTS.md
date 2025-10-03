日本語で簡潔かつ丁寧に回答してください

# リポジトリガイドライン（純粋ツール方針）

## 目的と設計原則
- 単一の Codex CLI（会話エンジン）が本リポジトリの Python 関数を“ツール”として直接呼ぶ。
- 本リポジトリは LLM/API を呼ばない。ファイル入出力と索引更新のみを担う。
- 機能は副作用の明確な小さな関数に分解し、入出力をテストしやすく保つ。

## コアモジュール
- `src/tools/research.py`
  - `list_papers(config=None)`
  - `load_paper(slug, max_chars=None, config=None)`
  - `save_summary(slug, content, tags=None, config=None)`
 - `src/convert.py`（Docling ベースの PDF→Markdown 変換ユーティリティ）

生成された Markdown とメタデータは `context/papers/<slug>/` に保存し、要約は `context/summaries/papers/<slug>.md` に同期します。索引は `context/papers/index.yaml` と `context/summaries/papers/index.json` を更新します。

## ビルド・テスト
```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
ruff check .
```

## コーディングスタイル
- 4 スペースインデント、型ヒント推奨。
- ファイル操作は失敗時の例外を明確化（`FileNotFoundError` など）。
- 相対パス格納を優先し、移動や共有に強いメタデータを維持。

## セキュリティ/設定
- API キーは扱いません（LLM 呼び出しは CLI 側）。
- `config.yaml` の `document_ingest` セクションでパスを調整可能です。
