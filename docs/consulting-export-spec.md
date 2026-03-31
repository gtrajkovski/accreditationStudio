# Consulting Export Specification

## PDF Export (Readiness Assessment)

### Format
- **Cover Page:** Institution name, accreditor, date, overall rating (color-coded), readiness score
- **Executive Summary:** 1-page overview with key findings
- **Section Analysis:** 1-2 pages per evaluation area with score, findings, critical gaps
- **Critical Gaps Appendix:** Prioritized list of all critical/high-severity issues with recommendations

### Styling
- Clean, professional layout
- Color-coded ratings (Green: Ready, Yellow: Conditional, Red: Not Ready)
- Page breaks between major sections
- Header/footer with institution name and page numbers
- Print-friendly (no dark backgrounds)

### Dependencies
- `weasyprint` for PDF generation
- GTK libraries (on Linux) for font rendering

### Error Handling
- If WeasyPrint not installed: returns informative error message
- Empty sections: shows "No findings" rather than failing
- Missing data: gracefully degrades (uses defaults)

## DOCX Export (Pre-Visit Checklist)

### Format
- **Title Page:** Checklist title, institution, accreditor, generation date
- **Overall Progress:** Summary statistics (complete/partial/not met)
- **Section Tables:** One table per evaluation area with:
  - Requirement column (40% width)
  - Status column (badge-style)
  - Evidence column (page references)
  - Action Needed column

### Styling
- Uses `python-docx` built-in table styles
- Light Grid Accent 1 for professional appearance
- Bold section headings
- Consistent spacing and alignment
- Page breaks between sections

### Dependencies
- `python-docx` for DOCX generation

### Error Handling
- If python-docx not installed: returns informative error message
- Long text truncated to prevent table overflow
- Empty evidence: displays "N/A"
- Missing sections: skips gracefully

## Installation

```bash
pip install weasyprint python-docx
```

### Linux Additional Requirements
```bash
# Ubuntu/Debian
sudo apt-get install libpango-1.0-0 libpangocairo-1.0-0

# Fedora/RHEL
sudo dnf install pango
```

## Testing

See `tests/test_consulting.py` for export validation tests:
- PDF valid (parseable)
- DOCX valid (parseable)
- Handles empty institution
- Handles missing sections
- Character encoding (UTF-8)
