"""Write the schematic into the project: python3 -m tools.schgen (from the
repository's root), or python3 tools/schgen out_dir to write a copy."""

import json
import os
import re
import shutil
import sys

from . import design, floorplan, parts
from .sexpr import Q, dump, parse, top_spans

REPO = parts.REPO
SYM_VERSION = "20251024"


def _library(sheets):
    """The symbols drawn here, as a library the project can edit."""
    syms = {}
    for s in sheets.values():
        for lib_id, sym in s.libs.items():
            if lib_id.startswith(parts.LIB + ":"):
                syms[lib_id] = sym
    out = ["kicad_symbol_lib", ["version", SYM_VERSION],
           ["generator", Q("spectre_schgen")], ["generator_version", Q("1")]]
    for lib_id in sorted(syms):
        sym = [x for x in syms[lib_id]]
        sym[1] = Q(lib_id.split(":", 1)[1])
        out.append(sym)
    return dump(out) + "\n"


def write(out):
    d, sheets = design.build()
    os.makedirs(out, exist_ok=True)
    # the root keeps the project's drawing sheet, which lives inside it
    old_root = os.path.join(REPO, "spectre.kicad_sch")
    with open(old_root, encoding="utf-8") as fh:
        old = fh.read()
    for token, a, b in top_spans(old):
        if token == "embedded_files":
            sheets["root"].raw_tail = old[a:b]
    for s in sheets.values():
        for pair in s.overlaps():
            print("%s: wires drawn over each other: %s" % (s.filename, pair),
                  file=sys.stderr)
        with open(os.path.join(out, s.filename), "w", encoding="utf-8") as fh:
            fh.write(s.text_out())
    # the synthesizer sheet is the project's own; only its control bus
    # gets the name its wires already use (SYN.SCK, ...)
    with open(os.path.join(REPO, "lo.kicad_sch"), encoding="utf-8") as fh:
        lo = fh.read()
    lo = lo.replace('(hierarchical_label "{SYN_CTRL}"',
                    '(hierarchical_label "SYN{SYN_CTRL}"')
    with open(os.path.join(out, "lo.kicad_sch"), "w", encoding="utf-8") as fh:
        fh.write(lo)
    # the project: bus aliases, and the libraries beside it
    with open(os.path.join(REPO, "spectre.kicad_pro"), encoding="utf-8") as fh:
        pro = json.load(fh)
    pro.setdefault("schematic", {})["bus_aliases"] = design.ALIASES
    with open(os.path.join(out, "spectre.kicad_pro"), "w",
              encoding="utf-8") as fh:
        json.dump(pro, fh, indent=2)
        fh.write("\n")
    with open(os.path.join(out, "spectre.kicad_sym"), "w",
              encoding="utf-8") as fh:
        fh.write(_library(sheets))
    with open(os.path.join(out, "sym-lib-table"), "w", encoding="utf-8") as fh:
        fh.write('(sym_lib_table\n\t(version 7)\n\t(lib (name "spectre")'
                 '(type "KiCad")(uri "${KIPRJMOD}/spectre.kicad_sym")'
                 '(options "")(descr "Parts of the 6.4 GHz proposal"))\n)\n')
    with open(os.path.join(out, "fp-lib-table"), "w", encoding="utf-8") as fh:
        fh.write('(fp_lib_table\n\t(version 7)\n\t(lib (name '
                 '"spectre_filters")(type "KiCad")(uri "${KIPRJMOD}/'
                 'footprints/spectre_filters.pretty")(options "")(descr '
                 '"Printed filters, from sim/filters (dfsynth)"))\n)\n')
    pretty = os.path.join(out, "footprints", "spectre_filters.pretty")
    os.makedirs(pretty, exist_ok=True)
    src = os.path.join(REPO, "sim", "filters")
    for f in sorted(os.listdir(src)):
        if f.endswith(".kicad_mod"):
            with open(os.path.join(src, f), encoding="utf-8") as fh:
                text = fh.read()
            name = f[:-len(".kicad_mod")]
            text = re.sub(r'\(footprint "[^"]*"', '(footprint "%s"' % name,
                          text, count=1)
            tie = " ".join('"%s"' % x for x in floorplan.tie_groups(
                name, parse(text)))
            text = text.replace("(attr smd)", "(attr smd)\n\t"
                                "(net_tie_pad_groups %s)" % tie, 1)
            with open(os.path.join(pretty, f), "w", encoding="utf-8") as fh:
                fh.write(text)
    with open(os.path.join(REPO, "spectre.kicad_pcb"), encoding="utf-8") as fh:
        pcb = fh.read()
    with open(os.path.join(out, "spectre.kicad_pcb"), "w",
              encoding="utf-8") as fh:
        fh.write(floorplan.apply(pcb, sheets))
    return d, sheets


if __name__ == "__main__":
    write(sys.argv[1] if len(sys.argv) > 1 else REPO)
