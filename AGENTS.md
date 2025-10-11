日本語で簡潔かつ丁寧に回答してください

# リポジトリガイドライン（純粋ツール方針）

## 目的と設計原則
- 単一の Codex CLI（会話エンジン）が本リポジトリの Python 関数を“ツール”として直接呼ぶ。
- 本リポジトリは LLM/API を呼ばない。ファイル入出力と索引更新のみを担う。
- 機能は副作用の明確な小さな関数に分解し、入出力をテストしやすく保つ。

## コアモジュール
- `src/tools/research.py`
  - `list_papers(base_dir)`
  - `load_paper(slug, base_dir, *, max_chars=None)`
  - `save_summary(slug, content, base_dir, *, tags=None)`
  - `ingest_pdf(slug, pdf_path, base_dir, *, options=None)`
  - `convert_pdf_to_markdown(pdf_path, out_dir, *, options=None)`
  - `chunk_markdown_for_llm(markdown_path, out_dir, *, strategy='heading', max_chars=4000, overlap=200)`
- `src/convert.py`（Docling ベースの PDF→Markdown 変換ユーティリティ）

生成された Markdown とメタデータは `context/papers/<slug>/` に保存され、本文は `main.md` です。要約は `context/summaries/papers/<slug>.md` に保存し、索引は `context/papers/index.yaml` と `context/summaries/papers/index.json` を更新します。論文一覧はディレクトリ走査ではなく索引から読み出します。

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
- `config.yaml` は参考情報です。コア関数は設定ファイルを読みません（固定パス規約に従い、戻り値は絶対パス、索引は相対パス）。
