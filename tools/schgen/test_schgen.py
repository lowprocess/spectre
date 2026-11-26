"""Checks on the generated schematic and floorplan.

    python3 -m unittest tools.schgen.test_schgen      (from the repository)

The KiCad checks run only where kicad-cli is installed."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

from . import __main__ as gen
from . import design, floorplan
from .sexpr import find, find_all, parse


class Generated(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = tempfile.mkdtemp()
        cls.d, cls.sheets = gen.write(cls.out)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.out)

    def test_no_wires_drawn_over_each_other(self):
        for s in self.sheets.values():
            self.assertEqual(s.overlaps(), [], s.filename)

    def test_references_are_unique(self):
        seen = {}
        for s in self.sheets.values():
            for inst in s.insts:
                for ref in inst.refs:
                    if ref.startswith("#"):
                        continue
                    key = (ref, inst.uuid)
                    self.assertNotIn(ref, [r for r, u in seen
                                           if u != inst.uuid], ref)
                    seen[key] = True

    def test_every_printed_filter_is_on_the_floorplan(self):
        filters = floorplan.filters_of(self.sheets)
        self.assertEqual(sorted(filters), sorted(floorplan.FILTERS))
        for ref, (name, _, _, _, _) in filters.items():
            self.assertTrue(os.path.exists(os.path.join(
                self.out, "footprints", "spectre_filters.pretty",
                name + ".kicad_mod")), name)

    def test_floorplan_leaves_the_board_as_it_was(self):
        with open(os.path.join(gen.REPO, "spectre.kicad_pcb")) as fh:
            before = fh.read()
        once = floorplan.apply(before, self.sheets)
        self.assertEqual(floorplan.apply(once, self.sheets), once)
        # the project's own footprints and tracks are all still there
        for token in ("segment", "via"):
            self.assertEqual(once.count("(%s\n" % token),
                             before.count("(%s\n" % token))
        self.assertIn('"ar_ic:QFN40"', once)

    @unittest.skipUnless(shutil.which("kicad-cli"), "no kicad-cli")
    def test_kicad_finds_no_errors_in_the_new_sheets(self):
        report = os.path.join(self.out, "erc.json")
        subprocess.run(["kicad-cli", "sch", "erc", "--severity-all",
                        "--format", "json", "-o", report,
                        os.path.join(self.out, "spectre.kicad_sch")],
                       check=True, capture_output=True)
        with open(report) as fh:
            data = json.load(fh)
        bad = []
        for sheet in data["sheets"]:
            for v in sheet["violations"]:
                if v["type"] in ("lib_symbol_issues", "footprint_link_issues"):
                    continue          # this machine's library tables
                items = " ".join(i["description"] for i in v["items"])
                # the synthesizer sheet is the project's own
                if sheet["path"] in ("/LO1/", "/LO2/") or "LO_B" in items:
                    continue
                bad.append((sheet["path"], v["description"], items))
        self.assertEqual(bad, [])

    @unittest.skipUnless(shutil.which("kicad-cli"), "no kicad-cli")
    def test_nets_reach_across_the_sheets(self):
        net = os.path.join(self.out, "n.net")
        subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format",
                        "kicadsexpr", "-o", net,
                        os.path.join(self.out, "spectre.kicad_sch")],
                       check=True, capture_output=True)
        with open(net) as fh:
            tree = parse(fh.read())
        nets = {}
        for n in find_all(find(tree, "nets"), "net"):
            nets[str(find(n, "name")[1])] = {
                "%s.%s" % (find(x, "ref")[1], find(x, "pin")[1])
                for x in find_all(n, "node")}

        def joined(*pins):
            return any(set(pins) <= nodes for nodes in nets.values())
        # synthesizer outputs to the mixers' buffers, references, SPI
        self.assertTrue(joined("C16.2", "R501.1"))      # LO1 to its drive
        self.assertTrue(joined("C29.2", "R551.1"))      # LO2 to its drive
        self.assertTrue(joined("U400.8", "R505.2"))     # drive to MIX1
        self.assertTrue(joined("U403.8", "R555.2"))     # drive to MIX2
        self.assertTrue(joined("C1.1", "R712.2"))       # 40 MHz to LO1
        self.assertTrue(joined("C26.1", "R713.2"))      # 40 MHz to LO2
        self.assertTrue(joined("U3.24", "U800.16"))     # LO1 chip select
        self.assertTrue(joined("U4.24", "U800.18"))     # LO2 chip select
        self.assertTrue(joined("U701.?D9", "U800.7"))   # ADC MSB
        self.assertTrue(joined("U101.2", "C101.1"))     # direct path
        # and nothing joins two of the control nets
        for a, b in (("U402.14", "U600.11"), ("U300.14", "U302.14"),
                     ("U3.16", "U4.16")):
            self.assertFalse(joined(a, b), (a, b))


if __name__ == "__main__":
    unittest.main()
