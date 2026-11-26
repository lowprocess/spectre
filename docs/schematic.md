# Schematic and floorplan of the 6.4 GHz proposal

The proposal in [sim/README.md](../sim/README.md), drawn as a KiCad 10
schematic with real parts, and a floorplan of the board with the printed
filters in place.

- [schematic.pdf](schematic.pdf): all 13 pages.
- [floorplan.svg](floorplan.svg): the board, top copper and the floorplan
  layer.

Open `spectre.kicad_pro` in KiCad 10 to work on it.

## Sheets

| Page | Sheet | File | What is on it |
|---|---|---|---|
| 1 | top | `spectre.kicad_sch` | the blocks, signal left to right |
| 2 | LO1 | `lo.kicad_sch` | LMX2572 (yours, unchanged but for one label) |
| 3 | LO1 Drive | `lo_drive.kicad_sch` | pad, PMA3-83LN+ buffer, pad |
| 4, 5 | LO2, LO2 Drive | same two files | second instance |
| 6 | RF Input | `rf_input.kicad_sch` | SMA, DC block, ESD diode, PE43704, PE42540, direct-path low-pass |
| 7 | Low Band Front End | `fe_low.kicad_sch` | L1 (2 x LFCN-2250+), L2 (printed band-pass), 4.0 GHz low-pass, TRF37D73 with bypass |
| 8 | High Band Front End | `fe_high.kicad_sch` | H1 and H2 (printed band-pass and low-pass each), PMA3-83LN+ with bypass |
| 9 | First IF Stage | `if_1.kicad_sch` | SIM-83+, PMA3-83LN+, 4.0 GHz low-pass, 3.4 GHz hairpin, select switch, SIM-83+, diplexer |
| 10 | Second IF Stage | `if_2.kicad_sch` | path select, LMH6629, PE43711, 17.5 MHz elliptic low-pass, LMH6629 |
| 11 | Driver, ADC & Clock | `adc.kicad_sch` | THS4541, SD9609-40, 40 MHz oscillator, LMK1C1104 |
| 12 | Controller | `controller.kicad_sch` | RP2350B, flash, USB-C, SWD |
| 13 | Power | `power.kicad_sch` | USB 5 V filter, five LP5907 regulators |

315 parts: 34 ICs, 10 filters, 164 capacitors, 67 resistors, 19 inductors.

How to read it:

- The signal runs left to right, supplies come from above, ground goes
  below.
- Controls arrive by name. Each sheet has its control bus broken out at the
  left edge (`RFIN.LE`, `FEL.SEL_1`, ...); on the top sheet a bus stub
  carries the same name at both ends. The bus contents are the aliases in
  `spectre.kicad_pro` (`IN_CTRL`, `FE_CTRL`, `IF_CTRL`, `ADC_CTRL`, next to
  your `SYN_CTRL`).
- Decoupling capacitors are drawn together in a box on each sheet, each
  marked with the part it sits at.
- References are numbered by sheet: 100s RF input, 200s low band, 300s
  high band, 400s first IF, 500s and 550s the two LO drives, 600s second
  IF, 700s ADC and clock, 800s controller, 900s power. The synthesizer
  sheet keeps your numbers.

## Parts and where their pin numbers come from

| Part | Use | Pins checked against |
|---|---|---|
| PE43704 | input attenuator, serial, address 000 | pSemi data sheet |
| PE43711 | IF attenuator, serial | pSemi data sheet |
| PE42540 | SP4T band select | pSemi data sheet |
| PE42520 (x9) | SPDT: band pairs, preamp bypass, mixer and IF select | pSemi data sheet |
| TRF37D73 | low band preamplifier | TI data sheet |
| LMH6629 (x2) | IF gain | TI data sheet (SOT-23-5) |
| THS4541 | ADC driver | TI data sheet (RGT) |
| LMK1C1104 | clock fan-out | TI data sheet |
| LP5907 (x5) | regulators | KiCad library symbol |
| RP2350B, W25Q32JV, USBLC6-2, USB-C | controller | KiCad library symbols |
| LFCN-2250+ (x2) | L1 low-pass | KiCad library symbol |
| SIM-83+ (x2) | mixers | your symbol `#bt-db:ic/ICIR-00218` |
| PMA3-83LN+ (x4) | IF1 amplifier, high band preamplifier, LO buffers | **search-result summary only**: pad 2 in, pad 8 out and supply, paddle ground |
| SD9609-40 | ADC | **partly**: only pins 1-8, 23, the four AVDD and the pad are confirmed (from the AD9609 it copies) |

## Open before layout

1. **ADC pin numbers.** I could not fetch the AD9609 or SD9609 data sheet
   from here. Eighteen pins of U701 carry a placeholder number that starts
   with `?` (`?D0`...`?D9`, `?DCO`, `?DRVDD`, `?VIN+`, `?VIN-`, `?VCM`,
   `?VREF`, `?SENSE`, `?RBIAS`), and two of the package's 32 pins are not in
   the symbol at all.
   Fill them in from the data sheet in the symbol `spectre:SD9609-40`.
   Board update will refuse the footprint until then, which is the intent.
   Check its clock input too: the sheet halves the 3.3 V clock and AC
   couples it.
2. **PMA3-83LN+ bias parts.** Mini-Circuits' site refuses downloads from
   here, so the input inductor and the supply feed inductor of each of the
   four amplifiers are marked `TBD` (L300, L301, L400, L401, L500, L501,
   L550, L551). Take the values from the data sheet's application circuit.
   Its footprint is KiCad's generic QFN-12 3x3; check it against
   Mini-Circuits' land pattern for case DQ1225.
3. **PE42540 footprint.** It is a 32-lead 5x5 mm LGA; KiCad's QFN-32 5x5 is
   assigned. Check pad lengths against pSemi's drawing.
4. **LO level.** The LO drive is pad, 21 dB buffer, pad, at 3 dB each. Set
   the pads once the LMX2572 output power in your sheet is fixed, for
   +7 dBm at the mixers.
5. **Passive part numbers.** Resistors (Vishay CRCW0402), C0G capacitors
   (Murata GRM1555C1H) and inductors (Coilcraft 0402HP and 1008CS) have
   part numbers built from the value by the makers' numbering rules. They
   were not checked for stock. Values that match your database keep its
   IPN.
6. **Supply current.** About 750 mA at 5 V, more than a USB 2.0 port gives.
   The USB-C connector asks for 5 V with 5.1 k on CC1/CC2 but nothing
   checks that the port offers 1.5 A.
7. **The synthesizer sheet's own ERC items** are as before: SYNC and
   SysRefReq open, VccDIG and VccBUF behind 0 ohm links, `LO_B` unused.

## What changed in your files

- `lo.kicad_sch`: the hierarchical label `{SYN_CTRL}` is now
  `SYN{SYN_CTRL}`, so that it meets the `SYN.SCK`... labels already on the
  sheet. Nothing else.
- `spectre.kicad_sch`: redrawn on A3. Sheet identities are kept, so the
  synthesizer annotation and its board placement still match. The
  `DEBUG` (FX3) block and `fe_select.kicad_sch` are gone; the front end is
  now `fe_low` and `fe_high`.
- `spectre.kicad_pro`: four bus aliases added.
- `spectre.kicad_pcb`: see below. `rf_io`, `lo1` and `lo2.kicad_sch` are
  untouched (they are not in the hierarchy).

## Where the schematic differs from the simulated chain

- Each LMH6629 stage has a gain of 40 (32 dB). The first drives the
  attenuator through 49.9 ohm, which gives the simulation's 26 dB in 50
  ohm. The second drives the THS4541 directly, and the THS4541 runs at
  gain 1: 32 dB together, as simulated (26 + 6).
- The anti-alias filter is drawn with standard values: 470, 470, 330,
  560 nH and E24 capacitors. With ideal parts it follows the simulated 9th
  order elliptic response; with inductor Q of 50 it droops 2 dB at 17 MHz
  and 1 dB at 15 MHz, and stays 68 dB or more down from 21.5 MHz. Calibration absorbs
  the droop.
- Added, not simulated: the 30 MHz diplexer after the second mixer, the
  5th order 30 MHz low-pass in the direct path, the LO buffers.

## Checks made

- KiCad's ERC on all sheets: no errors or warnings in the new sheets. What
  remains is in the synthesizer sheet (item 7) and library paths that only
  exist on your machine (`#bt-db`, `ar_passives`).
- The netlist: every net that crosses sheets was listed and compared with
  the design. One fault was found this way and fixed (a control stub drawn
  on top of the direct-path wire on the top sheet).
- `python3 -m unittest tools.schgen.test_schgen` repeats both checks.

## Floorplan

`spectre.kicad_pcb` now has:

- an outline, 222 x 126 mm;
- a four layer stackup: F.Cu, 0.508 mm RO4003C, In1.Cu (ground), prepreg,
  In2.Cu, FR4, B.Cu. Your board was two layer 1.51 mm FR4, on which the
  printed filters do not work;
- the eight printed filters as footprints (library `spectre_filters`, in
  `footprints/`), each tied to its schematic symbol, so "Update PCB from
  Schematic" leaves them where they are;
- a ground zone on In1.Cu under the whole board (not yet filled);
- on layer User.1 ("Floorplan"): a named region for every block with the
  parts that go in it, and the intended RF routes. Solid lines are on
  F.Cu, the dotted one is the 12 MHz IF on In2.Cu.

Your synthesizer placement and routing are untouched; four lines of the
original file changed (the stackup and the name of User.1). The layout is
built round them: low band along the top into MIX1, the first IF out to
the right and back through the hairpin filter to MIX2, high band along the
bottom, IF and digital on the right.

Known about the floorplan:

- The high band filters set the size: the H1 band-pass alone is 73 mm
  long.
- 50 ohm microstrip on the new stackup is 1.10 mm wide. The synthesizer
  outputs are routed at 0.2 mm today.
- DRC reports 59 hole-clearance items, all a filter's ground via against
  the same filter's copper. The via sits in that copper by design.
- The other parts are not on the board yet. "Update PCB from Schematic"
  brings them in, and renames the synthesizers' nets (`/LO1/REF.P` becomes
  `/REF1.P`, and so on).
- The 12 MHz IF has to cross the high band feed to reach the second IF; it
  does so on In2.Cu. IF_DIRECT, the 40 MHz references and the ADC bus are
  also meant for In2.Cu.

## Regenerating

The sheets are written by `tools/schgen` (plain Python, no dependencies):

    python3 -m tools.schgen            # writes into the project
    python3 -m tools.schgen /tmp/out   # writes a copy

`design.py` has one function per sheet, `parts.py` the symbols,
`floorplan.py` the board regions and filter positions. Running it again
overwrites edits made in KiCad to the generated sheets, so either keep
editing through the generator or stop using it once you take the
schematic over by hand. `lo.kicad_sch` is never rewritten.
