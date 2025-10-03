# 研究支援ツール（純粋ツール構成）

## 目的

単一の Codex CLI（会話エンジン）が起動時に本リポジトリの「ツール関数」を直接呼び出せるようにし、研究の相棒として論文コンテキストの読み出し・保存・索引更新を行う。ここでは LLM/API を一切呼び出さず、純粋なファイル操作のみを提供する。

## 提供機能（Python ツール関数）

- `src/tools/research.py`
  - `list_papers(config=None) -> list[dict]`
    - `context/papers/<slug>/` を走査して論文一覧を返す。
  - `load_paper(slug, max_chars=None, config=None) -> dict`
    - `paper.md` を読み出し、必要なら文字数制限して返す。
  - `save_summary(slug, content, tags=None, config=None) -> dict`
    - `summary.md` を保存し、`context/summaries/papers/<slug>.md` の別名同期、`index.yaml` と `summaries/index.json` を更新。

加えて、PDF→Markdown 変換ユーティリティを同梱しています（LLM 非依存）。
- `src/convert.py`（Docling ベース）
  - CLI: `python -m src.convert --input path/to/paper.pdf --output-dir data/generated` 
  - 出力: `data/generated/<name>.md`

要約の生成自体は Codex CLI のプロンプト（例: `.codex/prompts/summary.md`）で行い、本ツールは結果の永続化のみを担当する。

## 使い方（例）

Codex CLI のツール実行から Python 関数を呼べる設定で、下記のように利用します。

1. `load_paper(slug)` で本文を取得 → CLI 側のプロンプトで要約生成。
2. 生成テキストを `save_summary(slug, content)` に渡して保存・索引更新。

Python から直接呼ぶ場合の参考:

```python
from src.tools import research

cfg = research.load_config()
paper = research.load_paper("my-paper-slug", max_chars=8000, config=cfg)
summary = "...ここにCLIで生成したサマリー文字列..."
result = research.save_summary("my-paper-slug", summary, tags=["experiment"], config=cfg)
print(result)

# PDF→Markdown 変換をツール関数として利用する例
res = research.convert_pdf_tool("path/to/paper.pdf", output_dir="data/generated", force=False)
print(res["markdown_path"])  # 生成された Markdown のパス
```

## ディレクトリ/設定

- 既定の配置
  - 論文本文: `context/papers/<slug>/paper.md`
  - 要約別名: `context/summaries/papers/<slug>.md`
  - 論文索引: `context/papers/index.yaml`
  - 要約索引: `context/summaries/papers/index.json`
- これらのパスは `config.yaml` の `document_ingest` セクションで変更可能です。

## 開発メモ

- 本リポジトリは API を直接呼びません。LLM 呼び出しは会話エンジン（Codex CLI）側で行ってください。
- 生成物は可逆なので、必要に応じて再生成・再保存できます。
