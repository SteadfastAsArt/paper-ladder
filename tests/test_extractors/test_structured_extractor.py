"""Tests for structured extractor."""

import pytest

from paper_ladder.extractors.structured_extractor import (
    StructuredExtractor,
    _match_section_type,
)
from paper_ladder.models import ContentBlock


class TestSectionPatternMatching:
    """Tests for section pattern matching."""

    def test_match_abstract(self):
        """Test matching abstract section."""
        assert _match_section_type("Abstract") == "abstract"
        assert _match_section_type("ABSTRACT") == "abstract"
        assert _match_section_type("Summary") == "abstract"

    def test_match_introduction(self):
        """Test matching introduction section."""
        assert _match_section_type("Introduction") == "introduction"
        assert _match_section_type("1. Introduction") == "introduction"
        assert _match_section_type("1 Introduction") == "introduction"

    def test_match_methods(self):
        """Test matching methods section."""
        assert _match_section_type("Methods") == "methods"
        assert _match_section_type("Methodology") == "methods"
        assert _match_section_type("Materials and Methods") == "methods"
        assert _match_section_type("Materials & Methods") == "methods"
        assert _match_section_type("Experimental Section") == "methods"
        assert _match_section_type("Experimental Methods") == "methods"
        assert _match_section_type("2. Methods") == "methods"

    def test_match_results(self):
        """Test matching results section."""
        assert _match_section_type("Results") == "results"
        assert _match_section_type("Findings") == "results"
        assert _match_section_type("Results and Discussion") == "results"
        assert _match_section_type("Results & Discussion") == "results"

    def test_match_discussion(self):
        """Test matching discussion section."""
        assert _match_section_type("Discussion") == "discussion"
        assert _match_section_type("4. Discussion") == "discussion"

    def test_match_conclusion(self):
        """Test matching conclusion section."""
        assert _match_section_type("Conclusion") == "conclusion"
        assert _match_section_type("Conclusions") == "conclusion"
        assert _match_section_type("Concluding Remarks") == "conclusion"

    def test_match_references(self):
        """Test matching references section."""
        assert _match_section_type("References") == "references"
        assert _match_section_type("Bibliography") == "references"
        assert _match_section_type("Literature Cited") == "references"

    def test_match_acknowledgments(self):
        """Test matching acknowledgments section."""
        assert _match_section_type("Acknowledgments") == "acknowledgments"
        assert _match_section_type("Acknowledgements") == "acknowledgments"
        assert _match_section_type("Acknowledgment") == "acknowledgments"

    def test_no_match(self):
        """Test non-matching titles."""
        assert _match_section_type("Related Work") is None
        assert _match_section_type("Background") is None
        assert _match_section_type("Chapter 1") is None


class TestStructuredExtractor:
    """Tests for StructuredExtractor class."""

    @pytest.fixture
    def extractor(self):
        """Create extractor instance."""
        return StructuredExtractor()

    def test_extractor_creation(self, extractor):
        """Test extractor can be created."""
        assert extractor is not None
        assert extractor.config is not None

    def test_detect_document_type_paper(self, extractor):
        """Test paper detection based on standard sections."""
        blocks = [
            ContentBlock(type="title", content="Introduction", text_level=1),
            ContentBlock(type="text", content="This paper..."),
            ContentBlock(type="title", content="Methods", text_level=1),
            ContentBlock(type="text", content="We used..."),
            ContentBlock(type="title", content="Results", text_level=1),
            ContentBlock(type="text", content="Our findings..."),
            ContentBlock(type="title", content="Discussion", text_level=1),
            ContentBlock(type="text", content="These results..."),
        ]
        doc_type = extractor._detect_document_type(blocks)
        assert doc_type == "paper"

    def test_detect_document_type_book(self, extractor):
        """Test book detection based on chapter structure."""
        blocks = [
            ContentBlock(type="title", content="Chapter 1: Foundations", text_level=1),
            ContentBlock(type="text", content="In this chapter..."),
            ContentBlock(type="title", content="1.1 Basic Concepts", text_level=2),
            ContentBlock(type="text", content="We begin with..."),
            ContentBlock(type="title", content="1.2 Advanced Topics", text_level=2),
            ContentBlock(type="text", content="Moving on..."),
            ContentBlock(type="title", content="Chapter 2: Applications", text_level=1),
            ContentBlock(type="text", content="This chapter covers..."),
        ]
        # Add many pages to simulate a book
        for block in blocks:
            block.page_idx = 50  # High page count suggests book

        doc_type = extractor._detect_document_type(blocks)
        assert doc_type == "book"

    def test_extract_title_from_pre_section(self, extractor):
        """Test title extraction from pre-section blocks."""
        pre_blocks = [
            ContentBlock(type="title", content="A Novel Approach to ML", text_level=1, page_idx=0),
            ContentBlock(type="text", content="Author names..."),
        ]
        all_blocks = pre_blocks + [
            ContentBlock(type="title", content="Abstract", text_level=1),
        ]

        title = extractor._extract_title(pre_blocks, all_blocks)
        assert title == "A Novel Approach to ML"

    def test_extract_title_fallback(self, extractor):
        """Test title extraction fallback."""
        all_blocks = [
            ContentBlock(type="text", content="Some text"),
            ContentBlock(type="title", content="First Section", text_level=1),
        ]

        title = extractor._extract_title([], all_blocks)
        assert title == "First Section"

    def test_extract_tables(self, extractor):
        """Test table extraction from blocks."""
        blocks = [
            ContentBlock(type="text", content="Some text"),
            ContentBlock(type="table", content="<table><tr><td>Data</td></tr></table>"),
            ContentBlock(type="text", content="More text"),
            ContentBlock(type="table", content="<table><tr><td>More data</td></tr></table>"),
        ]

        tables = extractor._extract_tables(blocks)
        assert len(tables) == 2
        assert "Data" in tables[0]

    def test_find_abstract_in_blocks(self, extractor):
        """Test abstract detection from block content."""
        blocks = [
            ContentBlock(
                type="text",
                content="Abstract: This paper presents a novel approach...",
                page_idx=0,
            ),
            ContentBlock(type="text", content="Keywords: machine learning, AI"),
        ]

        abstract = extractor._find_abstract_in_blocks(blocks)
        assert abstract is not None
        assert "novel approach" in abstract
        assert "Abstract:" not in abstract

    def test_parse_content_blocks_from_content_list(self, extractor):
        """Test parsing content blocks from content_list format."""
        raw_result = {
            "content_list": [
                {"type": "text", "text": "Introduction text", "text_level": 0},
                {"type": "text", "text": "Methods", "text_level": 1},
                {"type": "text", "text": "Method details here", "text_level": 0},
                {"type": "table", "html": "<table></table>"},
                {"type": "image", "img_path": "figure1.png"},
            ]
        }

        blocks = extractor._parse_content_blocks(raw_result)

        assert len(blocks) == 5
        assert blocks[0].type == "text"
        assert blocks[0].content == "Introduction text"
        assert blocks[1].type == "title"  # text_level > 0 should be title
        assert blocks[1].text_level == 1
        assert blocks[3].type == "table"
        assert blocks[4].type == "image"

    def test_build_paper_structure(self, extractor):
        """Test building paper structure from blocks."""
        blocks = [
            ContentBlock(type="title", content="Test Paper Title", text_level=1, page_idx=0),
            ContentBlock(type="text", content="Author info", page_idx=0),
            ContentBlock(type="title", content="Abstract", text_level=1, page_idx=0),
            ContentBlock(type="text", content="This is the abstract text."),
            ContentBlock(type="title", content="Introduction", text_level=1),
            ContentBlock(type="text", content="Introduction paragraph."),
            ContentBlock(type="title", content="Methods", text_level=1),
            ContentBlock(type="text", content="Method details."),
            ContentBlock(type="title", content="Results", text_level=1),
            ContentBlock(type="text", content="Results description."),
            ContentBlock(type="title", content="Discussion", text_level=1),
            ContentBlock(type="text", content="Discussion text."),
            ContentBlock(type="title", content="Conclusion", text_level=1),
            ContentBlock(type="text", content="Conclusion text."),
        ]

        raw_result = {"figures": ["fig1.png"], "pdf_path": "/test.pdf"}
        paper = extractor._build_paper_structure(blocks, raw_result, "/test.pdf")

        assert paper.document_type == "paper"
        assert paper.abstract == "This is the abstract text."
        assert paper.introduction == "Introduction paragraph."
        assert paper.methods == "Method details."
        assert paper.results == "Results description."
        assert paper.discussion == "Discussion text."
        assert paper.conclusion == "Conclusion text."
        assert len(paper.sections) > 0

    def test_build_book_structure(self, extractor):
        """Test building book structure from blocks."""
        blocks = [
            ContentBlock(type="title", content="Chapter 1: Basics", text_level=1),
            ContentBlock(type="text", content="Chapter 1 intro."),
            ContentBlock(type="title", content="1.1 Overview", text_level=2),
            ContentBlock(type="text", content="Overview content."),
            ContentBlock(type="title", content="1.2 Details", text_level=2),
            ContentBlock(type="text", content="Details content."),
            ContentBlock(type="title", content="Chapter 2: Advanced", text_level=1),
            ContentBlock(type="text", content="Chapter 2 intro."),
        ]

        raw_result = {"figures": [], "pdf_path": "/book.pdf"}
        book = extractor._build_book_structure(blocks, raw_result, "/book.pdf")

        assert book.document_type == "book"
        assert len(book.chapters) == 2

        ch1 = book.chapters[0]
        assert ch1.title == "Chapter 1: Basics"
        assert len(ch1.children) == 2
        assert ch1.children[0].title == "1.1 Overview"
        assert ch1.children[1].title == "1.2 Details"

        ch2 = book.chapters[1]
        assert ch2.title == "Chapter 2: Advanced"
        assert len(ch2.children) == 0

        # Test search
        found = book.get_chapter("1.1 overview")
        assert found is not None
        assert found.level == 2
