#!/usr/bin/env bash
# Helper: convert common shell/script files to LF and set execute bit where appropriate
set -e

echo "Fixing line endings (to LF) for shell and py files..."
# find common script files
files=$(git ls-files '*.sh' '*.py' '*.env' || true)
if [ -z "$files" ]; then
  echo "No matching files tracked by git. Scanning workspace..."
  files=$(find . -type f -name "*.sh" -o -name "*.py" -o -name ".env" )
fi

for f in $files; do
  if [ -f "$f" ]; then
    echo "Processing: $f"
    # remove CR (carriage return)
    sed -i 's/\r$//' "$f" || true
    # if it's a shell script, ensure executable
    case "$f" in
      *.sh)
        chmod +x "$f" || true
        ;;
    esac
  fi
done

echo "Done. Consider committing .gitattributes to enforce LF on checkout."