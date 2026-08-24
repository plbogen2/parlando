"""Multi-Format Manuscript Ingest & Intelligent Web Scraper for Parlando."""

import dataclasses
import os
import re
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple


@dataclasses.dataclass
class Chapter:
    title: str
    content: str
    chapter_index: int
    word_count: int = 0


@dataclasses.dataclass
class ParsedDocument:
    title: str
    author: str
    chapters: List[Chapter]
    source_type: str
    metadata: Dict[str, str] = dataclasses.field(default_factory=dict)

    @property
    def total_words(self) -> int:
        return sum(c.word_count for c in self.chapters)

    @property
    def total_chapters(self) -> int:
        return len(self.chapters)

    def get_audition_excerpt(self, max_words: int = 1200) -> "ParsedDocument":
        """DRY helper to extract the first section/excerpt for instant auditioning."""
        if not self.chapters:
            return self

        first_chap = self.chapters[0]
        words = first_chap.content.split()
        if len(words) > max_words:
            excerpt_content = " ".join(words[:max_words]) + "..."
        else:
            excerpt_content = first_chap.content

        excerpt_chapter = Chapter(
            title=f"{first_chap.title} (Audition Excerpt)",
            content=excerpt_content,
            chapter_index=0,
            word_count=len(excerpt_content.split()),
        )
        return ParsedDocument(
            title=self.title,
            author=self.author,
            chapters=[excerpt_chapter],
            source_type=self.source_type,
            metadata=self.metadata,
        )


class DocumentParser:
    """Ingests Markdown, Plain Text, EPUB, PDF, HTML files, or live Web URLs."""

    @classmethod
    def from_file_or_url(cls, target: str) -> ParsedDocument:
        if target.startswith("http://") or target.startswith("https://"):
            return cls.from_url(target)
        if not os.path.exists(target):
            raise FileNotFoundError(f"Input file not found: {target}")

        ext = os.path.splitext(target)[1].lower()
        if ext in (".md", ".markdown"):
            return cls.from_markdown_file(target)
        elif ext in (".html", ".htm"):
            return cls.from_html_file(target)
        elif ext == ".pdf":
            return cls.from_pdf_file(target)
        elif ext == ".epub":
            return cls.from_epub_file(target)
        else:
            return cls.from_text_file(target)

    @classmethod
    def from_text(cls, raw_text: str, title: str = "Untitled Manuscript", author: str = "Unknown Author") -> ParsedDocument:
        cleaned = cls.clean_prose(raw_text)
        chapters = cls._split_into_chapters(cleaned)
        return ParsedDocument(
            title=title,
            author=author,
            chapters=chapters,
            source_type="TEXT",
        )

    @classmethod
    def from_text_file(cls, filepath: str) -> ParsedDocument:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        title = os.path.splitext(os.path.basename(filepath))[0].replace("_", " ").title()
        return cls.from_text(content, title=title)

    @classmethod
    def from_markdown_file(cls, filepath: str) -> ParsedDocument:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        title = os.path.splitext(os.path.basename(filepath))[0].replace("_", " ").title()
        author = "Unknown Author"
        meta = {}

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1]
                content = parts[2]
                for line in frontmatter.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        k = k.strip().lower()
                        v = v.strip().strip('"').strip("'")
                        meta[k] = v
                        if k == "title":
                            title = v
                        elif k == "author":
                            author = v

        cleaned = cls.clean_prose(content)
        chapters = cls._split_into_chapters(cleaned)
        return ParsedDocument(
            title=title,
            author=author,
            chapters=chapters,
            source_type="MARKDOWN",
            metadata=meta,
        )

    @classmethod
    def from_html_file(cls, filepath: str) -> ParsedDocument:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            html = f.read()
        return cls.from_html_string(html, base_url=filepath)

    @classmethod
    def from_url(cls, url: str) -> ParsedDocument:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Parlando/1.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        parsed_doc = cls.from_html_string(html, base_url=url)
        parsed_doc.source_type = "WEB_URL"
        parsed_doc.metadata["url"] = url
        return parsed_doc

    @classmethod
    def from_html_string(cls, html_content: str, base_url: str = "") -> ParsedDocument:
        try:
            from bs4 import BeautifulSoup, Comment
        except ImportError:
            raw_text = re.sub(r"<[^>]+>", " ", html_content)
            return cls.from_text(raw_text)

        soup = BeautifulSoup(html_content, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "aside", "header", "form", "noscript"]):
            tag.decompose()

        for comment in soup.find_all(text=lambda text: isinstance(text, Comment)):
            comment.extract()

        title = "Web Article"
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        author = "Unknown Author"
        meta_author = soup.find("meta", attrs={"name": re.compile(r"author", re.I)})
        if meta_author and meta_author.get("content"):
            author = meta_author["content"].strip()

        # Byline search
        byline_match = re.search(r'([A-Za-z0-9\s,\'’\-]+)\s+--\s+(?:a\s+novelette\s+)?by\s+([A-Za-z0-9\s\.\-]+)', html_content, re.IGNORECASE)
        if byline_match:
            candidate_title = byline_match.group(1).strip()
            candidate_author = byline_match.group(2).strip()
            if candidate_title and not title.lower().startswith("infinity"):
                title = candidate_title
            if candidate_author:
                author = candidate_author

        # Find best content container
        candidates = soup.find_all(["article", "main", "div", "td", "body"])
        best_elem = soup.body or soup
        best_score = 0

        for cand in candidates:
            paras = cand.find_all("p")
            word_count = sum(len(p.get_text().split()) for p in paras)
            if word_count > best_score:
                best_score = word_count
                best_elem = cand

        lines = []
        for elem in best_elem.find_all(["h1", "h2", "h3", "h4", "p", "blockquote"]):
            text = elem.get_text().strip()
            if not text:
                continue
            if elem.name in ("h1", "h2", "h3", "h4"):
                lines.append(f"# {text}")
            elif elem.name == "p" and elem.find("b") and len(text.split()) <= 10:
                lines.append(f"# {text}")
            else:
                lines.append(text)

        full_prose = "\n\n".join(lines)
        cleaned = cls.clean_prose(full_prose)
        chapters = cls._split_into_chapters(cleaned)

        return ParsedDocument(
            title=title,
            author=author,
            chapters=chapters,
            source_type="HTML",
        )

    @classmethod
    def from_pdf_file(cls, filepath: str) -> ParsedDocument:
        try:
            import pypdf
            reader = pypdf.PdfReader(filepath)
            text_pages = [page.extract_text() for page in reader.pages if page.extract_text()]
            full_text = "\n\n".join(text_pages)
        except Exception:
            full_text = f"Failed to parse PDF file: {filepath}"

        title = os.path.splitext(os.path.basename(filepath))[0].replace("_", " ").title()
        return cls.from_text(full_text, title=title)

    @classmethod
    def from_epub_file(cls, filepath: str) -> ParsedDocument:
        import zipfile
        title = os.path.splitext(os.path.basename(filepath))[0].replace("_", " ").title()
        chapters = []

        try:
            with zipfile.ZipFile(filepath, "r") as zf:
                html_files = [f for f in zf.namelist() if f.endswith((".html", ".xhtml", ".htm"))]
                for idx, hf in enumerate(html_files):
                    content = zf.read(hf).decode("utf-8", errors="replace")
                    doc = cls.from_html_string(content)
                    if doc.chapters:
                        for ch in doc.chapters:
                            if ch.content.strip():
                                chapters.append(Chapter(
                                    title=ch.title if ch.title != "Chapter 1" else f"Section {idx+1}",
                                    content=ch.content,
                                    chapter_index=len(chapters),
                                    word_count=ch.word_count,
                                ))
        except Exception as e:
            chapters = [Chapter(title="Chapter 1", content=f"EPUB parsing error: {e}", chapter_index=0, word_count=5)]

        return ParsedDocument(title=title, author="Unknown", chapters=chapters, source_type="EPUB")

    @classmethod
    def clean_prose(cls, text: str) -> str:
        s = text
        s = s.replace("\r\n", "\n").replace("\r", "\n")
        s = re.sub(r'(\w+)-\n(\w+)', r'\1\2', s)
        s = re.sub(r'(?<=\w)\n(?=\w)', ' ', s)
        s = re.sub(r'[ \t]+', ' ', s)
        s = re.sub(r'\n{3,}', '\n\n', s)
        return s.strip()

    @classmethod
    def _split_into_chapters(cls, text: str) -> List[Chapter]:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            return [Chapter(title="", content="", chapter_index=0, word_count=0)]

        has_headings = any(p.startswith("#") for p in paragraphs)
        if not has_headings:
            word_count = len(text.split())
            return [Chapter(title="", content=text, chapter_index=0, word_count=word_count)]

        chapters: List[Chapter] = []
        current_title = "Prologue"
        current_paras: List[str] = []

        for p in paragraphs:
            if p.startswith("#"):
                if current_paras:
                    body = "\n\n".join(current_paras)
                    chapters.append(Chapter(
                        title=current_title,
                        content=body,
                        chapter_index=len(chapters),
                        word_count=len(body.split()),
                    ))
                    current_paras = []
                current_title = re.sub(r"^#+\s*", "", p).strip()
            else:
                current_paras.append(p)

        if current_paras:
            body = "\n\n".join(current_paras)
            chapters.append(Chapter(
                title=current_title,
                content=body,
                chapter_index=len(chapters),
                word_count=len(body.split()),
            ))

        return chapters or [Chapter(title="Chapter 1", content=text, chapter_index=0, word_count=len(text.split()))]
