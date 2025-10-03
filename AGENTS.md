日本語で簡潔かつ丁寧に回答してください

# リポジトリガイドライン

## プロジェクト構成とモジュール整理
Codex CLI 用のエントリーポイントは `codex_cli.py` に集約されており、`run.py` は後方互換のために CLI をフォワードします。現在のコアモジュールは以下の通りです。

- `src/convert.py`: Docling を用いて PDF を Markdown に変換する単体ユーティリティ。`python -m src.convert` で直接利用できます。
- `src/summarize.py`: 変換済み Markdown を Codex プロンプトで要約し、出力をファイルに保存します。
- `src/session_manager.py`: 生成されたサマリー・会話ログを読み込み、`/list` `/load` `/reset` `/summary` などのカスタムコマンドを扱う CLI ラッパー。
- `.codex/prompts/session_summary.md`: 会話サマリー生成に利用する Codex プロンプト。必要に応じて編集してください。
- `src/document_ingestor.py`: 既存の Codex CLI コマンド (`ingest pdf` / `ingest tex`) から呼ばれる取り込み処理。将来的に Docling ベースへ移行予定ですが、現状は PDF/TeX の一括処理に利用します。

生成された Markdown とメタデータは `context/papers/<slug>/` に保存され、要約は論文用の集約先 `context/summaries/papers/<slug>.md` へ配置されます。索引は一次索引を分離し、論文は `context/papers/index.yaml`、ノートは `context/notes/index.yaml` で個別管理します（必要なら集約用に `context/index.yaml` を別途用意可能）。テスト用データや生成物は `data/raw/`・`data/generated/` に配置しますが、リポジトリでは `.gitignore` 済みです。

## ビルド・テスト・開発コマンド
作業前に仮想環境と依存関係をセットアップしてください。
```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
PDF 取り込みと要約生成は Codex CLI もしくは個別ユーティリティから行います。
```
python codex_cli.py ingest pdf path/to/paper.pdf
# raw ディレクトリの未処理 PDF をまとめて処理する場合
python codex_cli.py ingest pdf

# 要約が必要になったタイミングで呼び出す
python codex_cli.py summarize paper <slug>

# Docling を使って単独で PDF→Markdown したい場合
python -m src.convert --input data/raw/papers/example.pdf --output-dir data/generated

# Codex プロンプトで Markdown を要約したい場合
python -m src.summarize --input data/generated/example.md
```
`--force` で既存スラッグの上書きやサマリー再生成、`--nougat-model` で利用モデルを切り替えられます。実行ログに出力されるパスを Codex セッションのコンテキストとして利用してください。

## コーディングスタイルと命名規則
Python は 4 スペースインデント、必要に応じて型ヒントを追加します。モジュールはスネークケース、クラスはパスカルケースに統一し、副作用を持つロジックは極力薄いラッパーに留めてテスタブルな関数へ分解してください。Codex プロンプト呼び出しを行う場合は、専用のコマンド呼び出しラッパー（`document_ingestor` や `session_manager`）を経由し、副作用を制御してください。

## テスト指針
各モジュールのユニットテストは `tests/test_convert.py`・`tests/test_summarize.py`・`tests/test_session_manager.py` に実装されています。新機能を追加した際は `tests/` 配下に `test_<対象>.py` を作成し、Docling や Codex プロンプト実行はモックして副作用を制御してください。提出前には最低でも以下を実行することを推奨します。
```
python -m pytest --maxfail=1 --disable-warnings -q
ruff check .
```

## コミット・プルリクエスト指針
コミットメッセージは Conventional Commits (`feat(cli): ...`, `refactor: ...`, `docs: ...` など) を採用してください。PR では変更概要・期待される挙動・必要な設定 (`AI_API_KEY`, Docling のモデルダウンロード、Nougat 等の補助ツール) を記載し、`summary.md` や `metadata.yaml` の例を添付するとレビューがスムーズです。

## セキュリティと設定上の注意
Codex 用の `AI_API_KEY` は `.env` に保存し、履歴やレビューコメントに含めないでください。`config.yaml` は小さな値でも変更したらドキュメントに反映し、再現性を保ちます。生成された Markdown には機密情報が含まれる可能性があるため、共有時は必要に応じて編集した上で配布してください。
