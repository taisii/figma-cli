## 研究支援ツール: 実装計画と仕様（v0）

本ドキュメントは、本リポジトリを第三者が単独で実装・運用できる状態にするための合意済み方針と具体的な実装計画を示します。現段階（v0）は破壊的変更を許容します。

### 目的とスコープ
- 研究側リポジトリでLLMエージェントと対話しながらPDF論文を扱う際、PDFのままでは扱いにくい課題を解消する。
- Doclingを用いてPDF→Markdownへ変換し、ファイル保存・索引更新・要約保存を提供する「純粋ツール群」を実装する。
- LLM/APIは呼ばず、I/Oと索引のみを担う。副作用は明示された出力パスに限定する。

### 採用方針
- 配布はGitサブモジュールのみ（PyPI配布は当面行わない）。
- 研究側リポジトリが会話・状態管理を担い、本リポジトリは決定論的ユーティリティ関数のみ提供する。

---

## 公開API（案）
型は説明用。実装では適切に`TypedDict`/`dataclass`を用いる。

```python
def convert_pdf_to_markdown(
    pdf_path: str | os.PathLike,
    out_dir: str | os.PathLike,
    *,
    options: dict | None = None,
) -> dict:  # ConvertResult
    """DoclingでPDFをMarkdownに変換し、出力先に保存する。
    戻り値: {
      'main_md_path': 'context/papers/<slug>/main.md',
      'assets_dir': 'context/papers/<slug>/assets',
      'tables_dir': 'context/papers/<slug>/tables',
      'page_map': [{'page':1,'start':...,'end':...}, ...],
      'pdf_sha256': '...', 'docling_opts_sha256': '...'}
    """

def ingest_pdf(
    slug: str,
    pdf_path: str | os.PathLike,
    base_dir: str | os.PathLike,
    *,
    options: dict | None = None,
) -> dict:  # IngestResult（変換→保存→索引更新まで一括）

def chunk_markdown_for_llm(
    markdown_path: str | os.PathLike,
    out_dir: str | os.PathLike,
    *,
    strategy: str = 'heading',  # 'heading' | 'fixed'
    max_chars: int = 4000,
    overlap: int = 200,
) -> dict:  # ChunkIndex（chunks/index.json を返すメタ）

def list_papers(base_dir: str | os.PathLike) -> list[dict]:  # PaperMeta

def load_paper(
    slug: str,
    base_dir: str | os.PathLike,
    *,
    max_chars: int | None = None,
) -> dict:  # {'content': str, 'meta': PaperMeta}

def save_summary(
    slug: str,
    content: str,
    base_dir: str | os.PathLike,
    *,
    tags: list[str] | None = None,
) -> dict:  # SummaryMeta
```

原則:
- すべての関数は入出力パスを引数で受け取り、実際に書き込んだ相対パス一覧とハッシュを返す。
- LLM/ネットワークを呼ばない。I/O失敗は明示的な例外で通知する。

---

## データ配置仕様

```
<base_dir>/
  context/
    papers/
      <slug>/
        main.md                  # 本文（YAMLフロントマター付き）
        assets/                  # 画像など
        tables/                  # 表のCSVや補助MD
        chunks/
          0001.md, 0002.md, ... # チャンク済み本文
          index.json             # チャンクメタ
        source.pdf               # 任意（同一性確認用）
    papers/index.yaml            # グローバル索引（version付き）
    summaries/
      papers/<slug>.md           # 要約（メタ付き）
      papers/index.json          # 要約索引（version付き）
```

フロントマター例（`main.md`）:
```yaml
---
title: "..."
doi: "..."
authors: ["..."]
pages: 12
hash: { pdf_sha256: "...", docling_opts: "..." }
updated_at: "2025-10-11T00:00:00Z"
---
```

`context/papers/index.yaml` スキーマ（v1）:
```yaml
version: 1
papers:
  - slug: "..."
    title: "..."
    md_path: "context/papers/<slug>/main.md"
    assets_dir: "context/papers/<slug>/assets"
    chunk_count: 8
    pages: 12
    hash: { pdf_sha256: "...", docling_opts: "..." }
    updated_at: "ISO-8601"
```

`context/summaries/papers/index.json` スキーマ（v1）:
```json
{ "version": 1,
  "summaries": [
    { "slug": "...",
      "path": "context/summaries/papers/<slug>.md",
      "tags": ["..."],
      "source_hash": "...",
      "chunk_refs": ["0001", "0002"],
      "updated_at": "ISO-8601" }
  ]
}
```

---

## 変換・チャンク方針
- 変換: Doclingを必須採用。見出し階層（h1–h3）とページ番号を可能な限り保持。
- 表: 本文側は概要＋リンク、実体は`tables/`へCSV/MDで保存。
- 数式: 既定はテキスト優先、レンダ不可は画像代替（オプション）。
- チャンク: 見出しベースで分割し、閾値超過時のみ二次分割。既定`max_chars=4000`、`overlap=200`。
- 再実行決定性: `pdf_sha256`とDocling設定ハッシュが同一なら変換をスキップ。

---

## 整合性・エラー処理
- 原子的更新: 一時ファイルに書き出し、`os.replace`で入れ替え。途中失敗は痕跡を残さない。
- 例外階層: `ResearchError`基底に`NotFoundError`/`IOError`/`ValidationError`/`ConflictError`/`ConvertError`。
- 同時実行: 当面は単一プロセス前提。将来は`filelock`導入で拡張可能に実装。
- スラグ規約: 小文字英数と`-`のみ、先頭末尾`-`禁止、重複はエラー。

---

## 対応環境
- Python 3.10+、macOS/Linuxを想定（Windowsは将来検討）。
- 依存: Docling（変換機能の必須依存）、`pyyaml`、`json`標準、`pathlib`等。

---

## 実装ロードマップ（v0）
1) Doclingラッパ実装（`src/convert.py`）
- 入力PDF→`main.md`/`assets`/`tables`を生成。
- `pdf_sha256`と`docling_opts`のハッシュを返却。

2) チャンク化ユーティリティ（`src/tools/research.py`）
- 見出し優先＋文字閾値＋オーバーラップ。`chunks/`と`index.json`生成。

3) 索引更新の原子的実装
- `context/papers/index.yaml`と`context/summaries/papers/index.json`のv1スキーマで更新。

4) 高位関数`ingest_pdf`
- 変換→保存→索引更新→チャンク生成までを一括で実行。

5) 例外とロールバック
- 例外階層導入。部分失敗時はロールバック（未コミットファイル削除）。

6) テスト/品質
- 小さなPDFフィクスチャで決定性を検証。`pytest -q`、`ruff check .`をCIに。

7) ドキュメント
- `doc/agent_integration.md`にエージェントからの呼び出し例と失敗時リトライ方針を記載。

---

## 使い方（最小例）
```python
from src.tools import research

base = "/path/to/project"  # 研究側のベースディレクトリ
slug = "attention-is-all-you-need"
pdf  = "/path/to/paper.pdf"

# 取り込み（変換→保存→索引更新→チャンク）
res = research.ingest_pdf(slug, pdf, base)

# 一覧・読み込み
papers = research.list_papers(base)
paper  = research.load_paper(slug, base)

# 要約を保存
research.save_summary(slug, "要約本文...", base, tags=["intro", "method"])
```

---

## 将来検討
- 並列安全化（`filelock`）、部分更新（差分変換）、OCR拡張、Windows対応。
- チャンクのトークンベース分割、数式/図表のリッチ表現最適化。

以上。
