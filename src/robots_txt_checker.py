#!/usr/bin/env python3
"""Check a robots.txt file is well formed.

Reads a local robots.txt file, checks its shape — User-agent groups,
Allow and Disallow rules, Sitemap lines, and line formats — and
reports every problem with its line number. Report-only: it never
rewrites a file, never fetches a URL, and needs no network.

Exit codes: 0 when every file is well formed, 1 when any file has a
problem, 2 on a usage error (missing file, bad flag, unreadable
input).
"""

import argparse
import json
import sys
from pathlib import Path

VERSION = "robots-txt-checker-cli 1.0.0"

# Directives this checker knows. Anything else is reported as
# unknown — a typo in a directive name is the most common robots.txt
# mistake, and a crawler quietly ignores a directive it does not know.
KNOWN_DIRECTIVES = {
    "user-agent",
    "allow",
    "disallow",
    "sitemap",
    "crawl-delay",
    "host",
    "clean-param",
    "request-rate",
    "visit-time",
    "noindex",
}

RULE_DIRECTIVES = {"allow", "disallow"}


class Problem:
    """One problem in a robots.txt file, with its line number."""

    def __init__(self, line, message):
        self.line = line
        self.message = message

    def __eq__(self, other):
        return (
            isinstance(other, Problem)
            and self.line == other.line
            and self.message == other.message
        )

    def __repr__(self):
        return "Problem(%r, %r)" % (self.line, self.message)


def _strip_comment(value):
    """Cut a trailing ' # comment' off a directive value."""
    marker = " #"
    cut = value.find(marker)
    if cut != -1:
        return value[:cut].rstrip()
    return value


def check_text(text, allow_block_all=False):
    """Check robots.txt text.

    Returns (problems, stats). problems is a list of Problem, in
    line order. stats is a dict with counts of groups, rules, and
    sitemaps found.
    """
    problems = []
    stats = {"groups": 0, "rules": 0, "sitemaps": 0}

    if not text.strip():
        return [Problem(1, "file is empty")], stats

    lines = text.splitlines()
    seen_agents = set()
    current_agents = None  # agents of the group rules belong to
    group_started = False  # a User-agent line has been seen at all
    group_has_rules = False  # the current group already has rules

    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            problems.append(
                Problem(
                    number,
                    "not a field: value line — expected 'Directive: value'",
                )
            )
            continue
        field, _, value = line.partition(":")
        field = field.strip()
        value = _strip_comment(value.strip())
        name = field.lower()

        if name not in KNOWN_DIRECTIVES:
            problems.append(
                Problem(number, "unknown directive '%s'" % field)
            )
            continue

        if name == "user-agent":
            if not value:
                problems.append(
                    Problem(number, "User-agent has no value")
                )
                # The line still counts as a group start, so the
                # rules after it do not collect extra "no group"
                # problems for the same one broken line.
                group_started = True
                continue
            if current_agents is None or group_has_rules:
                # A new group starts: the first User-agent line, or
                # a User-agent line after the previous group's rules.
                stats["groups"] += 1
                current_agents = [value]
                group_has_rules = False
                agent_key = value.lower()
                if agent_key in seen_agents:
                    problems.append(
                        Problem(
                            number,
                            "User-agent '%s' already has a group"
                            % value,
                        )
                    )
                else:
                    seen_agents.add(agent_key)
            else:
                # User-agent lines in a row belong to the same group.
                current_agents.append(value)
            group_started = True
            continue

        if name in RULE_DIRECTIVES:
            stats["rules"] += 1
            group_has_rules = True
            if not group_started:
                problems.append(
                    Problem(
                        number,
                        "rule '%s' appears before any User-agent group"
                        % field,
                    )
                )
            elif (
                not allow_block_all
                and name == "disallow"
                and value == "/"
                and current_agents is not None
                and any(a == "*" for a in current_agents)
            ):
                problems.append(
                    Problem(
                        number,
                        "Disallow: / blocks the whole site for every crawler",
                    )
                )
            continue

        if name == "sitemap":
            stats["sitemaps"] += 1
            if not (
                value.startswith("http://")
                or value.startswith("https://")
            ):
                problems.append(
                    Problem(number, "Sitemap is not a URL")
                )
            continue

        if name == "crawl-delay":
            try:
                float(value)
            except ValueError:
                problems.append(
                    Problem(number, "Crawl-delay is not a number")
                )
            continue

        # host, clean-param, request-rate, visit-time, noindex:
        # known directives with no shape this checker judges.
        # A rule line after a Sitemap or a global directive still
        # belongs to the current group, so current_agents is left
        # alone here.
        continue

    if not group_started:
        problems.append(
            Problem(len(lines), "no User-agent group found")
        )

    return problems, stats


def read_robots_file(path):
    """Read a robots.txt file. Returns (text, error)."""
    try:
        return Path(path).read_text(encoding="utf-8"), None
    except FileNotFoundError:
        return None, "file not found: %s" % path
    except IsADirectoryError:
        return None, "not a file: %s" % path
    except UnicodeDecodeError:
        return None, "file is not UTF-8 text: %s" % path
    except OSError as exc:
        return None, "cannot read %s: %s" % (path, exc)


def check_file(path, allow_block_all=False):
    """Check one file. Returns (problems, stats, error)."""
    text, error = read_robots_file(path)
    if error is not None:
        return None, None, error
    problems, stats = check_text(text, allow_block_all=allow_block_all)
    return problems, stats, None


def _result_dict(name, problems, stats):
    return {
        "file": name,
        "ok": not problems,
        "problems": [
            {"line": p.line, "message": p.message} for p in problems
        ],
        "groups": stats["groups"],
        "rules": stats["rules"],
        "sitemaps": stats["sitemaps"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="robots_txt_checker",
        description="Check a robots.txt file is well formed.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="robots.txt files to check (default: robots.txt)",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="read robots.txt text from standard input",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print results as JSON instead of text",
    )
    parser.add_argument(
        "--allow-block-all",
        action="store_true",
        help="allow Disallow: / for User-agent: *",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=VERSION,
    )
    args = parser.parse_args(argv)

    if args.files and args.stdin:
        print(
            "error: give files or --stdin, not both",
            file=sys.stderr,
        )
        return 2

    inputs = []  # list of (display name, text or None, error or None)
    if args.stdin:
        inputs.append(("<stdin>", sys.stdin.read(), None))
    else:
        names = args.files or ["robots.txt"]
        for name in names:
            text, error = read_robots_file(name)
            inputs.append((name, text, error))

    for name, _text, error in inputs:
        if error is not None:
            print("error: %s" % error, file=sys.stderr)
            return 2

    if args.stdin and not inputs[0][1].strip():
        print("error: no robots.txt text on stdin", file=sys.stderr)
        return 2

    results = []
    checked = 0
    ok_count = 0
    problem_count = 0
    for name, text, _error in inputs:
        problems, stats = check_text(
            text, allow_block_all=args.allow_block_all
        )
        checked += 1
        problem_count += len(problems)
        if not problems:
            ok_count += 1
        results.append(_result_dict(name, problems, stats))

    if args.json:
        summary = "%d checked, %d ok, %d problem(s)" % (
            checked,
            ok_count,
            problem_count,
        )
        print(
            json.dumps(
                {
                    "checked": checked,
                    "ok": ok_count,
                    "problems": problem_count,
                    "results": results,
                },
                indent=2,
            )
        )
        print(summary, file=sys.stderr)
    else:
        for result in results:
            if result["ok"]:
                print(
                    "OK    %s — %d group(s), %d rule(s), %d sitemap(s)"
                    % (
                        result["file"],
                        result["groups"],
                        result["rules"],
                        result["sitemaps"],
                    )
                )
            else:
                for problem in result["problems"]:
                    print(
                        "FAIL  %s:%d: %s"
                        % (
                            result["file"],
                            problem["line"],
                            problem["message"],
                        )
                    )
        print(
            "%d checked, %d ok, %d problem(s)"
            % (checked, ok_count, problem_count)
        )

    return 0 if problem_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
