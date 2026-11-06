# robots-txt-checker-cli

Check robots.txt is well formed, fail CI on a bad rule.

[![CI](https://github.com/haiderstudio/robots-txt-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/robots-txt-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`robots_txt_checker` reads a local robots.txt file and checks it
is well formed: every line is a `Directive: value` line, every
directive is one a crawler knows, every Allow or Disallow rule sits
inside a User-agent group, every Sitemap line is a real URL, and
every Crawl-delay is a number. Each problem is reported with its
file and line number, and the command exits 1 when any file has a
problem — so a CI step can fail the build on a bad robots.txt.

- It flags rules that appear before any User-agent group: a
  Disallow line with no group above it applies to nobody, so it is
  almost always a copy-paste mistake.
- It flags unknown directives, including typos like `Banana:` —
  a crawler quietly ignores a directive it does not know, so a
  misspelt rule looks fine and does nothing.
- It flags a Sitemap line that is not a URL (`Sitemap: sitemap.xml`
  is a file name, not an address a crawler can fetch).
- It flags `Disallow: /` under `User-agent: *`, which blocks the
  whole site for every crawler — the most common way a site
  disappears from search by mistake. `--allow-block-all` allows
  it when the block is on purpose.
- It flags a User-agent that appears in two separate groups, and
  a file with no User-agent group at all.
- It checks as many files as you name, reads from `--stdin` for
  pipes, and prints `--json` for scripts. In JSON mode the summary
  line goes to standard error, so the standard output is clean
  JSON.
- It is report-only and runs fully offline: it reads only the
  files you name, changes nothing, fetches no URL, and needs no
  API key.

## What it does NOT do

- It does not fetch a live robots.txt from a website. It checks
  only the local file you give it. Checking a live site is a
  different tool's job.
- It does not check whether a URL is allowed or blocked by the
  rules. It checks the shape of the file, not what the rules mean
  for one address.
- It does not check your sitemap file, your meta robots tags, or
  your crawl budget. It checks robots.txt and nothing else.
- It does not fix a bad file. A problem is reported with its line
  number, not repaired.

## Who it is for

Anyone who ships a robots.txt and wants to know it is well formed
before it goes live: a developer adding a CI step that fails the
build on a bad rule, someone who just edited robots.txt by hand
and wants a second pair of eyes, or anyone who has ever lost
search traffic to one wrong line and does not want it to happen
again. If the file is clean, you get the group and rule counts;
if it is not, the report says exactly which line went wrong.

## How this differs from similar tools

Most robots.txt checkers check a live site: tomverran/robots
(PHP, 10 stars) is a robots.txt checker that fetches the live
file, w0nkarov/robosnap (Python, 2 stars) is a fast command-line
checker for live sites, and tberlin-om/robots-txt-checker
(Python, 1 star) checks a live file's content and status code
and sends an email when the check fails. The closest name match,
nadeemalamseo/robots-txt-checker (Python, 0 stars), reviews
syntax, directives, and sitemap references for a site. The wider
search (`robots txt validator`) is topped by tools that answer a
different question — whether one URL is allowed or blocked by a
robots.txt — including a 23-star Python script that checks URLs
against the rules, and validators for LLM crawlers.

This tool does a narrower job: a Python standard-library-only
CLI that checks a local robots.txt file's shape, reports each
problem with its line number, and exits 1 on any problem for
CI — no install beyond Python, no network, no live site, no
monitoring, no email.

## Install

Python standard library only — no packages to download. Clone the
repo and run it in place:

```sh
git clone https://github.com/haiderstudio/robots-txt-checker-cli.git
cd robots-txt-checker-cli
```

Python 3.10 or newer.

## Usage

Check the bundled bad example:

```sh
python3 src/robots_txt_checker.py examples/bad-robots.txt
```

Real output:

```text
FAIL  examples/bad-robots.txt:1: rule 'Disallow' appears before any User-agent group
FAIL  examples/bad-robots.txt:3: unknown directive 'Banana'
FAIL  examples/bad-robots.txt:4: Disallow: / blocks the whole site for every crawler
FAIL  examples/bad-robots.txt:5: User-agent '*' already has a group
FAIL  examples/bad-robots.txt:7: Sitemap is not a URL
FAIL  examples/bad-robots.txt:8: Crawl-delay is not a number
FAIL  examples/bad-robots.txt:9: not a field: value line — expected 'Directive: value'
1 checked, 0 ok, 7 problem(s)
```

The command exits 1, because the file has seven problems. The
same output is saved in `examples/sample-output.txt`.

Check the good example:

```sh
python3 src/robots_txt_checker.py examples/good-robots.txt
```

Real output:

```text
OK    examples/good-robots.txt — 2 group(s), 4 rule(s), 1 sitemap(s)
1 checked, 1 ok, 0 problem(s)
```

The command exits 0. A well-formed file passes.

Check a file from a pipe:

```sh
printf 'User-agent: *\nDisallow: /private/\n' | python3 src/robots_txt_checker.py --stdin
```

Real output:

```text
OK    <stdin> — 1 group(s), 1 rule(s), 0 sitemap(s)
1 checked, 1 ok, 0 problem(s)
```

The same check as JSON:

```sh
python3 src/robots_txt_checker.py --json examples/good-robots.txt
```

Real output:

```text
{
  "checked": 1,
  "ok": 1,
  "problems": 0,
  "results": [
    {
      "file": "examples/good-robots.txt",
      "ok": true,
      "problems": [],
      "groups": 2,
      "rules": 4,
      "sitemaps": 1
    }
  ]
}
```

In `--json` mode the summary line (`1 checked, 1 ok, 0 problem(s)`)
goes to standard error, so the standard output is clean JSON a
script can parse.

## Examples

### 1. Fail CI on a bad robots.txt

```sh
python3 src/robots_txt_checker.py robots.txt
echo $?
```

```text
FAIL  robots.txt:1: rule 'Disallow' appears before any User-agent group
1 checked, 0 ok, 1 problem(s)
1
```

The exit code is 1 when a file has a problem. Put the same
command in CI and the build fails until the file is fixed. With
a clean file the same command prints `OK` and exits 0.

### 2. A site blocked on purpose

```sh
python3 src/robots_txt_checker.py examples/block-all-robots.txt
```

```text
FAIL  examples/block-all-robots.txt:3: Disallow: / blocks the whole site for every crawler
1 checked, 0 ok, 1 problem(s)
```

That file blocks every crawler on purpose, so allow it:

```sh
python3 src/robots_txt_checker.py --allow-block-all examples/block-all-robots.txt
```

```text
OK    examples/block-all-robots.txt — 1 group(s), 1 rule(s), 0 sitemap(s)
1 checked, 1 ok, 0 problem(s)
```

### 3. Check every robots.txt in a folder

```sh
python3 src/robots_txt_checker.py examples/good-robots.txt examples/bad-robots.txt
```

```text
OK    examples/good-robots.txt — 2 group(s), 4 rule(s), 1 sitemap(s)
FAIL  examples/bad-robots.txt:1: rule 'Disallow' appears before any User-agent group
FAIL  examples/bad-robots.txt:3: unknown directive 'Banana'
FAIL  examples/bad-robots.txt:4: Disallow: / blocks the whole site for every crawler
FAIL  examples/bad-robots.txt:5: User-agent '*' already has a group
FAIL  examples/bad-robots.txt:7: Sitemap is not a URL
FAIL  examples/bad-robots.txt:8: Crawl-delay is not a number
FAIL  examples/bad-robots.txt:9: not a field: value line — expected 'Directive: value'
2 checked, 1 ok, 7 problem(s)
```

The exit code is 1, because one of the two files has problems.

## How it is tested

```sh
python3 tests/test_robots_txt_checker.py
```

43 tests, standard library `unittest` only — no third-party
packages. They cover: the file shape (good file, empty file,
comments and blank lines, case-insensitive directives, inline
comments, an empty Disallow meaning "allow all"), each problem
(rule before any User-agent group, unknown directive, empty
User-agent value, no User-agent group at all, duplicate
User-agent group, same agent twice in one group, Sitemap not a
URL, Crawl-delay not a number, a line with no colon, a whole-site
block and its `--allow-block-all` flag), reading files (missing
file, non-UTF-8 file, a directory), the CLI (exit 0/1/2, the
default `robots.txt`, `--stdin`, `--json`, `--version`, bad
flags, files plus `--stdin`, input files unchanged), the bundled
examples (the committed `examples/sample-output.txt` is compared
byte-for-byte against a fresh run, the example script is run,
and every line of the sample output is checked to appear in this
README), and a check that the code and the tests import standard
library only.

The bundled example is a real run, not made-up output:

```sh
sh examples/run-example.sh
```

It checks the bad file (7 problems), the good file (clean), the
block-all file (1 problem), and the block-all file again with
`--allow-block-all` (clean). The committed
`examples/sample-output.txt` is the output of the bad-file check.

## Contributing

Small, focused improvements are welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

Built from scratch for this repo. The robots.txt rules checked
here follow the plain shape of the format (User-agent groups,
Allow and Disallow rules, Sitemap lines) as used across the web;
no code was copied from any existing robots.txt checker.
