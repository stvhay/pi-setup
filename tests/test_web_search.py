from __future__ import annotations

import json
import runpy
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pytest


SCRIPT = Path("pi/agent/bin/web-search")


@pytest.mark.parametrize(("category_args", "expected"), [([], None), (["--category", "it"], "it")])
def test_web_search_only_forwards_explicit_category(monkeypatch, category_args, expected):
    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"results": []}).encode()

    def urlopen(request, timeout):
        seen["url"] = request.full_url
        assert timeout == 30
        return Response()

    monkeypatch.setenv("SEARXNG_URL", "https://search.example")
    monkeypatch.setattr(sys, "argv", ["web-search", *category_args, "latest", "Python", "news"])
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)

    runpy.run_path(str(SCRIPT), run_name="__main__")

    params = urllib.parse.parse_qs(urllib.parse.urlsplit(seen["url"]).query)
    assert params.get("categories", [None]) == [expected]
