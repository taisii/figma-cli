import pytest

from src.prompt_generator import PromptGenerator


@pytest.fixture
def structured_data():
    """テスト用の構造化データ"""
    return {
        "objects": [
            {"id": "1:1", "text": "Idea A", "tag": "重要"},
            {"id": "1:2", "text": "Idea B", "tag": "疑問点"},
            {"id": "2:1", "text": "Idea C"},
        ],
        "clusters": [
            [{"id": "1:1", "text": "Idea A"}, {"id": "1:2", "text": "Idea B"}],
            [{"id": "2:1", "text": "Idea C"}],
        ],
        "connections": [("1:1", "1:2")],
    }


@pytest.fixture
def diff_data():
    """テスト用の差分データ"""
    return {
        "added": [{"id": "3:1", "text": "New Idea"}],
        "modified": [{"id": "1:1", "old_text": "Idea A", "new_text": "Idea A updated"}],
        "deleted": [{"id": "2:1", "text": "Idea C"}],
    }


@pytest.fixture
def old_outline():
    """テスト用の旧アウトライン"""
    return "# Old Outline\n\n- Section 1"


def test_generate_initial_prompt(structured_data):
    """初回実行用プロンプトが正しく生成されるかテストする"""
    prompt = PromptGenerator.generate_initial_prompt(structured_data)
    assert "# FigJam ボードの現状" in prompt
    assert "すべての付箋とテキスト" in prompt
    assert "Idea A" in prompt
    assert "(タグ: 重要)" in prompt
    assert "1 つのグループを形成しているようです" in prompt
    assert "[Idea A, Idea B]" in prompt
    assert "[Idea A] -> [Idea B]" in prompt


def test_generate_update_prompt(diff_data, old_outline):
    """差分更新用プロンプトが正しく生成されるかテストする"""
    prompt = PromptGenerator.generate_update_prompt(diff_data, old_outline)
    assert "# 既存のアウトライン" in prompt
    assert "# Old Outline" in prompt
    assert "# 今回の変更点" in prompt
    assert "追加された付箋:" in prompt
    assert "New Idea" in prompt
    assert "テキストが変更された付箋:" in prompt
    assert '"Idea A" -> "Idea A updated"' in prompt
    assert "削除された付箋:" in prompt
    assert "Idea C" in prompt


def test_generate_log_prompt_initial(structured_data):
    """ログ用プロンプト（初回実行時）が正しく生成されるかテストする"""
    prompt = PromptGenerator.generate_log_prompt(None, structured_data)
    assert "今回のFigJamボードの変更点と、それが研究アウトラインにどのように反映されたかについて、以下の観点から日報形式でまとめる。" in prompt
    assert "冗長な表現を避け、構造的かつ網羅的に記述すること。" in prompt
    assert "### 初回実行: ボード全体の概要" in prompt
    assert "- Idea A" in prompt
    assert "## 具体例と詳細" in prompt
    assert "## 考慮事項と疑問点" in prompt
    assert "## 進捗の要約" in prompt


def test_generate_log_prompt_update(diff_data, structured_data):
    """ログ用プロンプト（差分更新時）が正しく生成されるかテストする"""
    prompt = PromptGenerator.generate_log_prompt(diff_data, structured_data)
    assert "今回のFigJamボードの変更点と、それが研究アウトラインにどのように反映されたかについて、以下の観点から日報形式でまとめる。" in prompt
    assert "冗長な表現を避け、構造的かつ網羅的に記述すること。" in prompt
    assert "### 追加された要素:" in prompt
    assert "- New Idea" in prompt
    assert "### 変更された要素:" in prompt
    assert 'ID [1:1]: "Idea A" -> "Idea A updated"' in prompt
    assert "### 削除された要素:" in prompt
    assert "- Idea C" in prompt
    assert "## 具体例と詳細" in prompt


def test_generate_daily_report_prompt():
    """日報プロンプトにUnresolved_Pointsセクションが含まれるかテストする"""
    prompt = PromptGenerator.generate_daily_report_prompt("yesterday's log", "current outline")
    assert "## Unresolved_Points" in prompt
    assert "今日の作業で感じた小さな疑問や不確かな点" in prompt
    assert "疑問に至った背景や文脈" in prompt

def test_generate_strategy_prompt_is_structured_for_deepresearch():
    """戦略提案プロンプトがDeepResearchに適した構造を持つかテストする"""
    prompt = PromptGenerator.generate_strategy_prompt("Test Outline", "Test Logs")
    assert "## 調査の背景" in prompt
    assert "## 未解決の問い (Questions)" in prompt
    assert "## 生成されるべき仮説 (Hypotheses)" in prompt
    assert "## 調査すべきキーワード (Keywords)" in prompt

