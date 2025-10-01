# 研究支援 Codex CLI

## 概要

このリポジトリは Codex CLI から利用する軽量なリサーチ支援ツールです。PDF 論文を Nougat で Markdown 化し、必要に応じて Gemini でサマリーを生成するためのパイプラインを提供します。まず論文を `paper.md` に変換し、Codex セッションや追加コマンドからサマリー生成を呼び出すことで、利用したいタイミングだけ API コストを支払う運用ができます。

## 主な機能

- **PDF 取り込み (`codex ingest pdf`)**: 指定した PDF を `context/papers/<slug>/` にコピーし、Nougat で `paper.md` を生成します。
- **オンデマンド要約 (`codex summarize paper`)**: 変換した Markdown を読み込み、必要になったタイミングで Gemini が日本語サマリー (`summary.md`) を作成します。
- **メタデータ管理**: 取り込み結果は `metadata.yaml` と `context/index.yaml` に記録され、後から CLI で参照できます。

## セットアップ

1. 依存関係をインストールします。
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. `.env` に Gemini API キーを設定します。
   ```dotenv
   AI_API_KEY=your_gemini_api_key
   ```
3. Nougat CLI をローカルにインストールし、`nougat` コマンドが利用できる状態にします。

## 使い方

1. PDF を `context/papers/raw/` に置くか、コマンドの引数にファイルパスを指定します。
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
4. 生成結果は `context/papers/<slug>/` に配置されます。
   - `paper.md`: Nougat による Markdown 変換結果
   - `summary.md`: Gemini による構造化サマリー（必要な時に生成）
   - `metadata.yaml`: タイトル・著者・元 PDF パスなど

## プロジェクト構造

```
figma-cli/
├── codex_cli.py          # Codex CLI のエントリーポイント
├── config.yaml           # Gemini と PDF 取り込みの設定
├── context/              # 生成されたドキュメントの保存先
├── run.py                # Codex CLI へのフォワード用エントリーポイント
├── src/
│   ├── __init__.py
│   ├── llm_client.py     # Gemini クライアントの共通設定
│   └── pdf_ingestor.py   # Nougat 変換とオンデマンド要約
└── requirements.txt
```

## コマンド補助

- `python run.py ...` で従来どおり実行しても、内部的に Codex CLI にフォワードされます。
- `python codex_cli.py --help` で利用可能なオプションを確認できます（`--force`、`--llm-model`、`--nougat-model` など）。

## 開発メモ

- LLM 設定は `config.yaml` と `.env` から読み込みます。Gemini を利用できない場合でも、サマリーは抜粋にフォールバックします。
- 生成物は再生成可能なので、手動で編集する場合はバックアップを取ってから行ってください。
- 将来的に FigJam や他のデータソースを統合する際は、別ブランチで段階的に追加してください。
