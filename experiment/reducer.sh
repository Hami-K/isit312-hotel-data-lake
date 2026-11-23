#!/bin/sh
# Fallback reducer: checks and revenue per outlet.
awk -F'\t' '
  $1 != cur { if (cur != "") printf "%s\t%d\t%.2f\n", cur, n, s; cur = $1; n = 0; s = 0 }
  { n++; s += $2 }
  END { if (cur != "") printf "%s\t%d\t%.2f\n", cur, n, s }'
