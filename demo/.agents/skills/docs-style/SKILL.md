---
name: docs-style
description: Style guide for pages on the team docs wiki. Use when creating or editing wiki pages.
---
# Docs style

- One `#` title per page, matching the slug in words: slug `release-process` -> `# Release process`.
- Sentence-case headings.
- Start with one paragraph that says who the page is for and when to read it.
- Prefer numbered steps for procedures and tables for reference data.
- Use code formatting for commands, file paths, tool names, and identifiers.
- Link to other pages by slug instead of copying their content.
- Keep pages under about 150 lines; split longer ones.
- Put the date of the last substantive change at the bottom: `Last updated: YYYY-MM-DD`.
- Read the current page with `docs_get_page` before overwriting it with `docs_update_page`, since an update replaces the whole page.
