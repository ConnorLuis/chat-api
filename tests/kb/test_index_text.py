from src.app.kb.index_text import extract_index_text

def test_extract_index_text_cuts_at_horizontal_rule():
    raw = """# Header\n\n正文第一段。\n\n---\n# Keywords\nnoise-keyword\n\n# QA Seeds\nexpected_keywords: should_not_index\n"""

    indexed = extract_index_text(raw)

    assert "正文第一段" in indexed
    assert "# Keywords" not in indexed
    assert "noise-keyword" not in indexed
    assert "# QA Seeds" not in indexed
    assert "expected_keywords" not in indexed


def test_extract_index_text_cuts_at_keywords_heading_without_rule():
    raw = """# Header\n\n正文应该保留。\n\n# Keywords\nthis_should_not_enter_chroma\n"""

    indexed = extract_index_text(raw)

    assert "正文应该保留" in indexed
    assert "# Keywords" not in indexed
    assert "this_should_not_enter_chroma" not in indexed


def test_extract_index_text_cuts_at_qa_seeds_heading_without_rule():
    raw = """# Header\n\n正文应该保留。\n\n# QA Seeds\n{\"qid\":\"q001\",\"expected_keywords\":[\"noise\"]}\n"""

    indexed = extract_index_text(raw)

    assert "正文应该保留" in indexed
    assert "# QA Seeds" not in indexed
    assert "expected_keywords" not in indexed
    assert "q001" not in indexed


def test_extract_index_text_cuts_at_appendix_and_changelog():
    appendix_raw = """# Header\n\n正文。\n\n# Appendix\nappendix_noise\n"""
    changelog_raw = """# Header\n\n正文。\n\n# Changelog\nchangelog_noise\n"""

    appendix_indexed = extract_index_text(appendix_raw)
    changelog_indexed = extract_index_text(changelog_raw)

    assert "正文" in appendix_indexed
    assert "appendix_noise" not in appendix_indexed
    assert "正文" in changelog_indexed
    assert "changelog_noise" not in changelog_indexed


def test_extract_index_text_handles_crlf():
    raw = "# Header\r\n\r\n正文。\r\n\r\n---\r\n# Keywords\r\nnoise\r\n"

    indexed = extract_index_text(raw)

    assert "正文" in indexed
    assert "noise" not in indexed
    assert "\r" not in indexed



