# 論文フォーマット/移植手順（reproducible）

目的: 変換済み Markdown 論文を所定のリポジトリ構造へ移植し、BibTeX メタデータとサマリーを作成・索引反映まで一貫して行う。

入力:
- 変換済み Markdown（例: `data/generated/<paper>.md`）
- タイトル/著者/年/DOI（判明している範囲）

出力:
- `context/papers/<slug>/paper.md`
- `context/papers/<slug>/metadata.bib`
- `context/papers/<slug>/summary.md`
- `context/summaries/<slug>.md`（サマリーのエイリアス）
- `context/index.yaml` の更新

## 1. スラッグの決定
- 規則: 小文字/ASCII、単語はハイフン連結、記号除去（例: `SPECTECTOR: Principled Detection of …` → `spectector-principled-detection-of-speculative-information-flows`）。
- 元ファイル名に表記ゆれや誤記がある場合は、論文タイトルに合わせて正規化する。

例（環境変数定義）:
```bash
SRC="data/generated/Princepled_Detection_of_Speculative_Information_Flows.md"
SLUG="spectector-principled-detection-of-speculative-information-flows"
DEST_DIR="context/papers/$SLUG"
mkdir -p "$DEST_DIR"
```

## 2. 本文の配置
```bash
cp -f "$SRC" "$DEST_DIR/paper.md"
```

## 3. BibTeX メタデータの作成
最小テンプレート（`@misc`）:
```bibtex
% 保存先: context/papers/<slug>/metadata.bib
@misc{<bibkey>,
  title        = {<Title>},
  author       = {<Author1> and <Author2> and ...},
  year         = {<YYYY>},
  doi          = {<DOI or empty>},
  keywords     = {<comma-separated keywords>},
  note         = {Imported via Codex CLI. Source: <original path>}
}
```

SPECTECTOR 例:
```bibtex
@misc{spectector-2020,
  title        = {SPECTECTOR: Principled Detection of Speculative Information Flows},
  author       = {Guarnieri, Marco and Koepf, Boris and Morales, Jose F. and Reineke, Jan and Sanchez, Andres},
  year         = {2020},
  doi          = {10.1109/SP40000.2020.00063},
  keywords     = {speculative-execution, side-channel, formal-methods},
  note         = {Imported via Codex CLI. Source: data/generated/Princepled_Detection_of_Speculative_Information_Flows.md}
}
```

## 4. サマリーの作成
プロンプトは `.codex/prompts/summary.md` を使用する。生成方法は環境に応じていずれかを選択。

- A) Codex コマンドを直接利用（推奨）
```bash
cat "$DEST_DIR/paper.md" | codex prompt summary > "$DEST_DIR/summary.md"
cp -f "$DEST_DIR/summary.md" "context/summaries/$SLUG.md"
```

- B) ユーティリティを利用（ファイル名を揃えるためリネーム）
```bash
python -m src.summarize --input "$DEST_DIR/paper.md" --output-dir "$DEST_DIR"
mv -f "$DEST_DIR/paper_summary.md" "$DEST_DIR/summary.md"
cp -f "$DEST_DIR/summary.md" "context/summaries/$SLUG.md"
```

## 5. 索引 `context/index.yaml` の更新
以下の項目を追加/更新する（存在する場合は上書き）。
```yaml
- id: <slug>
  title: <paper title>
  authors: [<Author1>, <Author2>, ...]
  year: <YYYY>
  doi: <DOI or null>
  source_path: <元ファイルの相対パス>
  paper_path: papers/<slug>/paper.md
  summary_path: papers/<slug>/summary.md
  summary_alias_path: summaries/<slug>.md
  ingested_at: '<UTC ISO8601>'
  tags: [<tags>]
  summary_generated: true
  summary_updated_at: '<UTC ISO8601>'
  source_type: markdown
```
現在時刻の取得例（UTC ISO8601）:
```bash
python - << 'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).isoformat())
PY
```

SPECTECTOR 例（要点のみ）:
```yaml
- id: spectector-principled-detection-of-speculative-information-flows
  title: 'SPECTECTOR: Principled Detection of Speculative Information Flows'
  authors:
  - Marco Guarnieri
  - Boris Koepf
  - Jose F. Morales
  - Jan Reineke
  - Andres Sanchez
  year: 2020
  doi: 10.1109/SP40000.2020.00063
  source_path: raw/papers/Princepled_Detection_of_Speculative_Information_Flows.pdf
  paper_path: papers/spectector-principled-detection-of-speculative-information-flows/paper.md
  summary_path: papers/spectector-principled-detection-of-speculative-information-flows/summary.md
  summary_alias_path: summaries/spectector-principled-detection-of-speculative-information-flows.md
  ingested_at: '<UTC ISO8601>'
  tags: [speculative-execution, side-channel, formal-methods]
  summary_generated: true
  summary_updated_at: '<UTC ISO8601>'
  source_type: markdown
```

## 6. 検証チェックリスト
- `context/papers/<slug>/paper.md` が存在する
- `context/papers/<slug>/metadata.bib` が存在し、必須フィールドが埋まっている
- `context/papers/<slug>/summary.md` と `context/summaries/<slug>.md` が一致する
- `context/index.yaml` に対象エントリがあり、`id` とパスが整合している

## 7. 命名・表記ポリシー
- スラッグはタイトル準拠で正規化（ASCII 小文字、ハイフン連結）
- 既知の誤記はタイトルに合わせて修正（例: `Princepled` → `principled`）
- 可能であれば `@inproceedings` で会議名・巻・頁なども BibTeX に追記
