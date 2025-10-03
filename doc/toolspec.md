# Tool Specification（純粋ツール構成）

この文書は、会話エンジン（例: Codex CLI）から直接呼び出す本リポジトリの“ツール関数”仕様を定義します。LLM/API は呼び出さず、ファイル入出力と索引更新のみを行います。

## 共通
- 設定: `config.yaml` の `document_ingest` セクションを使用
  - `raw_dir`（既定: `data/raw/papers`）
  - `processed_dir`（既定: `context/papers`）
  - `summaries_dir`（既定: `context/summaries/papers`）
  - `summary_index_path`（既定: `context/summaries/papers/index.json`）
  - `index_path`（既定: `context/papers/index.yaml`）
- パスの表記
  - `list_papers` の `paper_path`/`summary_path`/`summary_alias_path` は相対パス（読みやすさのため）
  - `load_paper` の `paper_path` と `save_summary` の戻り値は絶対パス
  - シンボリックリンク不可環境では、要約の別名はコピーで同期
- エラーは Python 標準例外（`FileNotFoundError`/`OSError` など）または明示的例外（変換）を送出

---

## list_papers(config: dict | None = None) -> list[dict]
論文の概要を列挙します（各フィールドは `metadata.yaml` を優先し、欠落時は `paper.md` の frontmatter で補完）。

- 入力: 省略可（`config.yaml` の既定を使用）
- 動作: `processed_dir/<slug>/paper.md` を持つディレクトリを走査
- 戻り値（配列の各要素）
  - `id: str`（slug）
  - `title: str`（`metadata.yaml` 優先、無い場合は frontmatter）
  - `authors: list[str] | []`（`metadata.yaml` 優先、無い場合は frontmatter）
  - `year: str | int | null`（`metadata.yaml` 優先、無い場合は frontmatter）
  - `paper_path: str`（相対パス）
  - `summary_path: str | null`（相対パス、存在時）
  - `summary_alias_path: str | null`（相対パス、存在時）
- 例外/副作用: なし（読み取りのみ）
- 冪等性: あり

---

## load_paper(slug: str, max_chars: int | None = None, config: dict | None = None) -> dict
`paper.md` を読み出して返します。

- 入力
  - `slug: str`（必須）
  - `max_chars: int | None`（任意、先頭からの切り出し上限。トークン対策）
- 戻り値
  - `slug: str`
  - `content: str`
  - `truncated: bool`（切り詰めた場合 True）
  - `paper_path: str`（絶対パス）
- 例外
  - `FileNotFoundError`（`paper.md` が見つからない）
- 副作用/冪等性: なし / あり

---

## save_summary(slug: str, content: str, tags: list[str] | None = None, config: dict | None = None) -> dict
要約を保存し、別名と索引を更新します（LLM 非依存）。

- 入力
  - `slug: str`（必須）
  - `content: str`（必須）
  - `tags: list[str] | None`（任意、既存タグとマージ）
- 動作
  - `processed_dir/<slug>/summary.md` を上書き保存
  - `summaries_dir/<slug>.md` を symlink（不可時はコピー）で同期
  - `processed_dir/index.yaml` を upsert（`id/title/tags/summary_*` など）
  - `summaries_dir/index.json` を upsert（`id/title/summary_*` など）
- 戻り値
  - `summary_path: str`（絶対パス）
  - `summary_alias_path: str`（絶対パス）
- 例外
  - `FileNotFoundError`（`processed_dir/<slug>/paper.md` が存在しない）
  - `yaml.YAMLError`（`metadata.yaml` の構文エラー。保存を中止して例外を返す）
  - `OSError`（入出力失敗）
- 副作用/冪等性
  - 副作用あり（ファイル/索引更新）。同一 `content` での再実行はタイムスタンプ以外は実質同一

---

## convert_pdf_tool(pdf_path: str, output_dir: str | None = None, *, force: bool = False) -> dict
Docling を使用して PDF を Markdown に変換します（LLM 非依存）。

- 入力
  - `pdf_path: str`（必須）
  - `output_dir: str | None`（任意、既定は `data/generated`）
  - `force: bool`（任意、既存 `.md` 上書き）
- 戻り値
  - `markdown_path: str`（絶対パス）
- 例外
  - `ConversionError`（変換失敗・空出力 など。`src.convert` 由来）
  - `FileNotFoundError` / `ValueError` 等（入力不備）
- 副作用/冪等性
  - 出力ファイル作成。`force=False` では既存があると失敗。成功時は決定的（同一 PDF→同一 Markdown）

---

## 参考実装（擬似コード）
```python
from src.tools import research

cfg = research.load_config()
paper_info = research.load_paper("my-slug", max_chars=8000, config=cfg)
# 要約生成は会話エンジン（プロンプト）で実施
summary_text = "..."  # 生成テキスト
res = research.save_summary("my-slug", summary_text, tags=["experiment"], config=cfg)
print(res)

# PDF→Markdown 変換をツールとして利用
res2 = research.convert_pdf_tool("path/to/paper.pdf", output_dir="data/generated", force=False)
print(res2["markdown_path"]) 
```
