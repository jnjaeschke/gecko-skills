"""Read out a Speedometer 3 try comparison from Treeherder's perfcompare API.

  python3 perfcompare.py BASE_REVISION NEW_REVISION [--save cmp.json]
  python3 perfcompare.py --load cmp.json

Revisions are the full try revisions of the base and the new push (from the
Treeherder push page, or `treeherder-cli <lando id> --match-filter all`).

Prints, per platform, the change of the score and of every suite as
"median delta [bootstrap 95% interval]", positive = better, * = interval
excludes 0, followed by the number of jobs on each side.

The API repeats each job's value once per replicate, so 20 jobs show up as 100
values. Treating those as 100 samples makes intervals about twice too narrow.
This script keeps one value per job before bootstrapping.
"""

import argparse
import json
import random
import statistics
import subprocess

API = (
    "https://treeherder.mozilla.org/api/perfcompare/results/"
    "?base_repository={repo}&base_revision={base}"
    "&new_repository={repo}&new_revision={new}"
    "&framework=13&interval=86400&no_subtests=false"
)


def per_job(job_ids, values):
    return list(dict(zip(job_ids, values)).values())


def delta(base, new, resamples=4000):
    rng = random.Random(1)
    point = (statistics.median(new) / statistics.median(base) - 1) * 100
    samples = sorted(
        (
            statistics.median(rng.choices(new, k=len(new)))
            / statistics.median(rng.choices(base, k=len(base)))
            - 1
        )
        * 100
        for _ in range(resamples)
    )
    return point, samples[int(resamples * 0.025)], samples[int(resamples * 0.975) - 1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revisions", nargs="*")
    parser.add_argument("--repo", default="try")
    parser.add_argument("--suite", default="speedometer3")
    parser.add_argument("--save")
    parser.add_argument("--load")
    args = parser.parse_args()

    if args.load:
        data = json.load(open(args.load))
    else:
        if len(args.revisions) != 2:
            parser.error("need BASE_REVISION and NEW_REVISION, or --load")
        url = API.format(repo=args.repo, base=args.revisions[0], new=args.revisions[1])
        text = subprocess.run(
            ["curl", "-s", url], capture_output=True, text=True, check=True
        ).stdout
        if args.save:
            open(args.save, "w").write(text)
        data = json.loads(text)

    table = {}
    for row in data:
        if row["suite"] != args.suite or not row["base_runs"] or not row["new_runs"]:
            continue
        if row["test"] != "score" and not row["test"].endswith("/total"):
            continue
        base = per_job(row["base_retriggerable_job_ids"], row["base_runs"])
        new = per_job(row["new_retriggerable_job_ids"], row["new_runs"])
        point, low, high = delta(base, new)
        if row["test"] != "score":
            point, low, high = -point, -high, -low
        table.setdefault(row["platform"], {})[row["test"]] = (
            point,
            low,
            high,
            len(base),
            len(new),
        )
    if not table:
        raise SystemExit("no results yet for this pair (jobs still running?)")

    for platform in sorted(table):
        print(f"=== {platform}   (positive = better)")
        tests = table[platform]
        for test in sorted(tests, key=lambda t: (t != "score", t)):
            point, low, high, base_n, new_n = tests[test]
            mark = "*" if low > 0 or high < 0 else " "
            name = test.replace("/total", "")
            print(
                f"  {name:44} {point:+6.2f} [{low:+5.2f},{high:+5.2f}]{mark}"
                f"  n={base_n}/{new_n}"
            )


if __name__ == "__main__":
    main()
