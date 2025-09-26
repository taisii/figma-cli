# 研究支援ツール 実行計画書

## 1. プロジェクト概要

本計画書は、「**知識キュレーションツール**」の開発を、テスト駆動開発（TDD）のアプローチに基づき進めるための実行計画を定義する。本ツールは、研究者のFigJamボードと参考文献群を解析し、外部の対話型AIが消費するための構造化されたコンテキストファイルを生成する。

## 2. 開発アプローチ

-   **テスト駆動開発 (TDD)**: 各機能について「テスト作成 → 実装 → リファクタリング」のサイクルを回す。
-   **モジュール分割**: 機能ごとにPythonモジュールを分割し、疎結合で再利用性の高い設計を目指す。
-   **イテレーション開発**: 大きな機能を一度に作らず、小さな単位で実装とテストを繰り返す。

## 3. 開発フェーズとタスク

### フェーズ 0: プロジェクト基盤の構築

-   **タスク:**
    1.  **ディレクトリ作成**: `src`, `tests`, `context`, `references` のディレクトリ構造を作成する。
    2.  **ライブラリ選定とインストール**: `requirements.txt` に、PDF読み込みライブラリ（例: `pypdf`）などを追加する。
    3.  **設定ファイル拡張**: `config.yaml` に、FigJamの記法をユーザーが定義できる`figma_semantics`セクションのテンプレートを記述する。
    4.  **テスト環境構築**: `pytest` を設定し、簡単なテストが実行できることを確認する。

### フェーズ 1: コア情報源の解析とスナップショット生成

このフェーズでは、主要な情報源（FigJam, 参考文献）を解析し、基本的なコンテキストファイルを生成する基盤を構築する。

-   **テスト:**
    -   `tests/test_figma_client.py`: Figma APIからオブジェクトを取得できるか。
    -   `tests/test_structure_parser.py`: `config.yaml`の`figma_semantics`定義に基づき、オブジェクトに意味的タグを付与できるか。
    -   `tests/test_reference_manager.py`: `/references/`内のPDFやマークダウンファイルの内容を読み取れるか。
-   **実装:**
    -   `src/figma_client.py`: Figma API連携。
    -   `src/structure_parser.py`: `config.yaml`を読み込み、オブジェクトを構造化・意味付けする。
    -   `src/reference_manager.py`: `/references/`ディレクトリをスキャンし、ファイル内容を抽出するモジュール。
    -   `src/main_controller.py`: 上記モジュールを呼び出し、`02_FIGJAM_SNAPSHOT.md`と`03_STRUCTURED_DATA.json`を生成するロジックを実装。

### フェーズ 2: 差分検出と時系列ログ生成

FigJamボードの変更を検出し、それを意味のある「思考のログ」として記録する機能を実装する。

-   **テスト (`tests/test_main_flow.py`):**
    -   FigJamの差分がある場合に、内部LLM（モック）が呼び出され、`01_RESEARCH_LOG.md`に追記が行われるか。
-   **実装:**
    -   `src/diff_engine.py`: 2つのオブジェクトリストから差分を検出する。
    -   `src/prompt_generator.py`: 差分情報を基に「思考のログエントリー」を生成させるためのプロンプトを設計。
    -   `src/main_controller.py`: `DiffEngine`の結果を`PromptGenerator`に渡し、得られたログを`01_RESEARCH_LOG.md`に追記するロジックを実装。

### フェーズ 3: 課題・仮説の自動抽出

解析した情報から、研究の中心となる「問い」と「仮説」を自動で抽出し、管理する機能を実装する。

-   **テスト (`tests/test_main_flow.py`):**
    -   `#issue`タグ付きの付箋が追加された場合、`05_ISSUES_AND_HYPOTHESES.md`にその内容が追記されるか。
-   **実装:**
    -   `src/prompt_generator.py`: `RESEARCH_LOG`の最新エントリーや`FIGJAM_SNAPSHOT`の内容を基に、「課題と仮説」を抽出・更新させるためのプロンプトを設計。
    -   `src/main_controller.py`: `05_ISSUES_AND_HYPOTHESES.md`を更新するロジックを実装。

### フェーズ 4: ネクストアクションのドラフト生成

抽出された課題・仮説を基に、具体的な次の行動計画と、外部ツールで使えるプロンプトのドラフトを生成する。

-   **テスト (`tests/test_main_flow.py`):**
    -   `05_ISSUES_AND_HYPOTHESES.md`が更新された後、`06_NEXT_ACTIONS.md`が新たに生成されるか。
-   **実装:**
    -   `src/prompt_generator.py`: `05`のファイルをインプットとして、「ネクストアクション」と「DeepResearch用プロンプト」のドラフトを生成させるプロンプトを設計。
    -   `src/main_controller.py`: `06_NEXT_ACTIONS.md`を生成するロジックを実装。

## 4. テスト戦略

-   **ユニットテスト**: 各モジュール（Figma連携、差分検出、ファイル読込）は独立してテストする。
-   **統合テスト**: `main_controller`のテストでは、各モジュールと内部LLMの呼び出しをモックし、一連のデータフロー（FigJam差分→複数コンテキストファイルの生成）が正しく行われることを検証する。
-   **モッキング**: 外部API（Figma, Generative AI）への依存は、`unittest.mock`や`pytest-mock`を用いて完全にモック化する。