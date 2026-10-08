"""Update the test count badge in README.md based on collected tests."""
import re
import sys
import subprocess
from pathlib import Path


def update_badge() -> int:
    readme_path = Path("README.md")
    if not readme_path.exists():
        return 0

    res = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"], capture_output=True, text=True)
    count = None
    for line in res.stdout.splitlines():
        m = re.search(r"(\d+)\s+tests?\s+collected", line)
        if m:
            count = int(m.group(1))
            break
    if not count:
        lines = [l.strip() for l in res.stdout.splitlines() if "::" in l]
        if lines:
            count = len(lines)

    if not count:
        print("Could not determine test count")
        return 0

    content = readme_path.read_text(encoding="utf-8")
    new_content = re.sub(
        r"\[!\[Tests: \d+ Passing\]\(https://img\.shields\.io/badge/tests-\d+%20passing-brightgreen\.svg\)\]\(\)",
        f"[![Tests: {count} Passing](https://img.shields.io/badge/tests-{count}%20passing-brightgreen.svg)]()",
        content
    )
    if new_content != content:
        readme_path.write_text(new_content, encoding="utf-8")
        print(f"Updated README badge to {count} passing tests")
    else:
        print(f"Badge already up to date with {count} passing tests")
    return count


if __name__ == "__main__":
    update_badge()
