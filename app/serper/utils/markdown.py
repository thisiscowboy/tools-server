import logging
import re
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class HtmlToMarkdown:
    def __init__(self):
        # Common replacements for markdown conversion
        self.replacements = [
            # Headers
            (re.compile(r'<h1[^>]*>(.*?)</h1>', re.DOTALL), r'# \1\n'),
            (re.compile(r'<h2[^>]*>(.*?)</h2>', re.DOTALL), r'## \1\n'),
            (re.compile(r'<h3[^>]*>(.*?)</h3>', re.DOTALL), r'### \1\n'),
            (re.compile(r'<h4[^>]*>(.*?)</h4>', re.DOTALL), r'#### \1\n'),
            (re.compile(r'<h5[^>]*>(.*?)</h5>', re.DOTALL), r'##### \1\n'),
            (re.compile(r'<h6[^>]*>(.*?)</h6>', re.DOTALL), r'###### \1\n'),

            # Bold and italic
            (re.compile(r'<strong[^>]*>(.*?)</strong>', re.DOTALL), r'**\1**'),
            (re.compile(r'<b[^>]*>(.*?)</b>', re.DOTALL), r'**\1**'),
            (re.compile(r'<em[^>]*>(.*?)</em>', re.DOTALL), r'*\1*'),
            (re.compile(r'<i[^>]*>(.*?)</i>', re.DOTALL), r'*\1*'),

            # Lists
            (re.compile(r'<ul[^>]*>(.*?)</ul>', re.DOTALL), self._process_ul),
            (re.compile(r'<ol[^>]*>(.*?)</ol>', re.DOTALL), self._process_ol),

            # Links
            (re.compile(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.DOTALL), r'[\2](\1)'),

            # Images
            (re.compile(r'<img[^>]*src="([^"]*)"[^>]*alt="([^"]*)"[^>]*>', re.DOTALL), r'![\2](\1)'),
            (re.compile(r'<img[^>]*src="([^"]*)"[^>]*>', re.DOTALL), r'![](\1)'),

            # Code
            (re.compile(r'<pre[^>]*><code[^>]*>(.*?)</code></pre>', re.DOTALL), r'```\n\1\n```'),
            (re.compile(r'<code[^>]*>(.*?)</code>', re.DOTALL), r'`\1`'),

            # Blockquotes
            (re.compile(r'<blockquote[^>]*>(.*?)</blockquote>', re.DOTALL), self._process_blockquote),

            # Paragraphs and breaks
            (re.compile(r'<p[^>]*>(.*?)</p>', re.DOTALL), r'\1\n\n'),
            (re.compile(r'<br[^>]*>', re.DOTALL), r'\n'),

            # Tables - more complex, handled separately
        ]

    def _process_ul(self, match):
        content = match.group(1)
        soup = BeautifulSoup(content, 'html.parser')
        result = "\n"
        for li in soup.find_all('li'):
            result += f"- {li.get_text().strip()}\n"
        return result + "\n"

    def _process_ol(self, match):
        content = match.group(1)
        soup = BeautifulSoup(content, 'html.parser')
        result = "\n"
        for i, li in enumerate(soup.find_all('li')):
            result += f"{i+1}. {li.get_text().strip()}\n"
        return result + "\n"

    def _process_blockquote(self, match):
        content = match.group(1)
        lines = content.split('\n')
        result = "\n"
        for line in lines:
            stripped = line.strip()
            if stripped:
                result += f"> {stripped}\n"
        return result + "\n"

    def _process_table(self, soup):
        tables = soup.find_all('table')
        if not tables:
            return soup

        for table in tables:
            rows = table.find_all('tr')
            if not rows:
                continue

            markdown_table = []

            # Process header row
            header_cells = rows[0].find_all(['th', 'td'])
            if header_cells:
                header_row = "| " + " | ".join([cell.get_text().strip() for cell in header_cells]) + " |"
                markdown_table.append(header_row)

                # Add separator row
                separator_row = "| " + " | ".join(["---" for _ in header_cells]) + " |"
                markdown_table.append(separator_row)

            # Process data rows
            for row in rows[1:]:
                cells = row.find_all('td')
                if cells:
                    data_row = "| " + " | ".join([cell.get_text().strip() for cell in cells]) + " |"
                    markdown_table.append(data_row)

            # Replace table with markdown
            table_markdown = "\n" + "\n".join(markdown_table) + "\n\n"
            new_tag = soup.new_tag('div', attrs={'class': 'markdown-table'})
            new_tag.string = table_markdown
            table.replace_with(new_tag)

        return soup

    def convert(self, html: str) -> str:
        """
        Convert HTML to Markdown
        """
        # First pass - clean up HTML with BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        # Remove script and style elements
        for element in soup(['script', 'style', 'iframe', 'noscript']):
            element.decompose()

        # Process tables
        soup = self._process_table(soup)

        cleaned_html = str(soup)

        # Apply regular expressions
        markdown = cleaned_html
        for pattern, replacement in self.replacements:
            if callable(replacement):
                markdown = pattern.sub(replacement, markdown)
            else:
                markdown = pattern.sub(replacement, markdown)

        # Post-processing cleanup
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)  # Remove extra newlines
        markdown = re.sub(r'<.*?>', '', markdown)  # Remove any remaining HTML tags

        return markdown.strip()
