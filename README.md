# 研究支援 Codex CLI

## 概要

このリポジトリは Codex CLI から利用する軽量なリサーチ支援ツールです。PDF 論文を Docling で Markdown 化し、必要に応じて Codex のプロンプト（`.codex/prompts/summary.md`）を実行してサマリーを生成するためのパイプラインを提供します。まず論文を `paper.md` に変換し、Codex セッションや追加コマンドからサマリー生成を呼び出すことで、プロンプトをローカルで調整しながら運用できます。

## 主な機能

- **PDF 取り込み (`codex ingest pdf`)**: 指定した PDF を `context/papers/<slug>/` にコピーし、Docling で `paper.md` を生成します。
- **オンデマンド要約 (`codex summarize paper`)**: 変換した Markdown を読み込み、Codex プロンプトによる日本語サマリー (`summary.md`) を作成します。
- **メタデータ管理**: 取り込み結果は `metadata.yaml` と論文専用索引 `context/papers/index.yaml` に記録されます。ノート類は `context/notes/index.yaml` で別管理します。

## セットアップ

1. 依存関係をインストールします。
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. `.codex/prompts/summary.md` と `.codex/prompts/session_summary.md` にプロンプトを整備します（テンプレートを自由に調整できます）。
3. 必要に応じて Docling OCR モデルをローカルにインストールし、`docling` の変換が実行できる状態にします。

## 使い方

1. PDF を `data/raw/papers/` に置くか、コマンドの引数にファイルパスを指定します。
2. Codex CLI で取り込みを実行します。
   ```bash
   python codex_cli.py ingest pdf path/to/paper.pdf
   # raw ディレクトリ内の未処理 PDF を一括変換する場合
   python codex_cli.py ingest pdf
   ```
3. 必要なときにサマリーを生成します。
   ```bash
   python codex_cli.py summarize paper <slug>
   # 既存サマリーを再生成する場合
   python codex_cli.py summarize paper <slug> --force
   ```
4. 生成結果は `context/papers/<slug>/` に配置され、要約は `context/summaries/papers/<slug>.md` にも複製されます。
   - `paper.md`: Docling による Markdown 変換結果
   - `summary.md`: Codex プロンプトによる構造化サマリー（必要な時に生成）
   - `metadata.yaml`: タイトル・著者・元 PDF パスなど

## プロジェクト構造

```
figma-cli/
├── codex_cli.py          # Codex CLI のエントリーポイント
├── config.yaml           # Codex プロンプトと PDF 取り込みの設定
├── context/              # 生成されたドキュメントと要約の保存先
│   ├── papers/
│   └── summaries/
│       ├── papers/   # 論文サマリー
│       └── notes/    # ノート・発表サマリー（任意）
├── run.py                # Codex CLI へのフォワード用エントリーポイント
├── src/
│   ├── convert.py        # Docling を利用した PDF→Markdown ユーティリティ
│   ├── summarize.py      # Codex プロンプトで Markdown を要約するユーティリティ
│   ├── session_manager.py   # 会話ログ管理と Codex コマンド呼び出し
│   └── document_ingestor.py # Docling 変換と Codex プロンプトを使った要約生成
└── requirements.txt
```

## コマンド補助

- `python run.py ...` で従来どおり実行しても、内部的に Codex CLI にフォワードされます。
- `python codex_cli.py --help` で利用可能なオプションを確認できます（`--force`、`--nougat-model` など）。

## 開発メモ

- Codex 関連の設定は `config.yaml` と `.env` から読み込みます。必要に応じて `.codex/prompts/` 配下のプロンプトを調整してください。
- 生成物は再生成可能なので、手動で編集する場合はバックアップを取ってから行ってください。
- 将来的に FigJam や他のデータソースを統合する際は、別ブランチで段階的に追加してください。
