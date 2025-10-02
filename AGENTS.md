日本語で簡潔かつ丁寧に回答してください

# リポジトリガイドライン

## プロジェクト構成とモジュール整理
Codex CLI 用のコマンドは `codex_cli.py` に集約されています。`run.py` は後方互換のため Codex CLI へ実行をフォワードします。`src/` 配下は最小構成で、`llm_client.py` が Gemini クライアントの初期化、`pdf_ingestor.py` が Nougat 変換とオンデマンド要約処理を担います。生成された知識は `context/papers/<slug>/` に `paper.md`・`metadata.yaml`（必要に応じて `summary.md`）のセットで保存され、索引は `context/index.yaml` に記録されます。

## ビルド・テスト・開発コマンド
作業前に仮想環境と依存関係をセットアップしてください。
```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
PDF 取り込みと要約生成は Codex CLI から行います。
```
python codex_cli.py ingest pdf path/to/paper.pdf
# raw ディレクトリの未処理 PDF をまとめて処理する場合
python codex_cli.py ingest pdf

# 要約が必要になったタイミングで呼び出す
python codex_cli.py summarize paper <slug>
```
`--force` で既存スラッグの上書きやサマリー再生成、`--llm-model` / `--nougat-model` で利用モデルを切り替えられます。実行ログに出力されるパスを Codex セッションのコンテキストとして利用してください。

## コーディングスタイルと命名規則
Python は 4 スペースインデント、必要に応じて型ヒントを追加します。モジュールはスネークケース、クラスはパスカルケースに統一し、副作用を持つロジックは極力薄いラッパーに留めてテスタブルな関数へ分解してください。Gemini へのアクセスは `llm_client.build_generative_model` を通じて共通化します。

## テスト指針
現在は PDF インジェスト周りのユニットテストが未整備です。新機能を追加した際は `tests/` 配下に `test_<対象>.py` を作成し、`subprocess.run` や LLM 呼び出しをモックして副作用を制御してください。提出前には最低でも以下を実行することを推奨します。
```
python -m pytest --maxfail=1 --disable-warnings -q
ruff check .
```

## コミット・プルリクエスト指針
コミットメッセージは Conventional Commits (`feat(cli): ...`, `refactor: ...`, `docs: ...` など) を採用してください。PR では変更概要・期待される挙動・必要な設定 (`AI_API_KEY`, Nougat の導入手順など) を記載し、`summary.md` や `metadata.yaml` の例を添付するとレビューがスムーズです。

## セキュリティと設定上の注意
Gemini API キーは `.env` に保存し、履歴やレビューコメントに含めないでください。`config.yaml` は小さな値でも変更したらドキュメントに反映し、再現性を保ちます。生成された Markdown には機密情報が含まれる可能性があるため、共有時は必要に応じて編集した上で配布してください。
