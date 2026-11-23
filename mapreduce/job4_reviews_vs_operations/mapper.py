#!/usr/bin/env python3
"""
Job 4 mapper: review scores against hotel operations.

Input : /datalake/curated/review_stay_link   (one CSV row per review, with its stay details)
Output: group|name <TAB> reviews <TAB> score_sum <TAB> low_scores <TAB> nights <TAB> negative_mentions

Two kinds of key are emitted for every review:
  "Room type|<room type>"   - structured data from the PMS
  "Theme|<theme>"           - found in the FREE TEXT of the review, one per theme mentioned
A theme mention is negative when the same clause holds a complaint word
("Wi-Fi kept dropping out" -> Wi-Fi, negative). This is simple keyword matching, not a
trained sentiment model; it shows that the lake can analyse unstructured text in the
same batch run as the structured data.
"""
import csv
import io
import re
import sys

COUNTS = {}   # Hadoop counters, reported once at the end (shown in the job summary)

def count(name):
    COUNTS[name] = COUNTS.get(name, 0) + 1
LOW_SCORE = 5            # a score of 5 or less out of 10 counts as a low score

# Theme -> words that show the review talks about that area of the hotel's operations
THEMES = [
    ("Wi-Fi",                 r"wi-?fi|internet"),
    ("Food and beverage",     r"breakfast|restaurant|room service|dinner|\bbar\b"),
    ("Housekeeping",          r"housekeeping|cleaned|clean|spotless|dirty"),
    ("Check-in",              r"check-?in|reception|front desk"),
    ("Room comfort",          r"\bbed\b|air conditioning|noisy|noise|\bview\b|quiet"),
    ("Staff",                 r"\bstaff\b|friendly|helpful|rude"),
    ("Pool and facilities",   r"\bpool\b|\bgym\b|\bspa\b|facilities"),
    ("Location",              r"location"),
]
THEMES = [(name, re.compile(pattern, re.I)) for name, pattern in THEMES]
NEGATIVE = re.compile(r"dropping|\bcold\b|\bslow\b|too long|\bnot\b|ran out|too loud|"
                      r"noisy|dirty|rude|broken|average|nothing special|\blate\b", re.I)

def out(key, score, nights, negative):
    print("%s\t1\t%d\t%d\t%d\t%d" % (key, score, 1 if score <= LOW_SCORE else 0,
                                     nights, 1 if negative else 0))

stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace")
for row in csv.reader(stdin):
    if not row or row[0] == "review_id":
        continue
    if len(row) != 11:
        count("Job4 rows skipped - bad format")
        continue
    room_type, text = row[4], row[10]
    try:
        score, nights = int(row[3]), int(row[6] or 0)
    except ValueError:
        count("Job4 rows skipped - bad score")
        continue
    if not 1 <= score <= 10:
        count("Job4 rows skipped - bad score")
        continue
    count("Job4 reviews read")

    if room_type:
        out("Room type|" + room_type, score, nights, False)

    # Split the text into clauses, then record each theme once per review
    found = {}
    for clause in re.split(r"[.!?,;]", text):
        for name, pattern in THEMES:
            if pattern.search(clause):
                found[name] = found.get(name, False) or bool(NEGATIVE.search(clause))
    if not found and text.strip():
        count("Job4 reviews with no theme found")
    for name in sorted(found):
        out("Theme|" + name, score, nights, found[name])

for name in sorted(COUNTS):
    sys.stderr.write("reporter:counter:Hotel data lake,%s,%d\n" % (name, COUNTS[name]))
