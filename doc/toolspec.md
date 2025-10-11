# Tool Specification（実装準拠）

この文書は、会話エンジン（例: Codex CLI）から直接呼び出す本リポジトリのツール関数仕様を、実装に合わせて定義します（最終更新: 2025-10-11）。LLM/API は呼び出さず、ファイル入出力と索引更新のみを行います。

## 共通
- ルート: 各関数は必ず `base_dir` または `out_dir` を受け取り、`<base_dir>/context/...` 配下に生成・更新します（`src/tools/research._resolve_paths` 準拠）。
- 設定ファイル: `config.yaml` は存在しますが、コア関数はこれを読みません（パス規約は固定）。
- 主要パス規約
  - 論文本文: `context/papers/<slug>/main.md`
  - チャンク: `context/papers/<slug>/chunks/`（`index.json` あり）
  - 要約: `context/summaries/papers/<slug>.md`
  - 索引: `context/papers/index.yaml`, `context/summaries/papers/index.json`
- APIのパス返却方針
  - API戻り値は「呼び出し側に返す値」は原則絶対パス。
  - 索引に保存される値は相対パス。
- 例外方針: モジュール独自の例外を使用します。
  - `ResearchError` 基底、`ValidationError`/`NotFoundError`/`ConvertError` など（実装定義）。

---

## list_papers(base_dir: str | os.PathLike | Path) -> list[dict]
論文の一覧を `context/papers/index.yaml` から読み込み、各要素を正規化して返します。

- 入力: `base_dir`（必須）
- 動作: インデックス内の各要素をコピーし、以下の既知パスキーを絶対パスへ正規化
  - `md_path`, `assets_dir`, `tables_dir`, `summary_path`
- 注意: インデックスに該当キーが無い場合は空文字として結合されるため、結果が `base_dir` を指す場合があります（インデックス整備を推奨）。
- 戻り値: インデックス項目の配列（未知キーはそのまま保持）。
- 例外/副作用: なし / なし

---

## load_paper(slug: str, base_dir: str | os.PathLike | Path, *, max_chars: int | None = None) -> dict
`context/papers/<slug>/main.md` を読み出して返します（先頭 front matter を除いた本文）。

- 入力: `slug`（必須）、`base_dir`（必須）、`max_chars`（任意）
- 戻り値
  - `slug: str`
  - `content: str`
  - `truncated: bool`
  - `meta: dict`（front matter）
  - `path: str`（絶対パス; `main.md`）
- 例外: `NotFoundError`（ファイル不存在）
- 副作用/冪等性: なし / あり

---

## save_summary(slug: str, content: str, base_dir: str | os.PathLike | Path, *, tags: list[str] | None = None) -> dict
要約を保存し、索引を更新します（LLM 非依存）。別名ファイルは作成しません。

- 入力: `slug`, `content`, `base_dir`（必須）、`tags`（任意）
- 動作
  - `context/summaries/papers/<slug>.md` を保存（front matter に `slug/tags/updated_at`）
  - `context/summaries/papers/index.json` を upsert（`slug/path/title/tags/source_hash/chunk_refs/updated_at`）
  - `context/papers/index.yaml` を upsert（`summary_path`, `summary_updated_at`）
- 戻り値
  - `summary_path: str`（絶対パス）
  - `chunk_refs: list[str]`
  - `updated_at: str`（UTC ISO8601）
- 例外: `NotFoundError`（未索引の `slug`、またはチャンク索引なし）
- 副作用/冪等性: あり / 同一内容なら時刻以外は実質同一

---

## convert_pdf_to_markdown(pdf_path: str | Path, out_dir: str | Path, *, options: dict | None = None) -> dict
Docling を使用して PDF を Markdown（`main.md`）に変換します（LLM 非依存）。

- 入力: `pdf_path`（必須）, `out_dir`（必須）, `options`（任意）
- 戻り値
  - `main_md_path: str`, `assets_dir: str`, `tables_dir: str`
  - `page_map: list[dict]`, `pdf_sha256: str`, `docling_opts_sha256: str`
- 例外: `src.convert.ConvertError`
- 副作用: `out_dir` 配下にファイル生成（決定的）

---

## ingest_pdf(slug: str, pdf_path: str | Path, base_dir: str | Path, *, options: dict | None = None) -> dict
PDF を取り込み、`main.md` のfront matter付与、`chunks/`生成、`context/papers/index.yaml` を upsert します。

- 戻り値: `slug`, `main_md_path`, `chunk_index_path`, `chunks`, `page_map`, `hash`
- 副作用: `context/papers/<slug>/` 配下に `main.md`, `chunks/`, `source.pdf` を作成し、索引更新
- 例外: `ConvertError` ほか

備考（リトライ挙動）
- スラッグが未索引かつ `context/papers/<slug>/` が既に存在する場合、残骸とみなし自動的に削除してから再生成します。
- 変換やチャンク生成などインデックス更新前の段階で失敗した場合は、未索引であれば部分生成物を自動削除し、次回実行で再試行できます。

---

## chunk_markdown_for_llm(markdown_path: str | Path, out_dir: str | Path, *, strategy: str = "heading", max_chars: int = 4000, overlap: int = 200) -> dict
Markdown をチャンク分割して `out_dir` に保存し、`index.json` を生成します。

- 戻り値: `chunks: list[{id, path, char_count}]`, `index_path: str`
- 例外: `ValidationError`（不正な戦略/引数）
- 副作用: `out_dir` にファイル作成

---

## 参考実装（擬似コード）
```python
from src.tools import research

# 取り込み（初回）
ing = research.ingest_pdf("my-slug", "path/to/paper.pdf", base_dir=".")

# 本文の読み出し（要約は会話エンジン側で生成）
paper = research.load_paper("my-slug", base_dir=".", max_chars=8000)

# 要約の保存
res = research.save_summary("my-slug", "...生成テキスト...", base_dir=".", tags=["experiment"])
print(res["summary_path"])  # 絶対パス

# 単体のPDF変換ユーティリティとして
res2 = research.convert_pdf_to_markdown("path/to/paper.pdf", out_dir="data/generated")
print(res2["main_md_path"]) 
```
