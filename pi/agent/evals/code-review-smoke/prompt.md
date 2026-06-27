You are reviewing a tiny patch. Return PASS if the patch is safe; otherwise list concrete findings.

Patch:
```diff
--- a/example.py
+++ b/example.py
@@
-def add(a, b):
-    return a + b
+def add(a, b):
+    return a + b
```

Focus on correctness and avoid speculative issues.
