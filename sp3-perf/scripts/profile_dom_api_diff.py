"""Line up DOM API entry points of a Firefox and a WebKit profile.

Both engines enter the DOM from script through generated binding functions
whose names contain the interface and the member, which makes them the one
place where two engines can be compared like for like:

  Gecko   mozilla::dom::Element_Binding::setAttribute(...)
          mozilla::dom::Element_Binding::set_innerHTML(...) / get_clientWidth(...)
  WebKit  WebCore::jsElementPrototypeFunction_setAttribute(...)
          WebCore::setJSElement_innerHTML(...) / WebCore::jsElement_clientWidth(...)

Input: the JSON of `profiler-cli thread functions --json --limit 0` for each
profile, taken with the same filter (normally: samples inside benchmark steps).

  python3 profile_dom_api_diff.py firefox.json webkit.json [--min 100]

Output: one row per interface member with total samples in each engine and the
difference, largest Firefox excess first. Totals include everything the call
runs: script called back from the DOM (click(), dispatchEvent()), forced style
and layout flushes (getBoundingClientRect, offsetWidth). A large difference is
where to look next, not the size of a fix. Members that only one engine reports
are listed too: JITs call some getters without going through the binding.
"""

import argparse
import json
import re

GECKO = re.compile(r"^mozilla::dom::(\w+?)_Binding::(?:(get|set)_)?(\w+)\(")
WEBKIT_METHOD = re.compile(r"^WebCore::js(\w+?)(?:Prototype|Instance|Constructor)Function_(\w+?)(?:Body)?\(")
WEBKIT_GETTER = re.compile(r"^WebCore::js([A-Z]\w+?)_(\w+?)(?:Getter)?\(")
WEBKIT_SETTER = re.compile(r"^WebCore::setJS([A-Z]\w+?)_(\w+?)(?:Setter)?\(")
SKIP = {"Wrap", "DefineDOMInterface", "CreateInterfaceObjects", "GetProtoObjectHandle"}


def gecko_totals(functions):
    totals = {}
    for f in functions:
        if m := GECKO.match(f["name"]):
            interface, kind, member = m.groups()
            if member in SKIP or member.startswith("_"):
                continue
            key = (interface, member, kind or "call")
            totals[key] = max(totals.get(key, 0), f["totalSamples"])
    return totals


def webkit_totals(functions):
    totals = {}
    for f in functions:
        name = f["name"]
        key = None
        if m := WEBKIT_SETTER.match(name):
            key = (m.group(1), m.group(2), "set")
        elif m := WEBKIT_METHOD.match(name):
            key = (m.group(1), m.group(2), "call")
        elif m := WEBKIT_GETTER.match(name):
            key = (m.group(1), m.group(2), "get")
        if key:
            totals[key] = max(totals.get(key, 0), f["totalSamples"])
    return totals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("firefox")
    parser.add_argument("webkit")
    parser.add_argument("--min", type=int, default=100, help="hide rows below this many samples")
    args = parser.parse_args()

    gecko = gecko_totals(json.load(open(args.firefox))["functions"])
    webkit = webkit_totals(json.load(open(args.webkit))["functions"])
    rows = []
    for key in gecko.keys() | webkit.keys():
        fx, wk = gecko.get(key), webkit.get(key)
        if max(fx or 0, wk or 0) < args.min:
            continue
        rows.append((key, fx, wk))
    rows.sort(key=lambda r: -((r[1] or 0) - (r[2] or 0)))

    print(f"{'interface.member':44}{'kind':>5}{'Firefox':>9}{'WebKit':>9}{'delta':>9}")
    for (interface, member, kind), fx, wk in rows:
        delta = "" if fx is None or wk is None else f"{fx - wk:+d}"
        print(
            f"{interface + '.' + member:44}{kind:>5}"
            f"{'-' if fx is None else fx:>9}{'-' if wk is None else wk:>9}{delta:>9}"
        )


if __name__ == "__main__":
    main()
