# Graphify Pi integration

This directory contains a Pi-native wrapper skill for [safishamsi/graphify](https://github.com/safishamsi/graphify).

- Upstream package: `graphifyy` on PyPI
- CLI command: `graphify`
- Pi helper entrypoint: `agnt graphify [ARGS...]`
- Imported upstream version checked during integration: `0.8.36`

The skill text is a Pi-specific rewrite that uses the local `agnt` helper surface instead of platform-specific hooks or assistant-specific subagent mechanisms.

`LICENSE.upstream` records the upstream MIT license for provenance.
