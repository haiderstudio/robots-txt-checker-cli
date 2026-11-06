# Security Policy

This tool runs locally, collects no data, sends nothing anywhere, and needs no API key or secret. It only reads the robots.txt files you name (or text you pipe in), and it never rewrites a file, never fetches a URL, and never changes anything on disk. It writes nothing except the report on standard output (and usage errors on standard error).

If you find a case where the tool changes a file, fetches a URL, or reports a pass for a robots.txt line that is not well formed, please open an issue describing the exact commands and input. Do not include any real secret in the report.
