# Codex CLI 研究支援ツール 要件定義

## 1. 概要

本ツールは Codex CLI から論文 PDF を取り込み、Nougat で Markdown を生成したあと、必要に応じて Gemini で要約を作成することを目的とする。生成された知識は `context/` 以下に蓄積され、以後の議論でコンテキストとして読み込める。

## 2. 機能要件

| ID  | 要件名                  | 概要 |
| --- | ----------------------- | ---- |
| FR-1 | PDF 変換機能            | 指定した PDF を Nougat で Markdown (`paper.md`) に変換する。 |
| FR-2 | サマリー生成機能        | 変換した Markdown をもとに Gemini が構造化サマリー (`summary.md`) を生成する（オンデマンド実行）。 |
| FR-3 | メタデータ管理機能      | タイトル・著者・発行年・元 PDF パス、要約有無などを `metadata.yaml` と `context/index.yaml` に記録する。 |
| FR-4 | CLI コマンド提供        | `codex_cli.py ingest pdf` と `codex_cli.py summarize paper` コマンドで処理を行えるようにする。 |

## 3. 非機能要件

| ID   | 要件名          | 概要 |
| ---- | --------------- | ---- |
| NFR-1 | 操作性          | PDF 取り込みは 1 コマンドで完了し、サマリーは必要なタイミングで追加コマンドを実行できる。 |
| NFR-2 | 再現性          | 取り込み・要約結果は `config.yaml` と `.env` によって再現可能にする。 |
| NFR-3 | 安全性          | API キーなどの機密情報は `.env` で管理し、リポジトリに含めない。 |
| NFR-4 | 拡張性          | 将来的に追加するデータソースは新しいサブコマンドとして実装できる。 |

## 4. システム構成

```
(User) --codex_cli.py ingest--> [PDFIngestor] --Nougat--> paper.md
            └--codex_cli.py summarize--> [PDFIngestor] --Gemini--> summary.md
                                       |
                                       v
                                 context/papers/<slug>/
```

- `codex_cli.py`: Codex CLI から操作するためのエントリーポイント。
- `pdf_ingestor.py`: Nougat 呼び出し、メタデータ抽出、オンデマンドでの Gemini 要約を担当。
- `llm_client.py`: Gemini クライアントの初期化を共通化。

## 5. データ構造

- `context/papers/<slug>/`
  - `paper.md`: Nougat 変換結果
- `summary.md`: Gemini サマリー（生成コマンド実行時に作成）
  - `metadata.yaml`: タイトル、著者、年、タグ、ファイルパスなど
- `context/index.yaml`: すべての取り込み結果を配列で保持（`id`, `title`, `summary_path` など）。

## 6. 運用ガイドライン

1. PDF を `context/papers/raw/` に配置するか、コマンド引数で指定する。
2. `python codex_cli.py ingest pdf [path]` を実行する。
3. 要約が必要になったら `python codex_cli.py summarize paper <slug>` を実行する。
4. 生成結果のパスを Codex セッションに読み込ませて議論を開始する。
5. メタデータを変更した場合は再実行して最新化する。

将来的な拡張（FigJam 取り込み等）は別フェーズで検討する。
