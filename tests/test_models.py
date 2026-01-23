"""Tests for data models."""

from paper_ladder.models import (
    BookStructure,
    ChapterNode,
    ContentBlock,
    DocumentStructure,
    ExtractedContent,
    Paper,
    PaperStructure,
    SearchResult,
    Section,
)


class TestPaper:
    """Tests for Paper model."""

    def test_paper_creation(self):
        """Test basic paper creation."""
        paper = Paper(
            title="Test Paper",
            source="test",
        )
        assert paper.title == "Test Paper"
        assert paper.source == "test"
        assert paper.authors == []
        assert paper.abstract is None

    def test_paper_with_all_fields(self):
        """Test paper with all fields."""
        paper = Paper(
            title="Full Paper",
            authors=["Author 1", "Author 2"],
            abstract="Test abstract",
            doi="10.1234/test",
            year=2024,
            journal="Test Journal",
            url="https://example.com",
            pdf_url="https://example.com/paper.pdf",
            source="test",
            raw_data={"key": "value"},
            citations_count=100,
            open_access=True,
            keywords=["test", "paper"],
        )
        assert paper.title == "Full Paper"
        assert len(paper.authors) == 2
        assert paper.doi == "10.1234/test"
        assert paper.year == 2024
        assert paper.citations_count == 100

    def test_paper_equality_by_doi(self):
        """Test paper equality based on DOI."""
        paper1 = Paper(title="Paper 1", doi="10.1234/test", source="a")
        paper2 = Paper(title="Paper 2", doi="10.1234/TEST", source="b")
        assert paper1 == paper2

    def test_paper_equality_by_title(self):
        """Test paper equality based on title."""
        paper1 = Paper(title="Test Paper", source="a")
        paper2 = Paper(title="TEST PAPER", source="b")
        assert paper1 == paper2

    def test_paper_hash_by_doi(self):
        """Test paper hashing based on DOI."""
        paper1 = Paper(title="Paper 1", doi="10.1234/test", source="a")
        paper2 = Paper(title="Paper 2", doi="10.1234/TEST", source="b")
        assert hash(paper1) == hash(paper2)

    def test_paper_hash_by_title(self):
        """Test paper hashing based on title."""
        paper1 = Paper(title="Test Paper", source="a")
        paper2 = Paper(title="TEST PAPER", source="b")
        assert hash(paper1) == hash(paper2)


class TestExtractedContent:
    """Tests for ExtractedContent model."""

    def test_extracted_content_creation(self):
        """Test basic ExtractedContent creation."""
        content = ExtractedContent(markdown="# Test")
        assert content.markdown == "# Test"
        assert content.metadata == {}
        assert content.figures == []
        assert content.tables == []

    def test_extracted_content_full(self):
        """Test ExtractedContent with all fields."""
        content = ExtractedContent(
            markdown="# Test\nContent here",
            metadata={"title": "Test"},
            figures=["fig1.png", "fig2.png"],
            tables=["<table></table>"],
            source_url="https://example.com",
            source_type="pdf",
        )
        assert len(content.figures) == 2
        assert len(content.tables) == 1
        assert content.source_type == "pdf"


class TestSearchResult:
    """Tests for SearchResult model."""

    def test_search_result_creation(self):
        """Test basic SearchResult creation."""
        result = SearchResult(query="test")
        assert result.query == "test"
        assert result.papers == []
        assert result.errors == {}

    def test_search_result_with_papers(self):
        """Test SearchResult with papers."""
        papers = [
            Paper(title="Paper 1", source="a"),
            Paper(title="Paper 2", source="b"),
        ]
        result = SearchResult(
            query="test",
            papers=papers,
            total_results=2,
            sources_queried=["a", "b"],
        )
        assert len(result.papers) == 2
        assert result.total_results == 2
        assert "a" in result.sources_queried


class TestContentBlock:
    """Tests for ContentBlock model."""

    def test_content_block_creation(self):
        """Test basic ContentBlock creation."""
        block = ContentBlock(type="text", content="Hello world")
        assert block.type == "text"
        assert block.content == "Hello world"
        assert block.text_level == 0
        assert block.page_idx is None

    def test_content_block_title(self):
        """Test title ContentBlock."""
        block = ContentBlock(
            type="title",
            content="Introduction",
            text_level=1,
            page_idx=0,
            bbox=[100, 200, 500, 250],
        )
        assert block.type == "title"
        assert block.text_level == 1
        assert block.bbox == [100, 200, 500, 250]


class TestSection:
    """Tests for Section model."""

    def test_section_creation(self):
        """Test basic Section creation."""
        section = Section(title="Introduction", level=1)
        assert section.title == "Introduction"
        assert section.level == 1
        assert section.blocks == []
        assert section.subsections == []

    def test_section_with_blocks(self):
        """Test Section with content blocks."""
        blocks = [
            ContentBlock(type="text", content="First paragraph."),
            ContentBlock(type="text", content="Second paragraph."),
            ContentBlock(type="image", content="figure1.png"),
        ]
        section = Section(title="Methods", level=1, blocks=blocks)
        assert len(section.blocks) == 3
        assert section.get_text() == "First paragraph.\n\nSecond paragraph."

    def test_section_nested(self):
        """Test Section with subsections."""
        subsection = Section(
            title="Data Collection",
            level=2,
            blocks=[ContentBlock(type="text", content="We collected data...")],
        )
        section = Section(
            title="Methods",
            level=1,
            blocks=[ContentBlock(type="text", content="Overview of methods.")],
            subsections=[subsection],
        )
        assert len(section.subsections) == 1
        all_text = section.get_all_text()
        assert "Overview of methods" in all_text
        assert "We collected data" in all_text


class TestDocumentStructure:
    """Tests for DocumentStructure model."""

    def test_document_structure_creation(self):
        """Test basic DocumentStructure creation."""
        doc = DocumentStructure(title="Test Document")
        assert doc.title == "Test Document"
        assert doc.sections == []
        assert doc.document_type == "generic"

    def test_get_section(self):
        """Test finding section by title pattern."""
        sections = [
            Section(title="Introduction", level=1),
            Section(title="Methods", level=1),
            Section(title="Results and Discussion", level=1),
        ]
        doc = DocumentStructure(title="Test", sections=sections)

        intro = doc.get_section("intro")
        assert intro is not None
        assert intro.title == "Introduction"

        results = doc.get_section("results")
        assert results is not None
        assert "Results" in results.title

        missing = doc.get_section("conclusion")
        assert missing is None


class TestPaperStructure:
    """Tests for PaperStructure model."""

    def test_paper_structure_creation(self):
        """Test basic PaperStructure creation."""
        paper = PaperStructure(title="Test Paper")
        assert paper.document_type == "paper"
        assert paper.abstract is None
        assert paper.introduction is None

    def test_paper_structure_with_sections(self):
        """Test PaperStructure with standard sections."""
        paper = PaperStructure(
            title="Machine Learning Study",
            abstract="This paper presents...",
            introduction="Machine learning has...",
            methods="We used a neural network...",
            results="Our model achieved...",
            discussion="These results suggest...",
            conclusion="In conclusion...",
        )
        assert paper.abstract == "This paper presents..."
        assert paper.methods is not None
        assert paper.conclusion is not None


class TestChapterNode:
    """Tests for ChapterNode model."""

    def test_chapter_node_creation(self):
        """Test basic ChapterNode creation."""
        chapter = ChapterNode(title="Chapter 1: Basics", level=1)
        assert chapter.title == "Chapter 1: Basics"
        assert chapter.level == 1
        assert chapter.children == []

    def test_chapter_node_nested(self):
        """Test nested ChapterNode structure."""
        section = ChapterNode(
            title="1.1 Overview",
            level=2,
            content="This section covers...",
        )
        chapter = ChapterNode(
            title="Chapter 1",
            level=1,
            content="Introduction to the chapter.",
            children=[section],
        )
        assert len(chapter.children) == 1
        all_text = chapter.get_all_text()
        assert "Introduction to the chapter" in all_text
        assert "This section covers" in all_text


class TestBookStructure:
    """Tests for BookStructure model."""

    def test_book_structure_creation(self):
        """Test basic BookStructure creation."""
        book = BookStructure(title="Test Textbook")
        assert book.document_type == "book"
        assert book.chapters == []

    def test_book_structure_with_chapters(self):
        """Test BookStructure with chapter hierarchy."""
        chapters = [
            ChapterNode(
                title="Chapter 1: Foundations",
                level=1,
                children=[
                    ChapterNode(title="1.1 Basics", level=2),
                    ChapterNode(title="1.2 Advanced", level=2),
                ],
            ),
            ChapterNode(
                title="Chapter 2: Applications",
                level=1,
            ),
        ]
        book = BookStructure(title="ML Textbook", chapters=chapters)

        assert len(book.chapters) == 2
        ch1 = book.get_chapter("foundations")
        assert ch1 is not None
        assert len(ch1.children) == 2

        # Test nested search
        section = book.get_chapter("1.1 basics")
        assert section is not None
        assert section.level == 2

    def test_book_get_all_chapters_flat(self):
        """Test flattening chapter hierarchy."""
        chapters = [
            ChapterNode(
                title="Ch1",
                level=1,
                children=[
                    ChapterNode(title="1.1", level=2),
                    ChapterNode(title="1.2", level=2),
                ],
            ),
            ChapterNode(title="Ch2", level=1),
        ]
        book = BookStructure(title="Test", chapters=chapters)

        flat = book.get_all_chapters_flat()
        assert len(flat) == 4
        titles = [c.title for c in flat]
        assert "Ch1" in titles
        assert "1.1" in titles
        assert "Ch2" in titles
