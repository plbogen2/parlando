"""Document parser and normalization module for plain text, Markdown, EPUB, HTML, PDF, and Web URLs."""

import os
import re
import shutil
import ssl
import subprocess
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import bs4

BeautifulSoup = bs4.BeautifulSoup


@dataclass
class Chapter:
    """Represents a single chapter or section in a document."""
    chapter_num: int
    title: str
    content: str
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """Container for the fully parsed manuscript."""
    title: str
    author: str
    chapters: List[Chapter] = field(default_factory=list)
    source_format: str = "text"
    raw_text: str = ""
    source_url: Optional[str] = None


class DocumentParser:
    """Multi-format manuscript ingest engine supporting local files and web URLs."""

    @classmethod
    def parse_target(
        cls,
        target: str,
        title: Optional[str] = None,
        author: Optional[str] = None,
    ) -> ParsedDocument:
        """Ingest and parse either a local manuscript path or a live web URL."""
        if target.startswith("http://") or target.startswith("https://"):
            return cls.parse_url(target, title, author)
        else:
            return cls.parse_file(target, title, author)

    @classmethod
    def parse_url(
        cls,
        url: str,
        title: Optional[str] = None,
        author: Optional[str] = None,
        timeout_sec: int = 20,
    ) -> ParsedDocument:
        """Fetch and extract clean prose/article content from a live HTTP/HTTPS URL."""
        parsed_url = urllib.parse.urlparse(url)
        clean_url = urllib.parse.urlunparse(parsed_url._replace(fragment=""))
        fragment = parsed_url.fragment

        # Build resilient SSL context
        try:
            ctx = ssl.create_default_context()
        except Exception:
            ctx = ssl._create_unverified_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(
            clean_url,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 AudiobookNarrator/1.0",
                "Accept": "text/html,application/xhtml+xml,application/xml,text/plain,text/markdown;q=0.9,*/*;q=0.8",
            },
        )

        with urllib.request.urlopen(req, context=ctx, timeout=timeout_sec) as resp:
            content_type = resp.headers.get("Content-Type", "").lower()
            raw_bytes = resp.read()

        charset = "utf-8"
        if "charset=" in content_type:
            charset = content_type.split("charset=")[-1].split(";")[0].strip()

        raw_text = raw_bytes.decode(charset, errors="replace")

        url_path = parsed_url.path.lower()
        fallback_title = title or parsed_url.netloc + url_path
        doc_author = author or "Unknown Author"

        if url_path.endswith(".md") or "text/markdown" in content_type:
            doc = cls._parse_markdown_string(raw_text, fallback_title, doc_author)
            doc.source_url = url
            return doc
        elif url_path.endswith(".txt") or "text/plain" in content_type:
            chapters = cls._split_into_chapters(raw_text, fallback_title)
            return ParsedDocument(
                title=fallback_title,
                author=doc_author,
                chapters=chapters,
                source_format="txt",
                raw_text=raw_text,
                source_url=url,
            )

        # Default to HTML article extraction with anchor fragment awareness
        return cls._parse_html_string(
            raw_html=raw_text,
            default_title=fallback_title,
            default_author=doc_author,
            url=url,
            fragment=fragment,
        )

    @classmethod
    def parse_file(
        cls,
        file_path: str,
        title: Optional[str] = None,
        author: Optional[str] = None,
    ) -> ParsedDocument:
        """Parse a local file based on its file extension."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Manuscript not found at: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()
        basename = os.path.splitext(os.path.basename(file_path))[0]
        doc_title = title or basename.replace("_", " ").replace("-", " ").title()
        doc_author = author or "Unknown Author"

        if ext == ".md":
            return cls.parse_markdown(file_path, doc_title, doc_author)
        elif ext == ".epub":
            return cls.parse_epub(file_path, doc_title, doc_author)
        elif ext in [".html", ".htm"]:
            return cls.parse_html(file_path, doc_title, doc_author)
        elif ext == ".pdf":
            return cls.parse_pdf(file_path, doc_title, doc_author)
        else:
            return cls.parse_plain_text(file_path, doc_title, doc_author)

    @classmethod
    def parse_text(cls, raw_text: str, title: str = "Audiobook", author: str = "Unknown Author") -> ParsedDocument:
        """Parse in-memory raw text directly into a ParsedDocument."""
        chapters = cls._split_into_chapters(raw_text, title)
        return ParsedDocument(
            title=title,
            author=author,
            chapters=chapters,
            source_format="text",
            raw_text=raw_text,
        )

    @classmethod
    def parse_pdf(
        cls,
        file_path: str,
        title: Optional[str] = None,
        author: Optional[str] = None,
    ) -> ParsedDocument:
        """Extract and parse structured manuscript from a PDF document."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF manuscript not found at: {file_path}")

        basename = os.path.splitext(os.path.basename(file_path))[0]
        doc_title = title or basename.replace("_", " ").replace("-", " ").title()
        doc_author = author or "Unknown Author"

        raw_text, meta_title, meta_author = cls._extract_text_from_pdf(file_path)
        if (not title or title == basename.replace("_", " ").replace("-", " ").title()) and meta_title:
            doc_title = meta_title
        if (not author or author == "Unknown Author") and meta_author:
            doc_author = meta_author

        cleaned_text = cls._clean_pdf_text(raw_text)
        chapters = cls._split_into_chapters(cleaned_text, doc_title)

        return ParsedDocument(
            title=doc_title,
            author=doc_author,
            chapters=chapters,
            source_format="pdf",
            raw_text=cleaned_text,
        )

    @classmethod
    def _extract_text_from_pdf(cls, file_path: str) -> Tuple[str, Optional[str], Optional[str]]:
        """Extract text and metadata from PDF using pdftotext CLI, pdf-reader CLI, or Python libraries."""
        meta_title = None
        meta_author = None

        # 1. Try reading metadata via pdfinfo if present
        pdfinfo_bin = shutil.which("pdfinfo")
        if pdfinfo_bin:
            try:
                res = subprocess.run([pdfinfo_bin, file_path], capture_output=True, text=True, check=False)
                if res.returncode == 0 and res.stdout:
                    for line in res.stdout.splitlines():
                        if line.startswith("Title:"):
                            t = line.split("Title:", 1)[1].strip()
                            if t and t.lower() != "untitled":
                                meta_title = t
                        elif line.startswith("Author:"):
                            a = line.split("Author:", 1)[1].strip()
                            if a:
                                meta_author = a
            except Exception:
                pass

        # 2. Extract text using /usr/bin/pdftotext (standard poppler utility)
        pdftotext_bin = shutil.which("pdftotext")
        if pdftotext_bin:
            try:
                res = subprocess.run([pdftotext_bin, file_path, "-"], capture_output=True, text=True, check=False)
                if res.returncode == 0 and res.stdout.strip():
                    return res.stdout, meta_title, meta_author
            except Exception:
                pass

        # 3. Try /google/bin/releases/gemini-agents-pdf-reader/read_pdf_cli if available
        g3_pdf_reader = "/google/bin/releases/gemini-agents-pdf-reader/read_pdf_cli"
        if os.path.exists(g3_pdf_reader):
            try:
                res = subprocess.run([g3_pdf_reader, f"--file={file_path}", "--text_only"], capture_output=True, text=True, check=False)
                if res.returncode == 0 and res.stdout.strip():
                    return res.stdout, meta_title, meta_author
            except Exception:
                pass

        # 4. Fallback to python libraries (pypdf, pypdf2, pypdfium2, fitz)
        for mod_name in ["pypdf", "pypdf2", "fitz", "pdfminer"]:
            try:
                if mod_name in ["pypdf", "pypdf2"]:
                    pypdf = __import__(mod_name)
                    reader = pypdf.PdfReader(file_path)
                    if not meta_title and reader.metadata and reader.metadata.title:
                        meta_title = reader.metadata.title
                    if not meta_author and reader.metadata and reader.metadata.author:
                        meta_author = reader.metadata.author
                    pages = []
                    for page in reader.pages:
                        t = page.extract_text()
                        if t:
                            pages.append(t)
                    if pages:
                        return "\n\x0c\n".join(pages), meta_title, meta_author
                elif mod_name == "fitz":
                    fitz = __import__(mod_name)
                    doc = fitz.open(file_path)
                    pages = [page.get_text() for page in doc]
                    if pages:
                        return "\n\x0c\n".join(pages), meta_title, meta_author
            except Exception:
                pass

        raise RuntimeError(
            f"Unable to extract text from PDF: {file_path}. Please ensure 'pdftotext' (poppler-utils) is installed."
        )

    @classmethod
    def _clean_pdf_text(cls, raw_text: str) -> str:
        """Post-process extracted PDF text, removing page numbers, joining hyphens, and preserving chapter headings."""
        pages = [p for p in raw_text.split("\x0c") if p.strip()]
        cleaned_pages = []

        for page in pages:
            lines = page.splitlines()
            filtered_lines = []
            for line in lines:
                stripped = line.strip()
                # Drop standalone page numbers (e.g. "1", "42", "Page 3", "Page 3 of 50", "- 4 -")
                if re.match(r"^(?:page\s+)?\d+(?:\s+of\s+\d+)?$", stripped, re.IGNORECASE):
                    continue
                if re.match(r"^[-—–]\s*\d+\s*[-—–]$", stripped):
                    continue
                filtered_lines.append(line)

            page_text = "\n".join(filtered_lines)
            cleaned_pages.append(page_text)

        combined = "\n\n".join(cleaned_pages)

        # Rejoin hyphenated words split across line breaks (e.g. "neuro-\nmancer" -> "neuromancer")
        combined = re.sub(r'(\b[a-zA-Z]{2,})-\n\s*([a-zA-Z]{2,}\b)', r'\1\2', combined)

        lines = combined.splitlines()
        rejoined = []

        heading_pattern = re.compile(
            r"^(?:chapter\s+(?:\d+|[ivxlcdm]+|[a-z]+)|prologue|epilogue|part\s+(?:\d+|[ivxlcdm]+|[a-z]+)|act\s+(?:\d+|[ivxlcdm]+)|book\s+(?:\d+|[ivxlcdm]+)|section\s+\d+|scene\s+\d+)",
            re.IGNORECASE,
        )

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if rejoined and rejoined[-1] != "":
                    rejoined.append("")
                continue

            is_heading = bool(heading_pattern.match(stripped)) or (len(stripped) < 60 and stripped.isupper() and len(stripped) > 3)

            if is_heading:
                if rejoined and rejoined[-1] != "":
                    rejoined.append("")
                rejoined.append(stripped)
                rejoined.append("")
                continue

            if not rejoined or rejoined[-1] == "":
                rejoined.append(stripped)
            elif not rejoined[-1].endswith((".", "!", "?", ":", '"', "'", "—", "”")):
                rejoined[-1] = rejoined[-1] + " " + stripped
            else:
                rejoined.append(stripped)

        result = "\n".join(rejoined)
        result = re.sub(r'\n{3,}', '\n\n', result)
        return cls.clean_prose_text(result)

    @classmethod
    def parse_plain_text(cls, file_path: str, title: str, author: str) -> ParsedDocument:
        """Parse a plain text file, detecting chapter headers if present."""
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()

        chapters = cls._split_into_chapters(raw, title)
        return ParsedDocument(
            title=title,
            author=author,
            chapters=chapters,
            source_format="txt",
            raw_text=raw,
        )

    @classmethod
    def parse_markdown(cls, file_path: str, title: str, author: str) -> ParsedDocument:
        """Parse a markdown file, stripping formatting and extracting chapter structure."""
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
        return cls._parse_markdown_string(raw, title, author)

    @classmethod
    def _parse_markdown_string(cls, raw: str, title: str, author: str) -> ParsedDocument:
        """Parse markdown string directly."""
        metadata = {}
        content = raw
        if raw.startswith("---"):
            parts = raw.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1]
                content = parts[2]
                for line in frontmatter.strip().splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        metadata[k.strip().lower()] = v.strip().strip('"\'')

        if "title" in metadata:
            title = metadata["title"]
        if "author" in metadata:
            author = metadata["author"]

        chapters = cls._split_markdown_chapters(content, title)
        return ParsedDocument(
            title=title,
            author=author,
            chapters=chapters,
            source_format="markdown",
            raw_text=content,
        )

    @classmethod
    def parse_html(cls, file_path: str, title: str, author: str) -> ParsedDocument:
        """Parse an HTML manuscript from a file."""
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
        return cls._parse_html_string(raw, title, author)

    @classmethod
    def _parse_html_string(
        cls,
        raw_html: str,
        default_title: str,
        default_author: str,
        url: Optional[str] = None,
        fragment: Optional[str] = None,
    ) -> ParsedDocument:
        """Extract clean narrative prose from HTML structure, isolating article content from navigation and presentational clutter."""
        soup = BeautifulSoup(raw_html, "html.parser")

        # 1. Metadata discovery (Title & Author)
        title = default_title
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()
        elif soup.h1:
            title = soup.h1.get_text().strip()

        # Clean HTML tags and publisher/platform branding suffixes from title
        if "<" in title:
            title = BeautifulSoup(title, "html.parser").get_text()
        title = re.sub(
            r"\s*[-–—|]\s*(?:baen(?:\s*books|\s*ebooks)?|royal\s*road|archive\s*of\s*our\s*own|ao3|wattpad|tor(?:\.com)?|project\s*gutenberg|infinity\s*plus|read\s*online|chapter\s*\d+).*$",
            "",
            title,
            flags=re.IGNORECASE,
        )
        title = re.sub(r"^[-\s—–:•|]+|[-\s—–:•|]+$", "", title).strip() or default_title

        author = default_author
        meta_author = soup.find("meta", attrs={"name": "author"}) or soup.find("meta", property="article:author")
        if meta_author and meta_author.get("content"):
            a_text = meta_author["content"].strip()
            if "<" in a_text:
                a_text = BeautifulSoup(a_text, "html.parser").get_text()
            author = a_text

        # Extract title and author if formatted as: "Story Title -- a novelette by Author Name" or "Story Title by Author"
        byline_patterns = [
            re.compile(r"^(.*?)\s*(?:--|-|–|—|:)\s*(?:(?:a\s+)?(?:novell?a|novelette|short\s+story|story|novel|book|fiction)\s+)?by\s+([A-Za-z0-9\.\s\-]+)$", re.IGNORECASE),
            re.compile(r"^(.*?)\s+\bby\s+([A-Za-z0-9\.\s\-]+)$", re.IGNORECASE),
        ]
        for pat in byline_patterns:
            m = pat.match(title)
            if m:
                extracted_title = m.group(1).strip()
                extracted_author = m.group(2).strip()
                if extracted_title and len(extracted_title) > 2:
                    title = extracted_title
                if extracted_author and (author in [default_author, "Unknown Author", "Author"] or not author):
                    author = extracted_author
                break

        # Also search for <p class="byline">, <div class="byline">, <span>, etc. if author is still default
        if author in [default_author, "Unknown Author", "Author"]:
            byline_el = soup.find(class_=re.compile(r"byline|author|story-author", re.IGNORECASE))
            if byline_el:
                b_text = byline_el.get_text().strip()
                b_match = re.search(r"(?:by\s+)?([A-Za-z0-9\.\s\-]+)", b_text, re.IGNORECASE)
                if b_match and len(b_match.group(1).strip()) > 2:
                    author = b_match.group(1).strip()

        # 2. Decompose unquestionable junk elements
        for element in soup(["script", "style", "nav", "header", "footer", "aside", "form", "button", "iframe", "noscript", "svg", "canvas", "picture"]):
            element.decompose()

        # 3. Targeted noise widget pruning (only leaf widgets, never layout containers)
        noise_widget_patterns = re.compile(
            r"(ad-|ad_|advert|banner|comment|social|share|widget|cookie|popup|modal|signup|subscribe|promo|pagination|pager|chapter-nav|breadcrumb|copyright|meta-bar)",
            re.IGNORECASE,
        )
        for el in list(soup.find_all(True)):
            if not hasattr(el, "attrs") or not el.attrs:
                continue
            classes = el.get("class", [])
            class_str = " ".join(classes) if isinstance(classes, list) else str(classes)
            el_id = str(el.get("id", ""))
            combined_id = f"{class_str} {el_id}".strip()

            if combined_id and noise_widget_patterns.search(combined_id):
                p_count = len(el.find_all("p"))
                if p_count <= 2:
                    el.decompose()

        boilerplate_patterns = re.compile(
            r"^(?:next\s+chapter|previous\s+chapter|table\s+of\s+contents|all\s+rights\s+reserved|share\s+on|published\s+by|sign\s+up\s+for|copyright|\&copy\;|\(c\)\s+\d{4}|back\s*\|\s*next|contents\s*\|\s*next|support\s+this\s+site|elsewhere\s+in|elsewhere\s+on\s+the\s+web|buy\s+books\s+through)",
            re.IGNORECASE,
        )
        nav_link_words = re.compile(r"^(?:back|next|contents|toc|home|top|index|framed|unframed|previous|next\s+chapter|prev\s+chapter)$", re.IGNORECASE)

        def _is_nav_paragraph(el, text: str) -> bool:
            if boilerplate_patterns.search(text):
                return True
            if re.match(r"^(\&laquo\;|\&raquo\;|<<|>>|<|>|\xab|\xbb)?\s*(prev|next|toc|home|top|contents|previous\s+chapter|next\s+chapter|back\s*\|\s*next)\s*(\&laquo\;|\&raquo\;|<<|>>|<|>|\xab|\xbb)?$", text, re.IGNORECASE):
                return True
            a_tags = el.find_all("a")
            if a_tags:
                a_chars = sum(len(a.get_text().strip()) for a in a_tags)
                if len(text) > 0 and (a_chars / float(len(text))) > 0.35:
                    words = [w.strip(" |[]()<>/»«") for w in text.split() if w.strip(" |[]()<>/»«")]
                    if all(nav_link_words.match(w) for w in words if w):
                        return True
            return False

        # Case 1: Specific anchor/fragment target (e.g. #Lobsters or #Chapter_2)
        if fragment:
            anchor = (
                soup.find(attrs={"name": fragment}) or
                soup.find(id=fragment) or
                soup.find(attrs={"name": fragment.lower()}) or
                soup.find(id=fragment.lower())
            )
            if anchor:
                chap_title = anchor.get_text().strip() or fragment
                paragraphs = []
                curr = anchor
                while curr:
                    curr = curr.find_next()
                    if not curr:
                        break
                    if curr.name == "a" and curr.get("name") and curr.get("name") != fragment and "chapter" in curr.get_text().lower():
                        break
                    if curr.name in ["h1", "h2", "h3"] and curr != anchor and ("chapter" in curr.get_text().lower() or "part" in curr.get_text().lower()):
                        break
                    if curr.name == "p":
                        p_txt = curr.get_text().strip()
                        if p_txt and not _is_nav_paragraph(curr, p_txt) and (not paragraphs or p_txt != paragraphs[-1]):
                            paragraphs.append(p_txt)

                chapter_content = cls.clean_prose_text("\n\n".join(paragraphs))
                full_title = f"{title} - {chap_title}" if title != chap_title else title
                chapter = Chapter(
                    chapter_num=1,
                    title=chap_title,
                    content=chapter_content,
                )
                return ParsedDocument(
                    title=full_title,
                    author=author,
                    chapters=[chapter],
                    source_format="html",
                    raw_text=chapter_content,
                    source_url=url,
                )

        # Case 2: Multi-chapter document with named anchors/headers (<a name="Chapter...">, <h1>, <h2>)
        named_anchors = []
        for a in soup.find_all("a", attrs={"name": True}):
            txt = a.get_text().strip()
            name = a.get("name")
            if "chapter" in txt.lower():
                named_anchors.append((name, txt, a))

        if named_anchors:
            chapters = []
            for i, (name, chap_title, anchor) in enumerate(named_anchors):
                paragraphs = []
                curr = anchor
                while curr:
                    curr = curr.find_next()
                    if not curr:
                        break
                    if curr.name == "a" and curr.get("name") and curr != anchor:
                        next_txt = curr.get_text().strip().lower()
                        if "chapter" in next_txt or "part" in next_txt:
                            break
                    if curr.name in ["h1", "h2", "h3"] and curr != anchor:
                        h_txt = curr.get_text().strip().lower()
                        if "chapter" in h_txt or "part" in h_txt:
                            break
                    if curr.name == "p":
                        p_txt = curr.get_text().strip()
                        if p_txt and not _is_nav_paragraph(curr, p_txt) and (not paragraphs or p_txt != paragraphs[-1]):
                            paragraphs.append(p_txt)

                chap_text = cls.clean_prose_text("\n\n".join(paragraphs))
                if chap_text:
                    chapters.append(Chapter(
                        chapter_num=len(chapters) + 1,
                        title=chap_title,
                        content=chap_text,
                    ))

            if chapters:
                full_combined = "\n\n".join(c.content for c in chapters)
                return ParsedDocument(
                    title=title,
                    author=author,
                    chapters=chapters,
                    source_format="html",
                    raw_text=full_combined,
                    source_url=url,
                )

        # Case 3: Content Container Selection & Prose Extraction
        content_whitelists = re.compile(
            r"(content|story|chapter|article|body|reading|entry|post|text|prose|novel)",
            re.IGNORECASE,
        )

        body_p_count = len(soup.find_all("p"))
        candidates = []
        for container in soup.find_all(["article", "main", "section", "div"]):
            p_tags = container.find_all("p")
            if len(p_tags) >= 5:
                p_len = sum(len(p.get_text().strip()) for p in p_tags)
                classes = container.get("class", [])
                class_str = " ".join(classes) if isinstance(classes, list) else str(classes)
                el_id = str(container.get("id", ""))
                combined_id = f"{class_str} {el_id}".lower()
                bonus = 300 if content_whitelists.search(combined_id) else 0
                candidates.append((p_len + bonus, len(p_tags), container))

        candidates.sort(key=lambda x: x[0], reverse=True)

        if candidates and candidates[0][1] >= (body_p_count * 0.8):
            best_container = candidates[0][2]
        else:
            best_container = soup.body or soup

        # 4. Extract clean prose paragraphs & headings
        clean_paragraphs = []
        elements = best_container.find_all(["p", "h1", "h2", "h3", "h4", "blockquote"])
        if not elements:
            raw_inner = best_container.get_text(separator="\n\n")
            lines = [line.strip() for line in raw_inner.splitlines() if line.strip()]
            for line in lines:
                if not boilerplate_patterns.search(line) and len(line) > 15:
                    clean_paragraphs.append(line)
        else:
            for el in elements:
                # Avoid collecting <p> if already collected inside a blockquote
                if el.name == "p" and el.find_parent("blockquote") and best_container.name != "blockquote":
                    continue
                txt = el.get_text().strip()
                if not txt or _is_nav_paragraph(el, txt):
                    continue

                clean_line = " ".join(txt.split())
                is_heading = el.name in ["h1", "h2", "h3", "h4"]
                if not is_heading and el.name in ["p", "div"]:
                    b_tag = el.find(["b", "strong"])
                    if b_tag and len(" ".join(b_tag.get_text().split())) == len(clean_line) and len(clean_line) <= 60:
                        is_heading = True

                if is_heading:
                    clean_paragraphs.append(f"## {clean_line}")
                else:
                    if len(clean_line) >= 2:
                        clean_paragraphs.append(clean_line)

        # Discard leading title/byline paragraph if it matches metadata
        if clean_paragraphs:
            first_p_norm = " ".join(clean_paragraphs[0].lower().split())
            t_norm = " ".join(title.lower().split())
            a_norm = " ".join(author.lower().split())
            if (t_norm in first_p_norm) and (a_norm in first_p_norm or "by " in first_p_norm or "novelette" in first_p_norm or "story" in first_p_norm or "novel" in first_p_norm):
                clean_paragraphs.pop(0)

        full_text = "\n\n".join(clean_paragraphs)
        cleaned_text = cls.clean_prose_text(full_text)
        if "## " in cleaned_text or "# " in cleaned_text:
            chapters = cls._split_markdown_chapters(cleaned_text, title)
        else:
            chapters = cls._split_into_chapters(cleaned_text, title)

        return ParsedDocument(
            title=title,
            author=author,
            chapters=chapters,
            source_format="html",
            raw_text=cleaned_text,
            source_url=url,
        )

    @classmethod
    def parse_epub(cls, file_path: str, title: str, author: str) -> ParsedDocument:
        """Parse an EPUB archive by extracting XHTML documents in spine order."""
        chapters: List[Chapter] = []
        raw_combined = []
        
        with zipfile.ZipFile(file_path, "r") as zf:
            html_files = [f for f in zf.namelist() if f.lower().endswith((".xhtml", ".html", ".htm"))]
            html_files.sort()

            chap_num = 1
            for hf in html_files:
                try:
                    content = zf.read(hf).decode("utf-8", errors="replace")
                    soup = BeautifulSoup(content, "html.parser")
                    
                    for element in soup(["script", "style", "nav", "header", "footer"]):
                        element.decompose()
                    
                    chap_title = f"Chapter {chap_num}"
                    h_tag = soup.find(["h1", "h2", "h3"])
                    if h_tag:
                        chap_title = h_tag.get_text().strip()

                    text = soup.get_text(separator="\n\n")
                    cleaned = cls.clean_prose_text(text)
                    if len(cleaned.strip()) > 50:
                        chapters.append(Chapter(
                            chapter_num=chap_num,
                            title=chap_title,
                            content=cleaned,
                        ))
                        raw_combined.append(cleaned)
                        chap_num += 1
                except Exception:
                    continue

        if not chapters:
            chapters = [Chapter(chapter_num=1, title=title, content="")]

        return ParsedDocument(
            title=title,
            author=author,
            chapters=chapters,
            source_format="epub",
            raw_text="\n\n".join(raw_combined),
        )

    @classmethod
    def clean_prose_text(cls, text: str) -> str:
        """Normalize unicode quotes, dashes, spacing, and Markdown artifact noise."""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        
        # Normalize double smart quotes to standard double quote "
        text = text.replace("“", '"').replace("”", '"').replace("„", '"')
        
        # Normalize inside-word curly apostrophes to ASCII single apostrophe (e.g. Manfred’s -> Manfred's, don’t -> don't)
        text = re.sub(r'(\w)[’‘](\w)', r"\1'\2", text)
        
        # Normalize leading/trailing word apostrophes (e.g. 't, 'bout, 'round, 'em)
        text = re.sub(r'(^|[\s—\(])’(\w)', r"\1'\2", text)
        text = re.sub(r'(\w)’([\s—,\.!\?;:\)]|$)', r"\1'\2", text)

        # Convert standalone single-quoted dialogue ('Hello world!') to double quotes ("Hello world!")
        def _convert_single_quote_dialogue(m):
            prefix = m.group(1)
            inner = m.group(2)
            suffix = m.group(3)
            # Ensure it's not a standalone contraction like 't
            if len(inner.strip()) > 1 and not re.match(r"^[stmdlvnSTMDLVN]$", inner.strip()):
                return f'{prefix}"{inner}"{suffix}'
            return m.group(0)

        text = re.sub(r'(^|[\s—\(\[\{])[\'‘]([^\n\r\'’]{2,})[\'’]([\s—,\.!\?;:\)\]\}]|$)', _convert_single_quote_dialogue, text)

        text = text.replace("—", " — ").replace("–", " — ")
        text = text.replace("…", "...")

        # Strip Markdown links [text](url) -> text
        text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
        # Strip Markdown images ![alt](url) -> ""
        text = re.sub(r"!\[[^\]]*\]\([^\)]+\)", "", text)
        # Strip Markdown bold/italic
        text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)
        text = re.sub(r"(\*|_)(.*?)\1", r"\2", text)
        # Strip code fences and inline backticks
        text = re.sub(r"```[\w]*\n(.*?)```", r"\1", text, flags=re.DOTALL)
        text = re.sub(r"`([^`]+)`", r"\1", text)

        # Normalize bullet lists
        text = re.sub(r"^\s*[\*\-\+]\s+", "• ", text, flags=re.MULTILINE)
        
        # Collapse whitespace
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @classmethod
    def _split_markdown_chapters(cls, content: str, default_title: str) -> List[Chapter]:
        """Split Markdown text by H1/H2 headers (# Chapter, ## Section)."""
        lines = content.splitlines()
        chapters: List[Chapter] = []
        current_title = default_title
        current_lines: List[str] = []
        chap_num = 1

        header_re = re.compile(r"^(#{1,2})\s+(.+)$")

        for line in lines:
            match = header_re.match(line.strip())
            if match:
                accumulated = "\n".join(current_lines).strip()
                if accumulated:
                    cleaned = cls.clean_prose_text(accumulated)
                    if cleaned:
                        chapters.append(Chapter(
                            chapter_num=chap_num,
                            title=current_title,
                            content=cleaned,
                        ))
                        chap_num += 1
                        current_lines = []
                current_title = match.group(2).strip()
            else:
                current_lines.append(line)

        accumulated = "\n".join(current_lines).strip()
        if accumulated or not chapters:
            cleaned = cls.clean_prose_text(accumulated)
            chapters.append(Chapter(
                chapter_num=chap_num,
                title=current_title,
                content=cleaned,
            ))

        return chapters

    @classmethod
    def _split_into_chapters(cls, text: str, default_title: str) -> List[Chapter]:
        """Split plain text into chapters based on standard Chapter keywords."""
        cleaned = cls.clean_prose_text(text)
        chapter_pattern = re.compile(
            r"^(?:CHAPTER|Chapter|ACT|Act|PART|Part|BOOK|Book)\s+([0-9IVXLCDMivxlcdm]+|[A-Za-z]+)(?::?\s*(.*))?$",
            re.MULTILINE,
        )

        matches = list(chapter_pattern.finditer(cleaned))
        if not matches:
            return [Chapter(chapter_num=1, title=default_title, content=cleaned)]

        chapters: List[Chapter] = []
        if matches[0].start() > 0:
            intro_text = cleaned[:matches[0].start()].strip()
            if len(intro_text) > 30:
                chapters.append(Chapter(
                    chapter_num=1,
                    title="Prologue",
                    content=intro_text,
                ))

        for i, match in enumerate(matches):
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(cleaned)
            heading = match.group(0).strip()
            body = cleaned[start:end].strip()
            
            chap_title = heading
            chap_num = len(chapters) + 1
            if body:
                chapters.append(Chapter(
                    chapter_num=chap_num,
                    title=chap_title,
                    content=body,
                ))

        return chapters if chapters else [Chapter(chapter_num=1, title=default_title, content=cleaned)]
