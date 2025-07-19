# 研究支援 CLI ツール

## 概要

このツールは、Figma社のオンラインホワイトボードツール「FigJam」上のブレインストーミング内容を、生成AIを活用して解釈・構造化し、マークダウン形式の研究アウトラインを半自動で生成・更新することを目的としたCLIツールです。

研究活動におけるアイデア整理からアウトライン作成までの時間と労力を削減し、研究者がより本質的な思考や実験に集中できる環境を提供します。

## 機能

-   **FigJam ボードの読込機能**: 指定された FigJam ボードの URL から、API 経由でオブジェクト（付箋、テキスト、コネクター等）の情報を取得します。
-   **コンテンツの構造解釈機能**: 取得したオブジェクトの位置情報からクラスタリング（グループ化）を、色情報からユーザー定義のタグを抽出し、接続関係（矢印）と合わせてアイデアの論理構造を解釈します。
-   **AI によるアウトライン生成**: 解釈した構造とテキスト情報をコンテキストとして生成 AI に渡し、階層化されたマークダウン形式のアウトラインを生成します。初回実行と差分更新の両方に対応します。
-   **差分更新機能**: 前回の実行時と比較して、FigJam ボード上の変更点を検出し、その差分情報のみを AI に伝えてアウトラインを効率的に更新します。
-   **成果物のバージョン管理機能**: ツール実行時に、更新前の公式アウトライン (`outline.md`) を `outline_history/` フォルダに自動でバックアップし、変更履歴を保存します。
-   **実行ログの保存機能**: AI の生出力結果を、実行ごとにタイムスタンプ付きのファイルとして `logs/` フォルダに保存し、デバッグや思考プロセスの追跡を可能にします。

## はじめに

### 前提条件

-   Python 3.9+ がインストールされていること。
-   `pip` が利用可能であること。
-   Figma API トークンと対象の FigJam ボードの URL。
-   Google Cloud の Gemini API キー。

### インストール

1.  リポジトリをクローンします。
    ```bash
    git clone https://github.com/taisii/figma-cli
    cd figma-cli
    ```

2.  必要なライブラリをインストールします。
    ```bash
    pip install -r requirements.txt
    ```

### 設定

本ツールを実行する前に、以下の設定ファイルを用意する必要があります。

1.  **`.env` ファイルの作成**
    プロジェクトのルートディレクトリに `.env` ファイルを作成し、以下の環境変数を設定してください。
    ```dotenv
    FIGMA_API_TOKEN=YOUR_FIGMA_API_TOKEN
    FIGJAM_BOARD_URL=YOUR_FIGJAM_BOARD_URL
    AI_API_KEY=YOUR_GEMINI_API_KEY
    ```
    -   `YOUR_FIGMA_API_TOKEN`: [Figma Personal Access Tokens](https://www.figma.com/developers/api#access-tokens) から取得できます。
    -   `YOUR_FIGJAM_BOARD_URL`: 対象となる FigJam ボードのURLです。
    -   `YOUR_GEMINI_API_KEY`: [Google AI Studio](https://aistudio.google.com/app/apikey) などから取得できる Gemini API キーです。

2.  **`config.yaml` の設定**
    `config.yaml` ファイルで、色とタグのマッピングやクラスタリングの閾値、使用するGeminiモデルを設定できます。
    ```yaml
    # 色とタグのマッピング定義
    # Figmaで取得した色の16進数コードと、それに対応するタグ名を記述します。
    # 例: "#ff0000": "重要"
    color_tags:
      "#ff0000": "重要"
      "#0000ff": "疑問点"

    # クラスタリングの閾値
    # この値が小さいほど、より近くにあるオブジェクト同士がグループ化されます。
    clustering_threshold: 100

    # Gemini API モデル名
    # 使用するGeminiモデルを指定します。例: "models/gemini-1.5-pro", "models/gemini-1.5-flash"
    gemini_model_name: "models/gemini-1.5-pro"
    ```

## 使い方

設定が完了したら、以下のコマンドでツールを実行できます。

```bash
python run.py
```

初回実行時には、FigJam ボード全体からアウトラインが生成されます。2回目以降の実行では、前回の状態との差分が検出され、効率的にアウトラインが更新されます。

## プロジェクト構造

```
figma-cli/
├── .env                 # 環境変数 (APIキーなど)
├── .gitignore           # Git管理から除外するファイルの設定
├── config.yaml          # ツール設定ファイル (色マッピング、クラスタリング閾値、AIモデル名など)
├── requirements.txt     # Pythonの依存ライブラリリスト
├── run.py               # メイン実行スクリプト
├── cache.json           # FigJamボードの前回状態を保存するキャッシュファイル
├── outline.md           # 現在の最新版となる公式アウトライン
├── outline_history/     # 過去の公式アウトラインのバックアップが保存されるディレクトリ
│   └── (例: 2025-07-19_10-45.md)
├── logs/                # AIの生出力が実行ごとに保存されるディレクトリ
│   └── (例: 2025-07-19_10-45_raw.md)
├── src/                 # ソースコード
│   ├── __init__.py
│   ├── cache_manager.py # キャッシュの読み書きを管理
│   ├── diff_engine.py   # FigJamボードの差分を検出
│   ├── figma_client.py  # Figma APIとの連携
│   ├── main_controller.py # アプリケーションのメインロジック
│   ├── prompt_generator.py # AIプロンプトの生成
│   └── structure_parser.py # Figmaオブジェクトの構造解釈
└── tests/               # テストコード
    ├── test_cache_manager.py
    ├── test_diff_engine.py
    ├── test_figma_client.py
    ├── test_main_flow.py
    ├── test_prompt_generator.py
    ├── test_structure_parser.py
    └── dummy_response.json # Figma APIテスト用のダミーレスポンス
```

## 開発者向け

### テストの実行

本プロジェクトはテスト駆動開発 (TDD) のアプローチで開発されています。各機能のテストは `pytest` を使用して実行できます。

```bash
pytest
```

特定のテストファイルのみを実行することも可能です。

```bash
pytest tests/test_figma_client.py
```

### コードスタイル

コードの整形には `ruff` を使用しています。変更を加えた際は、以下のコマンドでコードスタイルを確認・修正できます。

```bash
ruff check .
ruff format .
```
