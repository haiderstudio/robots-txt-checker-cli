#!/bin/sh
# Run the bundled examples. The bad file is expected to fail (exit
# 1), so its check is followed by `|| true`; the script itself exits
# 0 when every output matches the sample output.
set -e
cd "$(dirname "$0")/.."

python3 src/robots_txt_checker.py examples/bad-robots.txt || true
python3 src/robots_txt_checker.py examples/good-robots.txt
python3 src/robots_txt_checker.py examples/block-all-robots.txt || true
python3 src/robots_txt_checker.py --allow-block-all examples/block-all-robots.txt
