---
inclusion: auto
---

# Confluence Page Update Safety

When updating an existing Confluence page via the MCP server:

1. ALWAYS read the page first using `get_confluence_page` to see the current content
2. Check the `body_storage` field for any `ac:structured-macro` elements (TOC, children display, page index, etc.)
3. If macros exist, PRESERVE them in the updated body — do not replace the entire page body with plain content
4. When adding content to a page that has macros, insert your content around the existing macros rather than replacing them
5. NEVER blindly overwrite a page body without checking for existing macros first
6. If you're unsure whether a page has macros, ask the user before updating

Confluence macros look like `<ac:structured-macro ac:name="...">` in storage format. Common ones include:
- `toc` — Table of Contents
- `children` — Children Display
- `pagetree` — Page Tree
- `excerpt` — Excerpt
- `info`, `warning`, `note` — Info/Warning/Note panels
