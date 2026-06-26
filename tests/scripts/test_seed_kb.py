from pathlib import Path

from scripts.seed_kb import (
    build_payload,
    iter_seed_paths,
    seed_index,
    title_from_filename,
)


def test_seed_index_parses_numeric_prefix():
    assert seed_index(Path("docs/kb_seed/07_KB Ingest & Search.md")) == 7
    assert seed_index(Path("docs/kb_seed/abc.md")) is None
    assert seed_index(Path("docs/kb_seed/no_prefix_file.md")) is None


def test_title_from_filename_removes_prefix_and_normalizes_or():
    assert (
        title_from_filename(Path("docs/kb_seed/07_KB Ingest & Search.md"))
        == "KB Ingest & Search"
    )
    assert (
        title_from_filename(Path("docs/kb_seed/08_RAG in Chat or Stream.md"))
        == "RAG in Chat/Stream"
    )
    assert (
        title_from_filename(Path("docs/kb_seed/02_chat_api_contract.md"))
        == "chat api contract"
    )


def test_iter_seed_paths_selects_only_requested_range(tmp_path):
    seed_dir = tmp_path / "docs" / "kb_seed"
    seed_dir.mkdir(parents=True)

    selected_1 = seed_dir / "01_project_overview.md"
    selected_2 = seed_dir / "02_chat_api_contract.md"
    excluded_12 = seed_dir / "12_RAG Eval Report.md"
    excluded_non_seed = seed_dir / "notes.md"

    for path in [selected_1, selected_2, excluded_12, excluded_non_seed]:
        path.write_text("content", encoding="utf-8")

    paths = iter_seed_paths(seed_dir, start_index=1, end_index=11)

    assert paths == [selected_1, selected_2]


def test_build_payload_uses_file_text_source_and_title(tmp_path):
    path = tmp_path / "07_KB Ingest & Search.md"
    path.write_text("# Header\n\nbody text", encoding="utf-8")

    payload = build_payload(path)

    assert payload["text"] == "# Header\n\nbody text"
    assert payload["source"].endswith("07_KB Ingest & Search.md")
    assert payload["title"] == "KB Ingest & Search"