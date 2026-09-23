#!/usr/bin/env python
"""Stack-based balance check that understands JS strings, template literals with
nested ${}, comments and regex literals. Regex stripping gets this wrong."""
import re, sys

def check(js):
    i, n = 0, len(js)
    stack, errs = [], []
    line = 1
    # tstack tracks template-literal nesting: each entry is the brace depth at
    # which the enclosing `...` resumes
    prev_significant = ""
    while i < n:
        c = js[i]
        if c == "\n":
            line += 1; i += 1; continue
        two = js[i:i+2]
        if two == "//":
            j = js.find("\n", i); i = n if j < 0 else j; continue
        if two == "/*":
            j = js.find("*/", i+2)
            if j < 0: errs.append((line, "unterminated /* comment")); break
            line += js.count("\n", i, j); i = j+2; continue
        if c in "\"'":
            q = c; j = i+1
            while j < n:
                if js[j] == "\\": j += 2; continue
                if js[j] == q: break
                if js[j] == "\n": errs.append((line, "newline in %s string" % q)); break
                j += 1
            if j >= n: errs.append((line, "unterminated string")); break
            i = j+1; prev_significant = "str"; continue
        if c == "`":
            # walk the template literal, recursing through ${ }
            j = i+1; depth = 0
            while j < n:
                if js[j] == "\\": j += 2; continue
                if js[j] == "\n": line += 1; j += 1; continue
                if depth == 0 and js[j] == "`": break
                if depth == 0 and js[j:j+2] == "${": depth += 1; j += 2; continue
                if depth > 0:
                    if js[j] == "{": depth += 1
                    elif js[j] == "}": depth -= 1
                j += 1
            if j >= n: errs.append((line, "unterminated template literal")); break
            i = j+1; prev_significant = "str"; continue
        if c == "/" and prev_significant in ("", "op"):
            # regex literal
            j = i+1; inclass = False
            while j < n:
                if js[j] == "\\": j += 2; continue
                if js[j] == "[": inclass = True
                elif js[j] == "]": inclass = False
                elif js[j] == "/" and not inclass: break
                elif js[j] == "\n": break
                j += 1
            if j < n and js[j] == "/":
                i = j+1
                while i < n and js[i].isalpha(): i += 1
                prev_significant = "str"; continue
        if c in "([{":
            stack.append((c, line)); prev_significant = "op"; i += 1; continue
        if c in ")]}":
            want = {")":"(", "]":"[", "}":"{"}[c]
            if not stack:
                errs.append((line, "unmatched closing %s" % c))
            elif stack[-1][0] != want:
                errs.append((line, "closing %s but %s opened at line %d"
                             % (c, stack[-1][0], stack[-1][1])))
                stack.pop()
            else:
                stack.pop()
            prev_significant = "str"; i += 1; continue
        if c.isalnum() or c in "_$":
            prev_significant = "str"
        elif not c.isspace():
            prev_significant = "op"
        i += 1
    for ch, ln in stack:
        errs.append((ln, "never closed: %s" % ch))
    return errs

s = open(sys.argv[1]).read()
m = re.search(r'<script>\n"use strict";(.*?)</script>', s, re.S)
js = m.group(1)
errs = check(js)
if errs:
    print("PROBLEMS (%d):" % len(errs))
    for ln, e in errs[:25]: print("   line %d: %s" % (ln, e))
else:
    print("balanced: no unclosed brackets, strings, template literals or comments")
print("js: %d chars, %d lines" % (len(js), js.count("\n")))
