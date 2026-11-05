#!/bin/bash
# Keep the data volume writable from BOTH sides (iter-141, item 890).
#
# The container runs as root; the host runs as pdsv(1000). Anything the container created was
# root-owned, so host-side maintenance (regenerating the master résumé, ad-hoc scripts) died with
# PermissionError while the same code succeeded inside the container.
#
# Fix: own the tree as pdsv, and set a DEFAULT ACL so files the root process creates later are
# still group-writable by pdsv. Re-run this after recreating the data volume.
set -euo pipefail

DATA="${1:-/mnt/storage/websites/leaploop/data}"
OWNER="${OWNER:-pdsv}"

[ -d "$DATA" ] || { echo "no such data dir: $DATA" >&2; exit 1; }
command -v setfacl >/dev/null || { echo "setfacl missing: apt install acl" >&2; exit 1; }

if [ -n "$(find "$DATA" -user root -print -quit 2>/dev/null)" ]; then
  chown -R "$OWNER:$OWNER" "$DATA" 2>/dev/null \
    || docker exec leaploop chown -R 1000:1000 /data
fi

setfacl -R  -m "g:$OWNER:rwx" "$DATA"
setfacl -R -d -m "g:$OWNER:rwx" "$DATA"

echo "ok: $DATA owned by $OWNER with inheriting group ACL"
echo "remaining root-owned entries: $(find "$DATA" -user root | wc -l)"
