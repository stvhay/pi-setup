# Prompt Pattern Notes

Use this directory for rewritten prompt-pattern notes from external projects.
Executable Pi action templates live in `../actions/`; this directory is for provenance-safe design notes and pattern candidates, not active invocation specs.

Rules:

- Do not copy external system-prompt text into this repository.
- Record source URL and license.
- Describe the pattern in your own words.
- Store an original Pi-specific rewrite that can be evaluated before adoption.

Create notes with:

```bash
agnt prompt import-pattern-note \
  --name "example" \
  --source-url "https://example.invalid" \
  --source-license "unknown" \
  --pattern "Short description of the observed pattern." \
  --rewrite "Original Pi-specific rewrite."
```
