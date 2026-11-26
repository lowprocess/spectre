"""KiCad's s-expressions: read into nested lists, write back out.

An atom is a str; a quoted string is a Q (a str subclass), so that it is
written back with its quotes.  A list is a Python list whose first item is
its token."""


class Q(str):
    """A quoted string."""


def parse(text):
    pos, n = 0, len(text)
    stack, cur = [], None
    while pos < n:
        c = text[pos]
        if c in " \t\r\n":
            pos += 1
        elif c == "(":
            new = []
            if cur is not None:
                cur.append(new)
                stack.append(cur)
            cur = new
            pos += 1
        elif c == ")":
            pos += 1
            if stack:
                cur = stack.pop()
            else:
                return cur
        elif c == '"':
            out, pos = [], pos + 1
            while text[pos] != '"':
                if text[pos] == "\\":
                    pos += 1
                    out.append({"n": "\n", "t": "\t"}.get(text[pos],
                                                          text[pos]))
                else:
                    out.append(text[pos])
                pos += 1
            pos += 1
            cur.append(Q("".join(out)))
        else:
            end = pos
            while end < n and text[end] not in " \t\r\n()":
                end += 1
            cur.append(text[pos:end])
            pos = end
    return cur


def _atom(a):
    if isinstance(a, Q):
        return '"%s"' % (a.replace("\\", "\\\\").replace('"', '\\"')
                         .replace("\n", "\\n"))
    if isinstance(a, float):
        s = ("%.4f" % a).rstrip("0").rstrip(".")
        return "0" if s in ("-0", "") else s
    return str(a)


def dump(node, depth=0):
    """KiCad's own layout, near enough: one list a line, short ones inline."""
    tab = "\t" * depth
    if not isinstance(node, list):
        return tab + _atom(node)
    if all(not isinstance(x, list) for x in node):
        return tab + "(" + " ".join(_atom(x) for x in node) + ")"
    head = [x for x in node if not isinstance(x, list)]
    out = [tab + "(" + " ".join(_atom(x) for x in head)]
    for x in node:
        if isinstance(x, list):
            out.append(dump(x, depth + 1))
    out.append(tab + ")")
    return "\n".join(out)


def find(node, token):
    """The first child list with this token, or None."""
    for x in node:
        if isinstance(x, list) and x and x[0] == token:
            return x
    return None


def find_all(node, token):
    return [x for x in node if isinstance(x, list) and x and x[0] == token]


def top_spans(text):
    """(token, start, end) of each list directly inside the outermost one,
    in the raw text: for changing part of a file while the rest stays
    byte for byte as it was."""
    out, depth, i, n, start = [], 0, 0, len(text), None
    while i < n:
        c = text[i]
        if c == '"':
            i += 1
            while text[i] != '"':
                i += 2 if text[i] == "\\" else 1
        elif c == "(":
            depth += 1
            if depth == 2:
                start = i
        elif c == ")":
            if depth == 2:
                j = start + 1
                while text[j] not in " \t\r\n()":
                    j += 1
                out.append((text[start + 1:j], start, i + 1))
            depth -= 1
        i += 1
    return out


def span_of(text, token, begin=0, end=None):
    """(start, end) of the first list with this token inside text[begin:
    end], wherever it is nested."""
    i = text.index("(" + token, begin, end)
    depth, j = 0, i
    while True:
        c = text[j]
        if c == '"':
            j += 1
            while text[j] != '"':
                j += 2 if text[j] == "\\" else 1
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i, j + 1
        j += 1
