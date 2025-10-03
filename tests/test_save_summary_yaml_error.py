from pathlib import Path
import yaml
import pytest


def build_config(tmp_path: Path) -> dict:
    return {
        "document_ingest": {
            "raw_dir": str(tmp_path / "raw"),
            "processed_dir": str(tmp_path / "processed"),
            "summaries_dir": str(tmp_path / "summaries" / "papers"),
            "summary_index_path": str(tmp_path / "summaries" / "papers" / "index.json"),
            "index_path": str(tmp_path / "processed" / "index.yaml"),
        }
    }


def prepare_bad_metadata(tmp_path: Path, slug: str) -> Path:
    root = tmp_path / "processed" / slug
    root.mkdir(parents=True)
    (root / "paper.md").write_text("---\ntitle: T\n---\nbody\n", encoding="utf-8")
    # YAML 構文エラー（未閉じクオート）
    (root / "metadata.yaml").write_text('title: "unterminated', encoding="utf-8")
    return root


def test_save_summary_raises_on_bad_metadata_yaml(tmp_path):
    from src.tools import research

    cfg = build_config(tmp_path)
    slug = "bad-meta"
    root = prepare_bad_metadata(tmp_path, slug)

    # 実行時に yaml.YAMLError が伝播し、ファイルは生成されない
    with pytest.raises(yaml.YAMLError):
        research.save_summary(slug, "Summary content", config=cfg)

    summary_path = Path(cfg["document_ingest"]["processed_dir"]) / slug / "summary.md"
    assert not summary_path.exists()

    alias_path = Path(cfg["document_ingest"]["summaries_dir"]) / f"{slug}.md"
    assert not alias_path.exists()

    # メタデータファイルは上書きされず、そのまま残る
    meta_path = Path(cfg["document_ingest"]["processed_dir"]) / slug / "metadata.yaml"
    assert meta_path.read_text(encoding="utf-8").startswith('title: "unterminated')

