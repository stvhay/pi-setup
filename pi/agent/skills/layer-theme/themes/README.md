# Named-style catalog

Each `.md` file in this directory is a finalized, named visual style that
can be referenced by name on future projects: "apply the
`<name>` style to `<new-site>`".

A style spec is site-agnostic — palette, weight tiers, slot patterns,
elevation tiers, focus-ring rules, native-widget harmonization. Reusing a
style means copying the `:root` token block and the slot/active patterns,
then doing site-specific Tier 1 + Tier 2 override work for the new target.

## Catalog

| Name | Origin | Aesthetic |
|---|---|---|
| [luci-dark-material](luci-dark-material.md) | OpenWrt LuCI | Material dark, OpenWrt cyan, 5 elevation tiers, slot buttons |

## Adding a new style

1. Finalize a theme on a real site.
2. Copy `../templates/theme-spec.md` to `<style-name>.md`.
3. Fill in palette, tiers, patterns, gotchas surfaced during implementation.
4. Add a row to the catalog table above.
5. Save a `reference` memory pointing at the file so future sessions can
   find it by name.
