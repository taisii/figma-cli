# 研究支援ツール（純粋ツール構成）

## 目的

単一の Codex CLI（会話エンジン）が起動時に本リポジトリの「ツール関数」を直接呼び出せるようにし、研究の相棒として論文コンテキストの読み出し・保存・索引更新を行う。ここでは LLM/API を一切呼び出さず、純粋なファイル操作のみを提供する。

## 提供機能（Python ツール関数）

- `src/tools/research.py`
  - `list_papers(base_dir) -> list[dict]`
    - `context/papers/index.yaml` を読み、既知パスキーを絶対パスへ正規化して返す。
  - `load_paper(slug, base_dir, *, max_chars=None) -> dict`
    - `context/papers/<slug>/main.md` を読み出し、front matter を除いた本文を返す。
  - `save_summary(slug, content, base_dir, *, tags=None) -> dict`
    - `context/summaries/papers/<slug>.md` を保存し、`context/papers/index.yaml` と `context/summaries/papers/index.json` を更新。
  - `ingest_pdf(slug, pdf_path, base_dir, *, options=None) -> dict`
    - PDF を変換→`main.md` に front matter 付与→チャンク生成→索引更新まで一括実行（重複スラグは `ConflictError`）。
  - `convert_pdf_to_markdown(pdf_path, out_dir, *, options=None) -> dict`
    - Docling により PDF を `main.md` に変換（`assets/`, `tables/` も整備）。
  - `chunk_markdown_for_llm(markdown_path, out_dir, *, strategy='heading', max_chars=4000, overlap=200) -> dict`
    - Markdown をチャンク分割して `chunks/` と `index.json` を生成。

要約の生成自体は Codex CLI 側で行い、本ツールは結果の永続化のみを担当します。

## 使い方（例）

```python
from src.tools import research

base = "."  # リポジトリのベースディレクトリ
slug = "my-paper-slug"
pdf  = "path/to/paper.pdf"

# 取り込み（変換→保存→索引更新→チャンク）
ing = research.ingest_pdf(slug, pdf, base_dir=base)

# 一覧・読み込み
papers = research.list_papers(base)
paper  = research.load_paper(slug, base, max_chars=8000)

# 要約の保存（CLI で生成したテキストを渡す）
res = research.save_summary(slug, "...要約本文...", base, tags=["experiment"])
print(res["summary_path"])  # 絶対パス

# 単体の PDF 変換ユーティリティとして
conv = research.convert_pdf_to_markdown(pdf, out_dir="data/generated")
print(conv["main_md_path"])  # 生成された main.md の絶対パス
```

## ディレクトリ/設定

- 既定の配置（固定規約）
  - 論文本文: `context/papers/<slug>/main.md`
  - チャンク: `context/papers/<slug>/chunks/`（`index.json`）
  - 要約: `context/summaries/papers/<slug>.md`
  - 論文索引: `context/papers/index.yaml`
  - 要約索引: `context/summaries/papers/index.json`
- 設定ファイル `config.yaml` は参考情報です。コア関数は設定を読みません。

## 開発メモ

- 本リポジトリは API を直接呼びません。LLM 呼び出しは会話エンジン（Codex CLI）側で行ってください。
- 生成物は決定論的ですが、変換スキップ最適化（`pdf_sha256`/Docling 設定一致でのスキップ）は現状未実装です（将来対応）。
