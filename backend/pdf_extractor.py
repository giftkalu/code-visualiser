"""
PDF Extraction Service for Educational Programming Materials
Multi-strategy pipeline:
  Layer 1 - Shaded rectangle detection  (boxed code blocks)
  Layer 2 - Monospace font detection     (font-tagged code)
  Layer 3 - Column gap detection         (slide-style side-by-side layout)
  Layer 4 - Pattern/keyword scoring      (plain text fallback)
"""

import re
from typing import Dict, List, Optional, Tuple
import pdfplumber
from io import BytesIO


# Monospace font names (lowercase matching)
MONOSPACE_FONTS = (
    'courier', 'consolas', 'monaco', 'monospace', 'lucidaconsole',
    'dejavusansmono', 'inconsolata', 'sourcecodepro', 'ubuntumono',
    'notomono', 'droidsansmono', 'anonymouspro', 'liberationmono',
)


class PDFExtractor:
    """Extracts and separates code from prose in PDF documents."""

    CODE_PATTERNS = [
        r'^\s*(def|class|if|elif|else|for|while|return|import|from|try|except|with|pass|break|continue)\b',
        r'^\s*print\s*\(',
        r'^\s*[a-zA-Z_][a-zA-Z0-9_]*\s*=\s*.+',  # assignments
        r'^\s*#',                                   # comments
        r'^\s{4,}',                                 # indented lines
    ]

    def __init__(self):
        self.extracted_data = {'code_blocks': []}
        self.code_counter = 0

    def extract_from_pdf(self, pdf_path: str) -> Dict:
        """Extract from PDF file path."""
        with pdfplumber.open(pdf_path) as pdf:
            return self._extract(pdf)

    def extract_from_bytes(self, pdf_bytes: bytes) -> Dict:
        """Extract from PDF bytes."""
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            return self._extract(pdf)

    def _extract(self, pdf) -> Dict:
        """Run the pipeline over every page."""
        self.extracted_data = {'code_blocks': []}
        self.code_counter = 0

        for page_num, page in enumerate(pdf.pages, start=1):
            self._process_page(page, page_num)

        return self.extracted_data

    # ------------------------------------------------------------------
    # LAYER 1 — Shaded rectangle detection
    # ------------------------------------------------------------------

    def _get_shaded_boxes(self, page) -> List[Tuple]:
        """
        Return bounding boxes of filled/shaded rectangles on the page.
        These are typically the grey boxes that surround code blocks in
        lecture-style PDFs.
        """
        boxes = []
        for rect in page.rects:
            fill = rect.get('non_stroking_color')
            stroke = rect.get('stroking_color')

            # Accept rect if it has any fill OR a visible coloured stroke border
            has_fill = fill is not None and fill not in (1, (1, 1, 1), [1, 1, 1])

            # A coloured stroke (not black, not white) signals a bordered code box
            # e.g. green or blue left-border boxes common in lecture PDFs
            has_coloured_stroke = False
            if stroke is not None and stroke not in (0, (0, 0, 0), [0, 0, 0],
                                                      1, (1, 1, 1), [1, 1, 1]):
                has_coloured_stroke = True

            if not has_fill and not has_coloured_stroke:
                continue

            w = rect['x1'] - rect['x0']
            h = rect['y1'] - rect['y0']
            if w < 20 or h < 10:   # skip tiny decorative lines
                continue
            boxes.append((rect['x0'], rect['y0'], rect['x1'], rect['y1']))
        return boxes

    def _extract_via_rects(self, page, page_num: int) -> bool:
        boxes = self._get_shaded_boxes(page)
        if not boxes:
            return False

        found = False

        for bbox in boxes:
            region = page.within_bbox(bbox)
            text = self._extract_text_preserving_indent(region)

            if not text or not text.strip():
                continue

            lines = text.split('\n')

            if self._is_code_block(lines):
                self._store_code(lines, page_num)
                found = True

        return found

    # ------------------------------------------------------------------
    # LAYER 2 — Monospace font detection
    # ------------------------------------------------------------------

    def _is_monospace(self, font_name: str) -> bool:
        """Check if a font name indicates monospace."""
        if not font_name:
            return False
        fn = font_name.lower().replace(' ', '').replace('-', '').replace('_', '')
        return any(mono in fn for mono in MONOSPACE_FONTS)

    def _extract_via_fonts(self, page, page_num: int) -> bool:
        chars = page.chars
        if not chars:
            return False

        if not any(self._is_monospace(c.get('fontname', '')) for c in chars):
            return False

        lines_map = {}
        for ch in chars:
            line_y = round(ch['top'])
            lines_map.setdefault(line_y, []).append(ch)

        found = False
        mono_block = []

        def flush():
            nonlocal found
            if mono_block:
                if self._is_code_block(mono_block):
                    self._store_code(mono_block, page_num)
                    found = True
                mono_block.clear()

        for y in sorted(lines_map.keys()):
            line_chars = sorted(lines_map[y], key=lambda c: c['x0'])
            min_x = min(c['x0'] for c in chars)
            line_text = self._reconstruct_line_with_indent(line_chars, min_x)

            mono_count = sum(1 for c in line_chars if self._is_monospace(c.get('fontname', '')))
            is_mono_line = mono_count / max(len(line_chars), 1) > 0.5

            if is_mono_line:
                mono_block.append(line_text)
            else:
                flush()

        flush()
        return found

    # ------------------------------------------------------------------
    # LAYER 3 — Column gap detection
    # ------------------------------------------------------------------

    def _find_code_column_start(self, page) -> Optional[float]:
        """
        Detect where a right-side code column starts by finding the largest
        horizontal gap between word x0 positions.
        """
        words = page.extract_words()
        if not words:
            return None

        x0_positions = sorted(set(round(w['x0']) for w in words))
        if len(x0_positions) < 2:
            return None

        largest_gap = 0
        gap_end = None
        for i in range(1, len(x0_positions)):
            gap = x0_positions[i] - x0_positions[i - 1]
            if gap > largest_gap:
                largest_gap = gap
                gap_end = x0_positions[i]

        if largest_gap < page.width * 0.15:
            return None

        return gap_end

    def _extract_via_columns(self, page, page_num: int) -> bool:
        code_col_start = self._find_code_column_start(page)
        if code_col_start is None:
            return False

        right_region = page.within_bbox((code_col_start, 0, page.width, page.height))
        right_text = right_region.extract_text()

        if right_text and right_text.strip():
            lines = right_text.split('\n')
            if self._is_code_block(lines):
                self._store_code(lines, page_num)
                return True

        return False

    # ------------------------------------------------------------------
    # LAYER 4 — Pattern/keyword scoring fallback
    # ------------------------------------------------------------------

    def _extract_via_patterns(self, page, page_num: int):
        text = page.extract_text(x_tolerance=1, y_tolerance=3)
        if not text or not text.strip():
            return

        lines = text.split('\n')
        blocks = self._group_into_blocks(lines)

        for block_lines, _ in blocks:
            if self._is_code_block(block_lines):
                self._store_code(block_lines, page_num)

    # ------------------------------------------------------------------
    # Main page processor — tries each layer in order
    # ------------------------------------------------------------------

    def _process_page(self, page, page_num: int):
        """Try each layer in order, stop as soon as one succeeds."""

        # Layer 1: shaded box detection
        if self._extract_via_rects(page, page_num):
            return

        # Layer 2: monospace font detection
        if self._extract_via_fonts(page, page_num):
            return

        # Layer 3: column gap detection
        if self._extract_via_columns(page, page_num):
            return

        # Layer 4: pattern-based fallback
        self._extract_via_patterns(page, page_num)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _store_code(self, lines: List[str], page_num: int):
        content = '\n'.join(lines).strip()

        # 🚫 Skip tiny/noisy blocks
        if len(content) < 20:
            return

        normalized = self._normalize_indentation(content)

        self.code_counter += 1
        self.extracted_data['code_blocks'].append({
            'id': self.code_counter,
            'code': normalized,
            'page': page_num,
        })

    def _group_into_blocks(self, lines: List[str]) -> List[tuple]:
        """Group consecutive non-empty lines into blocks."""
        blocks = []
        current_block = []
        line_start = 0

        for i, line in enumerate(lines):
            if line.strip():
                if not current_block:
                    line_start = i
                current_block.append(line)
            elif current_block:
                blocks.append((current_block, line_start))
                current_block = []

        if current_block:
            blocks.append((current_block, line_start))

        return blocks

    def _is_code_block(self, lines: List[str]) -> bool:
        non_empty = [l for l in lines if l.strip()]
        if not non_empty or len(non_empty) < 2:
            return False

        code_line_count = sum(1 for line in non_empty if self._is_code_line(line))
        return code_line_count / len(non_empty) > 0.5

    def _is_code_line(self, line: str) -> bool:
        """Check if a single line looks like code."""
        if any(re.search(pattern, line) for pattern in self.CODE_PATTERNS):
            return True

        score = 0
        score += 2 if re.search(r'\b(def|class|if|while|for|return|import)\b', line) else 0
        score += 1 if re.search(r'[a-zA-Z_]\w*\s*\(', line) else 0
        score += 1 if any(op in line for op in ['==', '!=', '+=', '-=', '**', '//']) else 0
        score += 1 if line.count('(') + line.count('[') >= 2 else 0
        score -= 2 if re.search(r'\.\s*$', line) and '"' not in line else 0
        score -= 1 if sum(1 for w in ['the', 'is', 'are', 'was', 'will']
                          if re.search(rf'\b{w}\b', line.lower())) >= 2 else 0

        return score >= 1

    def _normalize_indentation(self, code: str) -> str:
        """Normalize indentation relative to minimum indent (preserves structure)."""
        lines = code.split('\n')
        indents = [
            len(line) - len(line.lstrip())
            for line in lines if line.strip()
        ]

        if not indents:
            return code

        base_indent = min(indents)

        normalized = []
        for line in lines:
            if not line.strip():
                normalized.append('')
            else:
                indent = len(line) - len(line.lstrip())
                relative = max(indent - base_indent, 0)
                normalized.append(' ' * relative + line.lstrip())

        return '\n'.join(normalized)
    def _reconstruct_line_with_indent(self, line_chars, min_x):
        """Rebuild a line using x-coordinates to preserve indentation + spacing."""
        if not line_chars:
            return ""

        line = ""

    # --- Compute average character width (dynamic, not hardcoded) ---
        widths = [(c['x1'] - c['x0']) for c in line_chars if (c['x1'] - c['x0']) > 0]
        avg_char_width = sum(widths) / len(widths) if widths else 5

    # --- INDENTATION (leading spaces) ---
        first_char_x = line_chars[0]['x0']
        indent_spaces = int((first_char_x - min_x) / max(avg_char_width, 1))
        line += ' ' * max(indent_spaces, 0)

        # --- INLINE SPACING (between characters) ---
        prev_x1 = None
        for ch in line_chars:
            if prev_x1 is not None:
                gap = ch['x0'] - prev_x1
                if gap > avg_char_width * 0.5:
                    spaces = int(gap / avg_char_width)
                    line += ' ' * max(spaces, 1)

            line += ch['text']
            prev_x1 = ch['x1']

        return line
    def _extract_text_preserving_indent(self, region) -> str:
        """Reconstruct text from chars using layout (fixes run-on + indentation)."""
        chars = region.chars
        if not chars:
            return ""

        # Group by line (y-position)
        lines = {}
        for ch in chars:
            line_y = round(ch['top'])
            lines.setdefault(line_y, []).append(ch)

        min_x = min(ch['x0'] for ch in chars)

        reconstructed_lines = []
        for y in sorted(lines.keys()):
            line_chars = sorted(lines[y], key=lambda c: c['x0'])
            line_text = self._reconstruct_line_with_indent(line_chars, min_x)
            reconstructed_lines.append(line_text)

        return "\n".join(reconstructed_lines)

# ------------------------------------------------------------------
# Convenience functions
# ------------------------------------------------------------------

def extract_pdf(pdf_path: str) -> Dict:
    """Extract from PDF file."""
    return PDFExtractor().extract_from_pdf(pdf_path)


def extract_pdf_bytes(pdf_bytes: bytes) -> Dict:
    """Extract from PDF bytes."""
    return PDFExtractor().extract_from_bytes(pdf_bytes)


# if __name__ == "__main__":
#     import sys

#     pdf_path = sys.argv[1] if len(sys.argv) > 1 else "codepdf2.pdf"
#     result = extract_pdf(pdf_path)

#     print(f"Found {len(result['code_blocks'])} code blocks")
#     print(f"Found {len(result['text_sections'])} text sections")

#     for i, block in enumerate(result['code_blocks'], 1):
#         print(f"\n--- Code Block {i} (Page {block['page']}) ---")
#         print(block['code'])
