#!/usr/bin/env bash
# Log files बदलले असल्यास commit + push (दुसऱ्या run शी conflict झाल्यास 3 वेळा retry)
# वापर: scripts/commit_log.sh "message" [file ...]   (default: public/log/cue-log.json)
set -euo pipefail
MSG="${1:-Update cue log}"
shift || true
FILES=("$@")
if [ ${#FILES[@]} -eq 0 ]; then FILES=(public/log/cue-log.json); fi
git config user.name "github-actions[bot]"
git config user.email "41898531+github-actions[bot]@users.noreply.github.com"
git add -- "${FILES[@]}"
if git diff --cached --quiet; then
  echo "No log changes"
  exit 0
fi
git commit -q -m "$MSG"
for attempt in 1 2 3; do
  if git pull -q --rebase origin main && git push -q origin HEAD:main; then
    echo "Log pushed"
    exit 0
  fi
  sleep $((attempt * 5))
done
echo "ERROR: could not push log" >&2
exit 1
