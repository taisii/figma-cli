# Codex CLI 研究支援ツール 要件定義

## 1. 概要

本ツールは Codex CLI から論文 PDF や TeX プロジェクトを取り込み、Markdown と各種メタデータを生成したあと、必要に応じて Gemini で要約を作成することを目的とする。生成された知識は `context/` 以下に蓄積され、以後の議論でコンテキストとして読み込める。

## 2. 機能要件

| ID  | 要件名                  | 概要 |
| --- | ----------------------- | ---- |
| FR-1 | ドキュメント変換機能    | 指定した PDF / TeX ソースから Markdown (`paper.md`) と補助ファイルを生成する。 |
| FR-2 | サマリー生成機能        | 変換した Markdown をもとに Gemini が構造化サマリー (`summary.md`) を生成する（オンデマンド実行）。 |
| FR-3 | メタデータ管理機能      | タイトル・著者・発行年・元ソースパス、チャンク、マクロ情報などを `metadata.yaml` と `context/index.yaml` に記録する。 |
| FR-4 | CLI コマンド提供        | `codex_cli.py ingest pdf`, `codex_cli.py ingest tex`, `codex_cli.py summarize paper` コマンドで処理を行えるようにする。 |

## 3. 非機能要件

| ID   | 要件名          | 概要 |
| ---- | --------------- | ---- |
| NFR-1 | 操作性          | PDF 取り込みは 1 コマンドで完了し、サマリーは必要なタイミングで追加コマンドを実行できる。 |
| NFR-2 | 再現性          | 取り込み・要約結果は `config.yaml` と `.env` によって再現可能にする。 |
| NFR-3 | 安全性          | API キーなどの機密情報は `.env` で管理し、リポジトリに含めない。 |
| NFR-4 | 拡張性          | 将来的に追加するデータソースは新しいサブコマンドとして実装できる。 |

## 4. システム構成

```
(User) --codex_cli.py ingest pdf-->  [DocumentIngestor] --PDFテキスト抽出--> paper.md
       --codex_cli.py ingest tex-->  [DocumentIngestor] --TeX展開/変換--> paper.md + macros/chunks
                └--codex_cli.py summarize--> [DocumentIngestor] --Gemini--> summary.md
                                             |
                                             v
                                       context/papers/<slug>/
```

- `codex_cli.py`: Codex CLI から操作するためのエントリーポイント。
- `document_ingestor.py`: PDF/TeX の前処理、メタデータ抽出、オンデマンドでの Gemini 要約を担当。
- `llm_client.py`: Gemini クライアントの初期化を共通化。

## 5. データ構造

- `context/papers/<slug>/`
  - `paper.md`: Markdown 変換結果（PDF/TeX 共通）
  - `macros.md`: TeX マクロ定義（TeX 取り込み時）
  - `chunks/`: セクション単位の Markdown チャンク
  - `summary.md`: Gemini サマリー（生成コマンド実行時に作成）
  - `metadata.yaml`: タイトル、著者、年、タグ、ファイルパス、チャンク/マクロの参照など
- `context/index.yaml`: すべての取り込み結果を配列で保持（`id`, `title`, `summary_path` など）。

## 6. 運用ガイドライン

1. PDF / TeX を `context/papers/raw/` に配置するか、コマンド引数で指定する。
2. `python codex_cli.py ingest pdf [path]` または `python codex_cli.py ingest tex <dir>` を実行する。
3. 要約が必要になったら `python codex_cli.py summarize paper <slug>` を実行する。
4. 生成結果のパスを Codex セッションに読み込ませて議論を開始する。
5. メタデータを変更した場合は再実行して最新化する。

将来的な拡張（FigJam 取り込み等）は別フェーズで検討する。
