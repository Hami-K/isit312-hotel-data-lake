#!/bin/sh
# Fallback mapper (used only if python3 is missing on the NodeManager container).
awk -F, '$1 != "check_id" && NF >= 6 { printf "%s\t%s\n", $2, $5 }'
