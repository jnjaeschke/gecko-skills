"""Interleaved local A/B of Speedometer 3 across (binary, prefs) configurations.

Each round launches every configuration once, rotating the order between
rounds, so slow drift of the machine hits all configurations alike. A launch
runs the selected suites --iterations times in a fresh headless Firefox and
records the per-suite mean (ms, lower is better) plus the score.

Run from the root of a Firefox checkout, so the in-tree Speedometer 3 copy and
the Marionette client are available:

  ./mach python <skill>/scripts/sp3_ab.py \
      --config base=bins/base/firefox \
      --config patch=bins/patch/firefox \
      --config patch-off=bins/patch/firefox:some.pref.enabled=false \
      --suites TodoMVC-jQuery,NewsSite-Next --rounds 6 --iterations 8 \
      --out results.json

A configuration is NAME=BINARY[:PREF=VALUE[,PREF=VALUE...]]. The first one is
the baseline. Omit --suites to run all default suites (several minutes per
launch). Feed the --out file(s) to sp3_ab_stats.py for paired statistics.
"""

import argparse
import functools
import http.server
import json
import os
import statistics
import threading
import time
from pathlib import Path

from marionette_driver.marionette import Marionette

DEFAULT_SP3 = "third_party/webkit/PerformanceTests/Speedometer3"


def serve(directory):
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(directory)
    )
    handler.log_message = lambda *a: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def parse_config(text):
    name, rest = text.split("=", 1)
    binary, _, prefs = rest.partition(":")
    parsed = {}
    for item in filter(None, prefs.split(",")):
        key, value = item.split("=", 1)
        if value.lstrip("-").isdigit():
            parsed[key] = int(value)
        else:
            parsed[key] = {"true": True, "false": False}.get(value, value)
    binary = Path(binary).resolve()
    if not binary.exists():
        raise SystemExit(f"{name}: no such binary {binary}")
    return name, str(binary), parsed


def launch(binary, port, prefs, suites, iterations):
    marionette = Marionette(
        bin=binary,
        headless=True,
        prefs={
            "browser.startup.homepage": "about:blank",
            "browser.startup.page": 0,
            "datareporting.policy.dataSubmissionEnabled": False,
            "toolkit.telemetry.enabled": False,
            **prefs,
        },
        startup_timeout=180,
        socket_timeout=3600,
    )
    marionette.start_session()
    try:
        marionette.timeout.page_load = 120
        suite_param = f"&suites={suites}" if suites else ""
        marionette.navigate(
            f"http://127.0.0.1:{port}/index.html?startAutomatically"
            f"&iterationCount={iterations}{suite_param}"
        )
        start = time.time()
        while not marionette.execute_script(
            "return !!window.wrappedJSObject.benchmarkClient?._hasResults;"
        ):
            if time.time() - start > 3000:
                raise RuntimeError("Speedometer 3 did not finish")
            time.sleep(2)
        metrics = json.loads(
            marionette.execute_script(
                "return JSON.stringify(window.wrappedJSObject.benchmarkClient._metrics);"
            )
        )
    finally:
        marionette.cleanup()
    return {
        name: m["mean"]
        for name, m in metrics.items()
        if "/" not in name and not name.startswith("Iteration")
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", action="append", required=True)
    parser.add_argument("--suites", default="")
    parser.add_argument("--rounds", type=int, default=6)
    parser.add_argument("--iterations", type=int, default=8)
    parser.add_argument("--sp3-dir", default=DEFAULT_SP3)
    parser.add_argument("--out")
    args = parser.parse_args()

    sp3 = Path(args.sp3_dir).resolve()
    if not (sp3 / "index.html").exists():
        raise SystemExit(f"no Speedometer 3 at {sp3}; run from the checkout root")
    configs = [parse_config(c) for c in args.config]
    cores = os.cpu_count() or 1
    load = os.getloadavg()[0]
    print(f"load average {load:.1f} on {cores} cores at start", flush=True)
    if load > cores / 4:
        print("WARNING: machine is busy; results will be noisy", flush=True)

    server = serve(sp3)
    port = server.server_address[1]
    results = {name: [] for name, _, _ in configs}
    for round_index in range(args.rounds):
        shift = round_index % len(configs)
        for name, binary, prefs in configs[shift:] + configs[:shift]:
            means = launch(binary, port, prefs, args.suites, args.iterations)
            results[name].append(means)
            print(
                f"round {round_index + 1} {name}: "
                + " ".join(f"{k}={v:.2f}" for k, v in sorted(means.items())),
                flush=True,
            )
            if args.out:
                Path(args.out).write_text(json.dumps(results))
    server.shutdown()
    print(f"load average {os.getloadavg()[0]:.1f} at end")

    base = configs[0][0]
    names = [name for name, _, _ in configs]
    print(f"{'metric':36}" + "".join(f"{n:>18}" for n in names))
    for metric in sorted(results[base][0]):
        base_median = statistics.median(r[metric] for r in results[base])
        cells = []
        for name in names:
            median = statistics.median(r[metric] for r in results[name])
            delta = "" if name == base else f" {(median / base_median - 1) * 100:+.1f}%"
            cells.append(f"{median:.2f}{delta}".rjust(18))
        print(f"{metric:36}" + "".join(cells))
    print("medians only; run sp3_ab_stats.py on the --out file for intervals")


if __name__ == "__main__":
    main()
