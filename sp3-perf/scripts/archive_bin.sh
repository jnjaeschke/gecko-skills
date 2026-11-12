#!/bin/bash
# Snapshot a built Firefox so it survives the next build of the same objdir.
#
#   archive_bin.sh <objdir> <destination>
#   archive_bin.sh obj-opt bins/base
#
# dist/bin is mostly symlinks into the objdir; -L copies what they point to, so
# the snapshot keeps running after the objdir is rebuilt. Expect a few GB each.
# Launch the copy as <destination>/firefox.
set -euo pipefail
objdir=$1
dest=$2
if [ ! -x "$objdir/dist/bin/firefox" ]; then
  echo "no built Firefox in $objdir/dist/bin" >&2
  exit 1
fi
rm -rf "$dest"
mkdir -p "$(dirname "$dest")"
cp -aL "$objdir/dist/bin" "$dest"
du -sh "$dest"
