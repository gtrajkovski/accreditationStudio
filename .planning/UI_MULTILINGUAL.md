# UI Multilingual + Theme + Bilingual Documents

## Overview

This plan implements:
- Language selector (en-US, es-PR, etc.)
- Theme toggle (Light / Dark / System)
- Bilingual Document Workbench with evidence grounding
- Evidence Explorer with multilingual search

All aligned to existing Jinja + vanilla JS frontend and CSS tokens.

---

## Screen Map

### Global Top Bar Controls

```
┌────────────────────────────────────────────────────────────────────────┐
│  [Institution ▼]   [Language ▼]   [🌙/☀️ Theme]   [Plan Studio]   [?]  │
└────────────────────────────────────────────────────────────────────────┘
```

| Control | Behavior |
|---------|----------|
| Institution Switcher | Dropdown of user's institutions |
| Language Selector | `English (US)`, `Español (Puerto Rico)`, etc. |
| Theme Toggle | Light / Dark / System |
| Plan Studio | Opens agentic planning mode |

**Persistence**: User preference first, institution default fallback

---

## First-Run Setup Flow

1. **Create Institution**
   - Name, legal name
   - Choose primary accreditor

2. **Configure Localization**
   - Default locale: `en-US`
   - Additional locales: `es-PR`, etc.
   - Theme default: System (recommended)

3. **Upload First Document**
   - Auto-detect language
   - Offer translation if locale differs

---

## Bilingual Document Workbench

### Layout

```
┌──────────────────┬─────────────────────────────┬────────────────────┐
│                  │                             │                    │
│  Document List   │     Document Viewer         │   Findings Panel   │
│                  │                             │                    │
│  [Search...]     │  ┌─────────────────────┐   │   [Findings]       │
│                  │  │ Language: [▼ en-US] │   │   [Evidence]       │
│  📄 Catalog      │  └─────────────────────┘   │   [Fixes]          │
│     ✓ Indexed    │                             │                    │
│     🌐 Translated │  Page content here...      │   Finding 1        │
│                  │                             │   ├─ Standard: VII.A│
│  📄 Enrollment   │                             │   ├─ Status: ⚠️     │
│     ✓ Indexed    │                             │   └─ Evidence [3]  │
│                  │                             │                    │
└──────────────────┴─────────────────────────────┴────────────────────┘
```

### Document List Badges

| Badge | Meaning |
|-------|---------|
| `✓ Indexed` | Chunks created and embedded |
| `🌐 Translated` | Translation complete for target locale |
| `⏳ Translating` | Translation in progress |
| `⚠️ Issues` | Parse or translation quality issues |

### Language Dropdown in Viewer

Options:
- `Source (English)` — always available
- `Español (Puerto Rico)` — if translation exists

If translation not ready:
- Show "Translate this document" button
- Progress indicator via task queue SSE

---

## Evidence Grounding (Non-Negotiable)

### Rule: Evidence Always Anchors to Source

- `evidence_refs` stores `page`, `locator` in **source document**
- UI shows **translated excerpt by default** (if viewing translation)
- "Show source excerpt" toggle on every evidence card

### Evidence Card Component

```
┌────────────────────────────────────────────────────────────────┐
│ 📍 Evidence for Finding: Tuition total mismatch               │
├────────────────────────────────────────────────────────────────┤
│ Document: Enrollment Agreement (p. 3)                          │
│ Standard: VII.A.4 — Financial Disclosures                      │
├────────────────────────────────────────────────────────────────┤
│ "El costo total del programa es $12,500..."                    │
│                                                                │
│ [Show source excerpt] [View in context]                        │
└────────────────────────────────────────────────────────────────┘
```

Clicking "Show source excerpt" expands:
```
│ 🇺🇸 Source (English):                                          │
│ "The total program cost is $12,500..."                         │
```

---

## Evidence Explorer (Multilingual Search)

### Search Box Behavior

1. User types query in chosen language
2. Backend retrieval:
   - If target language chunks exist → search translated chunks
   - Otherwise → search source chunks
3. Results show excerpt in user's language with source toggle

### Search Results Card

```
┌────────────────────────────────────────────────────────────────┐
│ 🔍 "política de reembolso"                          Score: 0.89│
├────────────────────────────────────────────────────────────────┤
│ 📄 Catalog, p. 12                                              │
│ Standard: VII.B — Refund Policies                              │
├────────────────────────────────────────────────────────────────┤
│ "La política de reembolso del programa establece que..."       │
│                                                                │
│ [Show source] [View document] [Link to finding]                │
└────────────────────────────────────────────────────────────────┘
```

### Filters

| Filter | Options |
|--------|---------|
| Document Type | Catalog, Enrollment Agreement, etc. |
| Program | All programs or specific |
| Language | en-US, es-PR (search chunks in that locale) |
| Source | Accreditor / Federal / State / Professional |

### Source Color Tokens (from SPEC)

```css
--accreditor: #a78bfa;     /* purple */
--federal: #f472b6;        /* pink */
--state: #fb923c;          /* orange */
--professional: #34d399;   /* teal */
```

---

## Document Translation Workflow

### User Flow

1. Open Document Workbench
2. Select document without translation
3. Click "Translate to Español (Puerto Rico)"
4. Optional checkboxes:
   - ☑️ Use institution glossary
   - ☐ Prefer formal tone

### Background Pipeline

```
Document → Split by Chunks → Translate Each Chunk → Store Translations
                ↓                    ↓                     ↓
         document_chunks → document_chunk_translations → Assemble View
```

1. Chunk-by-chunk translation (batch for efficiency)
2. Apply glossary substitutions
3. Store in `document_chunk_translations`
4. Mark `document_translations.status = 'complete'`

### Quality Flags

If issues detected (e.g., untranslatable terms, formatting loss):
- Banner: "⚠️ Translation may need review"
- User can edit glossary entries
- Re-run translation for affected chunks only

---

## Theme Implementation

### CSS Variables (Dark Theme - Default)

```css
:root {
  --bg-primary: #1a1a2e;
  --bg-secondary: #16213e;
  --bg-card: #0f3460;
  --text-primary: #ffffff;
  --text-secondary: #a0aec0;
  --accent: #e94560;
  --border: #2d3748;
}
```

### Light Theme Override

```css
[data-theme="light"] {
  --bg-primary: #f7fafc;
  --bg-secondary: #edf2f7;
  --bg-card: #ffffff;
  --text-primary: #1a202c;
  --text-secondary: #4a5568;
  --accent: #e94560;
  --border: #e2e8f0;
}
```

### JavaScript Theme Toggle

```javascript
function setTheme(theme) {
  if (theme === 'system') {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
  } else {
    document.documentElement.setAttribute('data-theme', theme);
  }
  localStorage.setItem('theme', theme);
  // Also POST to /api/users/me/preferences if logged in
}

// System preference listener
window.matchMedia('(prefers-color-scheme: dark)')
  .addEventListener('change', e => {
    if (localStorage.getItem('theme') === 'system') {
      setTheme('system');
    }
  });
```

---

## Language Switch Implementation

### Jinja Template Updates

```html
<!-- base.html -->
<html lang="{{ user_locale or 'en-US' }}">
<head>
  <meta name="locale" content="{{ user_locale }}">
</head>
```

### i18n UI Strings

Use a simple JSON-based approach:

```javascript
// static/js/i18n.js
const TRANSLATIONS = {
  'en-US': {
    'search': 'Search',
    'findings': 'Findings',
    'evidence': 'Evidence',
    'translate_document': 'Translate Document',
    'show_source': 'Show source',
  },
  'es-PR': {
    'search': 'Buscar',
    'findings': 'Hallazgos',
    'evidence': 'Evidencia',
    'translate_document': 'Traducir Documento',
    'show_source': 'Mostrar fuente',
  }
};

function t(key) {
  const locale = document.documentElement.lang || 'en-US';
  return TRANSLATIONS[locale]?.[key] || TRANSLATIONS['en-US'][key] || key;
}
```

### API Response Headers

All API responses include user's locale:

```python
@app.after_request
def add_locale_header(response):
    response.headers['X-User-Locale'] = g.get('user_locale', 'en-US')
    return response
```

---

## Claude Code Prompt: UI Implementation

```text
Implement multilingual UI + theme toggle + bilingual Document Workbench for AccreditAI.

Context:
- Frontend: Jinja2 templates + vanilla JS
- Dark theme (#1a1a2e) is default, light theme optional
- Locales: en-US (default), es-PR (Spanish Puerto Rico)
- Evidence must always anchor to source document

Requirements:

1) Add to base.html:
   - Language selector dropdown in navbar
   - Theme toggle (Light / Dark / System)
   - data-theme attribute on html element
   - CSS variables for both themes

2) Create static/js/theme.js:
   - setTheme(theme) function
   - System preference listener
   - Persist to localStorage + optional API sync

3) Create static/js/i18n.js:
   - TRANSLATIONS object for en-US and es-PR
   - t(key) function for UI string lookup
   - Update UI strings on language change

4) Create static/css/themes.css:
   - Dark theme variables (default)
   - Light theme variables ([data-theme="light"])
   - Smooth transitions on theme change

5) Update Document Workbench (templates/documents.html):
   - Language dropdown in document viewer
   - "Translate this document" button
   - Translation progress indicator
   - Evidence cards with "Show source" toggle

6) Create Evidence Explorer component:
   - Search input with language awareness
   - Results cards with translated/source toggle
   - Filter by doc type, program, language, source type
   - Color-coded source badges (accreditor, federal, state, professional)

7) API endpoints (src/api/i18n.py):
   - GET /api/i18n/locales - available locales
   - POST /api/users/me/preferences - save locale/theme
   - POST /api/documents/<id>/translate - queue translation
   - GET /api/documents/<id>/translation-status

8) Tests:
   - Theme toggle persists preference
   - Language change updates UI strings
   - Evidence card shows both translated and source text

Start with themes.css + theme.js, then i18n.js, then Document Workbench updates.
```

---

## API Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/i18n/locales` | GET | List available locales |
| `/api/users/me/preferences` | GET/POST | Get/set user locale + theme |
| `/api/institutions/<id>/settings` | GET/POST | Institution locale defaults |
| `/api/documents/<id>/translate` | POST | Queue document translation |
| `/api/documents/<id>/translation-status` | GET | Translation progress |
| `/api/search` | POST | Semantic search with locale awareness |

---

## File Structure

```
static/
├── css/
│   ├── main.css          # Existing styles
│   └── themes.css        # Dark/light theme variables
├── js/
│   ├── app.js            # Existing app code
│   ├── theme.js          # Theme toggle logic
│   ├── i18n.js           # Translation strings + t() function
│   └── document-workbench.js  # Bilingual viewer logic
└── locales/
    ├── en-US.json        # Full UI strings (optional)
    └── es-PR.json        # Spanish UI strings (optional)

templates/
├── base.html             # Add theme/locale controls
├── documents.html        # Bilingual workbench
└── partials/
    ├── evidence-card.html
    └── search-results.html

src/api/
└── i18n.py               # Locale/translation endpoints
```

---

## Verification

1. **Theme toggle**: Switch themes, refresh, verify persistence
2. **Language switch**: Change locale, verify UI strings update
3. **Document translation**: Upload doc, request translation, verify progress
4. **Evidence grounding**: View finding in Spanish, click "Show source", verify English excerpt
5. **Search in locale**: Search in Spanish, verify results return translated chunks
