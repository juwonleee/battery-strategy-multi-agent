from pathlib import Path

from tools.preprocessing import _expand_page_range, load_document_manifest


def test_load_document_manifest_from_fixture():
    fixture_path = (
        Path(__file__).resolve().parent / "fixtures" / "sample_manifest.json"
    )

    documents = load_document_manifest(fixture_path)

    assert len(documents) == 2
    assert documents[0].document_id == "market-001"
    assert documents[1].company_scope == "lges"


def test_expand_page_range_parses_multiple_ranges():
    pages = _expand_page_range("1-3,5,7-8", total_pages=10)

    assert pages == [1, 2, 3, 5, 7, 8]
