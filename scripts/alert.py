"""
S5 — Failure / recovery alert.
सलग 3रा failed run → Telegram alert (फक्त एकदाच, दर 15 मिनिटांनी spam नाही).
3+ failures नंतर पहिला success → "recovered" message.

Env: GITHUB_REPOSITORY, GH_TOKEN, CURRENT_RESULT (success/failure), TELEGRAM_* secrets.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from notify import send_telegram  # noqa: E402

WORKFLOW_FILE = "update-data.yml"
ALERT_AFTER = 3  # किती सलग failures नंतर alert


def previous_conclusions(repo: str, token: str, limit: int = 5) -> list[str]:
    """याआधीच्या completed runs चे निकाल, नवीन ते जुने (चालू run यात नसतो)."""
    url = (f"https://api.github.com/repos/{repo}/actions/workflows/{WORKFLOW_FILE}/runs"
           f"?status=completed&per_page={limit}")
    request = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(request, timeout=15) as response:
        runs = json.loads(response.read().decode("utf-8")).get("workflow_runs", [])
    return [run.get("conclusion") or "" for run in runs]


def leading_failures(conclusions: list[str]) -> int:
    """सुरुवातीपासून सलग किती failures."""
    count = 0
    for conclusion in conclusions:
        if conclusion != "failure":
            break
        count += 1
    return count


def decide(current: str, previous: list[str]) -> str | None:
    """कोणता message पाठवायचा: 'alert', 'recovered' किंवा None."""
    streak_before = leading_failures(previous)
    if current == "failure" and streak_before == ALERT_AFTER - 1:
        return "alert"
    if current == "success" and streak_before >= ALERT_AFTER:
        return "recovered"
    return None


def main() -> int:
    repo = os.environ["GITHUB_REPOSITORY"]
    current = os.environ.get("CURRENT_RESULT", "failure")
    try:
        previous = previous_conclusions(repo, os.environ["GH_TOKEN"])
    except Exception as exc:  # noqa: BLE001
        print(f"WARN: could not read run history: {exc}", file=sys.stderr)
        return 0  # alert job मुळे workflow fail होऊ नये

    action = decide(current, previous)
    runs_url = f"https://github.com/{repo}/actions/workflows/{WORKFLOW_FILE}"
    print(f"current={current} previous={previous[:4]} action={action}")
    if action == "alert":
        send_telegram(f"🔴 Global Market Desk: data update failed {ALERT_AFTER} times in a row.\n"
                      f"The dashboard is showing older data.\nCheck: {runs_url}")
    elif action == "recovered":
        send_telegram("🟢 Global Market Desk: data updates are working again.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
