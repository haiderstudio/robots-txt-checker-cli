#!/usr/bin/env python3
"""Tests for robots_txt_checker. Standard library unittest only."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = ROOT / "src" / "robots_txt_checker.py"

sys.path.insert(0, str(ROOT / "src"))

import robots_txt_checker as rtc  # noqa: E402


def run_cli(*args, input_text=None, cwd=None):
    """Run the CLI as a subprocess. Returns (exit code, stdout, stderr)."""
    proc = subprocess.run(
        [sys.executable, str(SRC), *args],
        input=input_text,
        capture_output=True,
        text=True,
        cwd=cwd or str(ROOT),
    )
    return proc.returncode, proc.stdout, proc.stderr


def problems_of(text, **kwargs):
    """Problems of a text sample, as (line, message) pairs."""
    problems, _stats = rtc.check_text(text, **kwargs)
    return [(p.line, p.message) for p in problems]


GOOD = """# robots.txt for example.com
User-agent: *
Allow: /

User-agent: Googlebot
Disallow: /admin/
Disallow: /search
Allow: /search/help

Sitemap: https://example.com/sitemap.xml
"""


class TestCheckText(unittest.TestCase):
    def test_good_file_passes(self):
        problems, stats = rtc.check_text(GOOD)
        self.assertEqual(problems, [])
        self.assertEqual(stats, {"groups": 2, "rules": 4, "sitemaps": 1})

    def test_empty_file(self):
        self.assertEqual(
            problems_of(""), [(1, "file is empty")]
        )
        self.assertEqual(
            problems_of("  \n\n  \n"), [(1, "file is empty")]
        )

    def test_comments_and_blank_lines_are_fine(self):
        problems, stats = rtc.check_text(
            "# just a comment\n\n# another\nUser-agent: *\n"
            "Disallow: /tmp/\n"
        )
        self.assertEqual(problems, [])
        self.assertEqual(stats["groups"], 1)
        self.assertEqual(stats["rules"], 1)

    def test_rule_before_user_agent(self):
        self.assertEqual(
            problems_of("Disallow: /private/\nUser-agent: *\n"),
            [
                (
                    1,
                    "rule 'Disallow' appears before any "
                    "User-agent group",
                )
            ],
        )
        self.assertEqual(
            problems_of("Allow: /x\nUser-agent: *\n"),
            [
                (
                    1,
                    "rule 'Allow' appears before any User-agent group",
                )
            ],
        )

    def test_unknown_directive(self):
        self.assertEqual(
            problems_of("User-agent: *\nBanana: /x\n"),
            [(2, "unknown directive 'Banana'")],
        )

    def test_empty_user_agent_value(self):
        self.assertEqual(
            problems_of("User-agent:\nDisallow: /x\n"),
            [(1, "User-agent has no value")],
        )

    def test_no_user_agent_at_all(self):
        self.assertEqual(
            problems_of("Sitemap: https://example.com/sitemap.xml\n"),
            [(1, "no User-agent group found")],
        )

    def test_duplicate_user_agent_group(self):
        self.assertEqual(
            problems_of(
                "User-agent: *\nDisallow: /a/\n"
                "User-agent: *\nDisallow: /b/\n"
            ),
            [(3, "User-agent '*' already has a group")],
        )

    def test_same_agent_twice_in_one_group_is_fine(self):
        problems, stats = rtc.check_text(
            "User-agent: *\nUser-agent: Googlebot\nDisallow: /x/\n"
        )
        self.assertEqual(problems, [])
        self.assertEqual(stats["groups"], 1)

    def test_sitemap_must_be_a_url(self):
        self.assertEqual(
            problems_of(
                "User-agent: *\nSitemap: sitemap.xml\n"
            ),
            [(2, "Sitemap is not a URL")],
        )
        problems, _stats = rtc.check_text(
            "User-agent: *\nSitemap: http://example.com/s.xml\n"
        )
        self.assertEqual(problems, [])

    def test_crawl_delay_must_be_a_number(self):
        self.assertEqual(
            problems_of("User-agent: *\nCrawl-delay: slow\n"),
            [(2, "Crawl-delay is not a number")],
        )
        problems, _stats = rtc.check_text(
            "User-agent: *\nCrawl-delay: 10\n"
        )
        self.assertEqual(problems, [])
        problems, _stats = rtc.check_text(
            "User-agent: *\nCrawl-delay: 0.5\n"
        )
        self.assertEqual(problems, [])

    def test_line_without_a_colon(self):
        self.assertEqual(
            problems_of("User-agent: *\nGarbage line here\n"),
            [
                (
                    2,
                    "not a field: value line — expected "
                    "'Directive: value'",
                )
            ],
        )

    def test_block_all_for_every_crawler(self):
        self.assertEqual(
            problems_of("User-agent: *\nDisallow: /\n"),
            [
                (
                    2,
                    "Disallow: / blocks the whole site for "
                    "every crawler",
                )
            ],
        )
        self.assertEqual(
            problems_of(
                "User-agent: *\nDisallow: /\n", allow_block_all=True
            ),
            [],
        )

    def test_block_all_for_one_named_bot_is_fine(self):
        problems, _stats = rtc.check_text(
            "User-agent: BadBot\nDisallow: /\n"
        )
        self.assertEqual(problems, [])

    def test_directive_names_are_case_insensitive(self):
        problems, stats = rtc.check_text(
            "USER-AGENT: *\ndIsAlLoW: /tmp/\n"
            "sitemap: https://example.com/sitemap.xml\n"
        )
        self.assertEqual(problems, [])
        self.assertEqual(stats["rules"], 1)
        self.assertEqual(stats["sitemaps"], 1)

    def test_inline_comments_are_stripped(self):
        problems, _stats = rtc.check_text(
            "User-agent: * # every crawler\n"
            "Disallow: /tmp/ # keep out\n"
        )
        self.assertEqual(problems, [])

    def test_empty_disallow_means_allow_all(self):
        problems, _stats = rtc.check_text(
            "User-agent: *\nDisallow:\n"
        )
        self.assertEqual(problems, [])

    def test_sitemap_before_any_group_is_fine(self):
        problems, _stats = rtc.check_text(
            "Sitemap: https://example.com/sitemap.xml\n"
            "User-agent: *\nDisallow: /tmp/\n"
        )
        self.assertEqual(problems, [])

    def test_bad_file_has_seven_problems(self):
        text = (ROOT / "examples" / "bad-robots.txt").read_text(
            encoding="utf-8"
        )
        problems, stats = rtc.check_text(text)
        self.assertEqual(len(problems), 7)
        self.assertEqual(
            [p.line for p in problems], [1, 3, 4, 5, 7, 8, 9]
        )
        self.assertEqual(stats, {"groups": 2, "rules": 3, "sitemaps": 1})


class TestReadFile(unittest.TestCase):
    def test_read_good_file(self):
        problems, stats, error = rtc.check_file(
            str(ROOT / "examples" / "good-robots.txt")
        )
        self.assertIsNone(error)
        self.assertEqual(problems, [])
        self.assertEqual(stats["groups"], 2)

    def test_missing_file(self):
        _problems, _stats, error = rtc.check_file("/no/such/robots.txt")
        self.assertIn("not found", error)

    def test_not_utf8_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "robots.txt"
            path.write_bytes(b"User-agent: *\n\xff\xfe\n")
            _problems, _stats, error = rtc.check_file(str(path))
            self.assertIn("UTF-8", error)

    def test_directory_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            _problems, _stats, error = rtc.check_file(tmp)
            self.assertIsNotNone(error)


class TestCli(unittest.TestCase):
    def test_good_file_exit_zero(self):
        code, out, err = run_cli("examples/good-robots.txt")
        self.assertEqual(code, 0)
        self.assertIn(
            "OK    examples/good-robots.txt — 2 group(s), 4 rule(s), "
            "1 sitemap(s)",
            out,
        )
        self.assertIn("1 checked, 1 ok, 0 problem(s)", out)

    def test_bad_file_exit_one(self):
        code, out, err = run_cli("examples/bad-robots.txt")
        self.assertEqual(code, 1)
        self.assertIn(
            "FAIL  examples/bad-robots.txt:1: rule 'Disallow' "
            "appears before any User-agent group",
            out,
        )
        self.assertIn("1 checked, 0 ok, 7 problem(s)", out)

    def test_multiple_files(self):
        code, out, err = run_cli(
            "examples/good-robots.txt", "examples/bad-robots.txt"
        )
        self.assertEqual(code, 1)
        self.assertIn("2 checked, 1 ok, 7 problem(s)", out)

    def test_default_file_is_robots_txt(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "robots.txt").write_text(GOOD, encoding="utf-8")
            code, out, err = run_cli(cwd=tmp)
            self.assertEqual(code, 0)
            self.assertIn("OK    robots.txt", out)

    def test_default_file_missing_exit_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = run_cli(cwd=tmp)
            self.assertEqual(code, 2)
            self.assertIn("not found", err)

    def test_stdin_input(self):
        code, out, err = run_cli(
            "--stdin", input_text="User-agent: *\nDisallow: /private/\n"
        )
        self.assertEqual(code, 0)
        self.assertIn(
            "OK    <stdin> — 1 group(s), 1 rule(s), 0 sitemap(s)", out
        )

    def test_empty_stdin_exit_two(self):
        code, out, err = run_cli("--stdin", input_text="")
        self.assertEqual(code, 2)
        self.assertIn("no robots.txt text on stdin", err)

    def test_files_and_stdin_exit_two(self):
        code, out, err = run_cli(
            "examples/good-robots.txt", "--stdin", input_text="x"
        )
        self.assertEqual(code, 2)
        self.assertIn("not both", err)

    def test_missing_file_exit_two(self):
        code, out, err = run_cli("no-such-robots.txt")
        self.assertEqual(code, 2)
        self.assertIn("not found", err)

    def test_allow_block_all_flag(self):
        code, out, err = run_cli("examples/block-all-robots.txt")
        self.assertEqual(code, 1)
        self.assertIn("blocks the whole site", out)
        code, out, err = run_cli(
            "--allow-block-all", "examples/block-all-robots.txt"
        )
        self.assertEqual(code, 0)
        self.assertIn(
            "OK    examples/block-all-robots.txt — 1 group(s), "
            "1 rule(s), 0 sitemap(s)",
            out,
        )

    def test_json_output(self):
        code, out, err = run_cli(
            "--json", "examples/bad-robots.txt"
        )
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertEqual(data["checked"], 1)
        self.assertEqual(data["ok"], 0)
        self.assertEqual(data["problems"], 7)
        self.assertEqual(len(data["results"][0]["problems"]), 7)
        self.assertEqual(
            data["results"][0]["problems"][0]["line"], 1
        )
        self.assertIn("1 checked, 0 ok, 7 problem(s)", err)

    def test_version_flag(self):
        code, out, err = run_cli("--version")
        self.assertEqual(code, 0)
        self.assertIn("robots-txt-checker-cli", out)

    def test_bad_flag_exit_two(self):
        code, out, err = run_cli("--nope")
        self.assertEqual(code, 2)

    def test_input_file_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "robots.txt"
            before = "User-agent: *\nDisallow: /tmp/\n"
            path.write_text(before, encoding="utf-8")
            run_cli(str(path))
            self.assertEqual(path.read_text(encoding="utf-8"), before)


class TestExamples(unittest.TestCase):
    def test_sample_output_matches_fresh_run(self):
        code, out, err = run_cli("examples/bad-robots.txt")
        self.assertEqual(code, 1)
        saved = (ROOT / "examples" / "sample-output.txt").read_text(
            encoding="utf-8"
        )
        self.assertEqual(out, saved)

    def test_run_example_script(self):
        proc = subprocess.run(
            ["sh", "examples/run-example.sh"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("1 checked, 0 ok, 7 problem(s)", proc.stdout)
        self.assertIn("1 checked, 1 ok, 0 problem(s)", proc.stdout)
        self.assertIn("1 checked, 0 ok, 1 problem(s)", proc.stdout)

    def test_readme_quoted_outputs(self):
        # Every line the README quotes from a real run must match
        # a fresh run of the same command.
        code, out, err = run_cli("examples/good-robots.txt")
        self.assertEqual(
            out,
            "OK    examples/good-robots.txt — 2 group(s), 4 rule(s), "
            "1 sitemap(s)\n1 checked, 1 ok, 0 problem(s)\n",
        )
        code, out, err = run_cli("examples/bad-robots.txt")
        self.assertEqual(
            out,
            "FAIL  examples/bad-robots.txt:1: rule 'Disallow' "
            "appears before any User-agent group\n"
            "FAIL  examples/bad-robots.txt:3: unknown directive "
            "'Banana'\n"
            "FAIL  examples/bad-robots.txt:4: Disallow: / blocks "
            "the whole site for every crawler\n"
            "FAIL  examples/bad-robots.txt:5: User-agent '*' "
            "already has a group\n"
            "FAIL  examples/bad-robots.txt:7: Sitemap is not a URL\n"
            "FAIL  examples/bad-robots.txt:8: Crawl-delay is not "
            "a number\n"
            "FAIL  examples/bad-robots.txt:9: not a field: value "
            "line — expected 'Directive: value'\n"
            "1 checked, 0 ok, 7 problem(s)\n",
        )
        code, out, err = run_cli("examples/block-all-robots.txt")
        self.assertEqual(
            out,
            "FAIL  examples/block-all-robots.txt:3: Disallow: / "
            "blocks the whole site for every crawler\n"
            "1 checked, 0 ok, 1 problem(s)\n",
        )
        code, out, err = run_cli(
            "--allow-block-all", "examples/block-all-robots.txt"
        )
        self.assertEqual(
            out,
            "OK    examples/block-all-robots.txt — 1 group(s), "
            "1 rule(s), 0 sitemap(s)\n"
            "1 checked, 1 ok, 0 problem(s)\n",
        )


class TestHygiene(unittest.TestCase):
    def test_stdlib_only(self):
        import ast

        allowed = {
            "argparse",
            "ast",
            "contextlib",
            "json",
            "os",
            "re",
            "sys",
            "pathlib",
            "subprocess",
            "tempfile",
            "unittest",
        }
        for path in [SRC, Path(__file__)]:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertIn(
                            alias.name.split(".")[0],
                            allowed | {"robots_txt_checker"},
                            "%s imports %s" % (path, alias.name),
                        )
                elif isinstance(node, ast.ImportFrom):
                    self.assertIn(
                        (node.module or "").split(".")[0],
                        allowed | {"robots_txt_checker"},
                        "%s imports %s" % (path, node.module),
                    )

    def test_no_placeholders_or_secrets(self):
        banned = ["TODO", "FIXME", "coming soon", "lorem", "API_KEY"]
        bad = []
        # The tests directory is excluded from this scan: the test
        # file itself names the banned words in its own check list.
        # The .git directory is excluded too: GitHub's checkout ships
        # sample hooks under .git/hooks/ that contain "TODO" (Day 21
        # CI failure), and those are git's own files, not this repo's.
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            if "tests" in path.parts:
                continue
            text = path.read_text(
                encoding="utf-8", errors="ignore"
            )
            for word in banned:
                if word in text:
                    bad.append("%s: %s" % (path, word))
        self.assertEqual(bad, [])

    def test_gitignore_lists_env_first(self):
        lines = (ROOT / ".gitignore").read_text(
            encoding="utf-8"
        ).splitlines()
        self.assertEqual(lines[0], ".env")


if __name__ == "__main__":
    unittest.main()
