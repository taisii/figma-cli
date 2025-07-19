import pytest
import yaml

from src.structure_parser import StructureParser


@pytest.fixture
def sample_objects():
    """テスト用のサンプルFigmaオブジェクトリスト"""
    return [
        # Group 1
        {"id": "1:1", "type": "STICKY", "text": "Idea A", "position": {"x": 100, "y": 100}, "color": {"r": 1, "g": 0, "b": 0, "a": 1}}, # Red -> 重要
        {"id": "1:2", "type": "STICKY", "text": "Idea B", "position": {"x": 150, "y": 120}, "color": {"r": 0, "g": 0, "b": 1, "a": 1}}, # Blue -> 疑問点

        # Group 2
        {"id": "2:1", "type": "STICKY", "text": "Idea C", "position": {"x": 500, "y": 510}, "color": {"r": 0.5, "g": 0.5, "b": 0.5, "a": 1}}, # No tag

        # Connector
        {"id": "3:1", "type": "CONNECTOR", "text": None, "connectorStart": "1:1", "connectorEnd": "1:2"},
    ]


@pytest.fixture
def config():
    """テスト用の設定ファイル"""
    return {
        "color_tags": {
            "#ff0000": "重要",
            "#0000ff": "疑問点",
        },
        "clustering_threshold": 100,
    }


def test_tagging(sample_objects, config):
    """色の16進数コードに基づいて正しくタギングできるかテストする"""
    parser = StructureParser(config)
    tagged_objects = parser._tag_objects(sample_objects)
    assert tagged_objects[0]["tag"] == "重要"
    assert tagged_objects[1]["tag"] == "疑問点"
    assert "tag" not in tagged_objects[2]


def test_clustering(sample_objects, config):
    """位置情報に基づいて正しくクラスタリングできるかテストする"""
    parser = StructureParser(config)
    clusters = parser._cluster_objects(sample_objects)
    # Idea A and Idea B should be in the same cluster
    # Idea C should be in its own cluster
    assert len(clusters) == 2
    assert len(clusters[0]) == 2
    assert len(clusters[1]) == 1
    assert clusters[0][0]["id"] in ["1:1", "1:2"]


def test_parse_structure(sample_objects, config):
    """構造解釈のメイン処理をテストする"""
    parser = StructureParser(config)
    result = parser.parse(sample_objects)

    assert "clusters" in result
    assert "connections" in result
    assert "objects" in result

    assert len(result["clusters"]) == 2
    assert len(result["connections"]) == 1
    assert result["connections"][0] == ("1:1", "1:2")
    assert result["objects"][0]["tag"] == "重要"
