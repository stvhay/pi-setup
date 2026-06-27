# Prefer Parsers for Formats with Formal Grammars

## Rule

When reading, writing, or modifying any format that has a formal grammar, use
a parser — not regex, sed, grep, or string manipulation.

**Preference hierarchy:**

1. **Stdlib parser** — use first if available
2. **Well-known third-party parser** — when stdlib is insufficient
3. **Regex as last resort** — only when no formal grammar exists or no parser
   is available. If chosen, explain why in a code comment

## Common Examples

This table is non-exhaustive. The rule applies to any format with a formal
grammar, not just these. Examples are Python/Shell-centric; equivalent parsers
exist in all major languages.

| Format | Stdlib Parser | Third-Party |
|--------|--------------|-------------|
| JSON | Python: `json`; Shell: `jq` | — |
| TOML (read) | Python 3.11+: `tomllib` | `tomli` (older Python) |
| TOML (write) | — | `tomlkit` (preserves comments/formatting), `tomli_w` (lossy) |
| YAML | — | `pyyaml`, `ruamel.yaml` |
| XML | Python: `xml.etree.ElementTree` | `lxml` |
| CSV | Python: `csv` | `pandas` (for analysis) |
| INI | Python: `configparser` | — |
| HTML | Python: `html.parser` | `beautifulsoup4`, `lxml` |
| SQL | — | `sqlparse`, ORM query builders |

## Anti-Patterns

**Bad:** `re.sub(r'version = ".*"', f'version = "{new}"', toml_content)`
— Breaks on multiline strings, inline tables, comments after the value.

**Good:** Parse with `tomlkit` (preserves comments/formatting), modify, write back. Use `tomli_w` only when comment preservation isn't needed.

**Bad:** `grep -oP '"version":\s*"\K[^"]+' package.json`
— Breaks on nested objects, escaped quotes, different formatting.

**Good:** `jq -r '.version' package.json`

**Bad:** `sed -i 's/<tag>old<\/tag>/<tag>new<\/tag>/' file.xml`
— Breaks on namespaces, CDATA, attributes, multiline elements.

**Good:** Parse with `xml.etree`, modify the element, write back.

## When Regex Is Acceptable

- The format has no formal grammar (log files, free-form text)
- No parser exists for the specific format variant
- Extracting a pattern from within a value that was already parsed
  (e.g., regex on a string field after JSON parsing)

In these cases, add a comment explaining why a parser isn't used.

## Flag the Choice

If you choose regex over a parser for a format with a formal grammar, you must
add a code comment explaining the reason. The code reviewer will check for this.
