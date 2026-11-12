"""Paired statistics for sp3_ab.py result files.

For every metric and configuration, prints the mean per-round delta against the
baseline with a bootstrap 95% interval. Rounds are paired: round i of a
configuration is compared with round i of the baseline, which cancels drift.

  python3 sp3_ab_stats.py results-1.json results-2.json
  python3 sp3_ab_stats.py results.json --base patch-off --pair patch:patch-off

Several files with the same configuration names are concatenated. --pair A:B
adds a direct A-versus-B column. An interval that excludes 0 is marked with *,
from 5 rounds on; a bootstrap over fewer rounds understates the spread.
Suite times are lower-is-better; Score is higher-is-better.

Always include two configurations that should not differ (the same binary
twice, or a pref that the suite never reaches). Their delta is the noise floor;
anything of that size elsewhere in the table is not a result.
"""

import argparse
import json
import random
import statistics


def interval(deltas, resamples=4000):
    rng = random.Random(1)
    means = sorted(
        statistics.mean(rng.choices(deltas, k=len(deltas))) for _ in range(resamples)
    )
    return means[int(resamples * 0.025)], means[int(resamples * 0.975) - 1]


MIN_ROUNDS = 5


def cell(new, base, metric):
    deltas = [n[metric] / b[metric] - 1 for n, b in zip(new, base)]
    low, high = interval(deltas)
    mark = "*" if len(deltas) >= MIN_ROUNDS and (low > 0 or high < 0) else " "
    return f"{statistics.mean(deltas) * 100:+6.1f}% [{low * 100:+5.1f},{high * 100:+5.1f}]{mark}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+")
    parser.add_argument("--base")
    parser.add_argument("--pair", action="append", default=[], metavar="A:B")
    args = parser.parse_args()

    runs = {}
    for path in args.files:
        for name, rounds in json.load(open(path)).items():
            runs.setdefault(name, []).extend(rounds)
    base = args.base or next(iter(runs))
    count = min(len(rounds) for rounds in runs.values())
    print(f"{count} paired rounds; baseline {base}; mean delta [95% interval]")
    if count < MIN_ROUNDS:
        print(f"fewer than {MIN_ROUNDS} rounds: intervals are not trustworthy, no * shown")

    columns = [(name, name, base) for name in runs if name != base]
    for pair in args.pair:
        a, b = pair.split(":")
        columns.append((f"{a} vs {b}", a, b))
    print(f"{'metric':28}" + "".join(f"{title:>26}" for title, _, _ in columns))
    for metric in sorted(runs[base][0]):
        if metric.startswith("Iteration"):
            continue
        row = f"{metric:28}"
        for _, new, ref in columns:
            row += cell(runs[new][:count], runs[ref][:count], metric).rjust(26)
        print(row)


if __name__ == "__main__":
    main()
