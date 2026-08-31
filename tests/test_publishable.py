from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ("D:\\", "C:\\Users\\", "/Users/", "adhoc_jobs/uva", "op://")


def test_examples_and_docs_have_no_local_paths():
    hits = []
    for path in list(ROOT.glob("examples/**/*.json")) + list(ROOT.glob("*.md")) + list(ROOT.glob("docs/*.md")):
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN:
            if token in text:
                hits.append(f"{path.name}: {token}")
    assert hits == []
