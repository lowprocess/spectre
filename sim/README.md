# The analyzer's signal chain, simulated

A behavioural simulation of this spectrum analyzer: what it reads for a given
set of input signals, with its noise, images, spurs, distortion and ADC in
it. It holds two designs, on the same parts models and the same tests:

- **board**: the chain of [docs/block-diagram.svg](../docs/block-diagram.svg)
  and the notes on `spectre.kicad_sch`;
- **proposal**: a two-band alternative, [block_diagram.svg](block_diagram.svg).

```bash
pip install numpy scipy scikit-rf matplotlib
python sim/run.py                      # the board: every case, 2.5 minutes
python sim/run.py --design proposal    # the proposal
python sim/run.py compare              # one against the other
python -m pytest sim/test_sasim.py
```

`run.py` writes `out/report.md` and its figures. The reports as they stand
are [results/board/report.md](results/board/report.md) and
[results/proposal/report.md](results/proposal/report.md).

## The board's chain, as simulated

```
in - termination switch - buffer (or bypass) - BDA4601 - 20 dB - switch -+- low-pass - MIX1 - 6 dB -
                                                                         |  band-pass - MIX2 - 6 dB - 2-18 MHz - 20 dB - attenuator - 2-16 MHz -+
                                                                         +----------------------- direct-sample path ---------------------------+
- switch - ADC driver - 18 MHz low-pass - SD9609-40 (10 bit, 40 MSPS)
```

The repository's three descriptions of the board do not agree, and the
simulation follows the newest, the schematic's notes:

| | first IF | first LO | input low-pass | second LO | synthesizers |
|---|---|---|---|---|---|
| `docs/block-diagram.drawio` | 3.2 GHz | 3.3-5.5 GHz | 2.3-2.5 GHz | "3.29" | LMX2582 (three boxes, one unconnected) |
| `docs/block-diagram.svg` | 3.2 GHz | 3.3-6.4 GHz | 3.4 GHz | "3.29" | LMX2572 and LMX2581E |
| `spectre.kicad_sch` notes, `lo.kicad_sch` | 3.4 GHz | 3400 MHz (there "LO2") | - | 3388 MHz (there "LO1") | LMX2572, both |
| simulated | 3.4 GHz | 3.4-6.4 GHz | 3.4 GHz | 3388 MHz | LMX2572, both |

So: DC to 3 GHz, a 3.4 GHz first IF, a 12 MHz second IF, a direct-sample
path under 15 MHz. Only the attenuator, the mixers, the synthesizers and the
ADC are named in the drawing. Everything else is a stand-in, listed under
"Where the numbers come from".

## What the simulation finds

|  | board, as drawn | proposal, preamp bypassed | proposal, preamp in |
|---|---|---|---|
| highest frequency | 3.00 GHz | 5.49 GHz | 5.49 GHz |
| noise figure of the chain alone, dB | 7.3 | 21.1 | 8.0 |
| noise figure with the image and the ADC, dB | 20.7 | 24.4 | 11.0 |
| noise floor, dBm/Hz | -153.3 | -149.6 | -163.0 |
| chain noise at the ADC, LSB rms (0.5 or more dithers it) | 0.08 | 1.26 | 3.16 |
| smallest signal seen alone in a 19.6 kHz RBW, dBm | -73 (one LSB) | -107 | -120 |
| IIP3, dBm | -7.0 | +9.1 | -11.9 |
| ADC full scale at the input, dBm | -19.2 | -16.3 | -37.4 |
| level at the first mixer when the ADC is at full scale, dBm | -2.5 | -24.1 | -24.1 |
| largest input that keeps the first mixer at -25 dBm (most attenuation), dBm | -10.2 | +14.5 | -6.6 |
| largest input before the ADC clips or the mixer compresses, dBm | +12.3 | +15.4 | -5.7 |
| a signal on the first IF reads this many dB down | 33 | 85 | 89 |
| two -30 dBm signals at 3.90 and 4.95 GHz make, at 1050 MHz, dBm | -97 | nothing | nothing |

At 1 GHz with the input attenuator at 0 dB, except the two largest-input
rows. From [results/board/report.md](results/board/report.md).

On the board's chain:

- **The ADC is not dithered.** The chain puts 0.08 LSB rms of noise on the
  10 bit converter, where half an LSB is the least that works. With nothing
  larger in the IF band it rests on one code: the 7 dB noise figure of the
  front end is never seen, a signal alone has to reach about -73 dBm to move
  it, and a signal a few LSB in size comes with its harmonics (a 3.3 MHz
  signal at -45 dBm shows its ninth and tenth, 28 dB under it). About 16 dB
  more gain ahead of the ADC cures it.
- **The gain is on the wrong side of the first mixer.** 17 dB ahead of it and
  12 dB after: when the ADC is at full scale the mixer has -2.5 dBm on it,
  where a level 7 mixer is clean to about -25 dBm. IIP3 is -7 dBm, and
  with the attenuator at its 31.5 dB the mixer is past -25 dBm for any input
  over -10 dBm.
- **The input low-pass does not stop the first IF.** A filter that passes
  3 GHz is 2 dB down at 3.4 GHz, so a signal there reads 33 dB down at every
  tuning (the mixer's isolation and nothing else). The first IF has to sit
  well above the low-pass's stop band, or the range has to end lower.
- **The 20 dB amplifier is ahead of that low-pass**, so it sees everything
  to 6 GHz: two -30 dBm signals at 3.90 and 4.95 GHz make a product at
  1050 MHz, -97 dBm referred to the input.
- **Nothing rejects the second mixer's image.** A signal reads again, at full
  level, about 24 MHz below itself. Capturing each step twice with the
  second LO on either side removes it in software, which needs that LO to
  move (3388 and 3402 MHz here) and does not work on bursting signals.
- **The direct-sample path** has the 18 MHz low-pass and nothing else in
  front of the ADC: a 27.2 MHz signal folds to 12.8 MHz, 43 dB down.
- **The printed 3.4 GHz band-pass passes again at 6.4 GHz** (-4 dB, EM),
  which is the top of the first LO's range.

On the proposal (its own report has the detail): 24 dB noise figure with the
preamps bypassed and 11 dB with them in; IIP3 +9 dBm; the image removed to
-73 dBc by two captures; a signal on the first IF 85 dB down; nothing over
the floor with the input terminated.

## How it is modelled

| part of the chain | how | file |
|---|---|---|
| input to the second mixer's output | the signal as a list of tones; every stage adds the products its intercepts, isolations and spur table give (every `n LO +/- m f`, LO leakage, harmonics, two- and three-tone products), with compression | `sasim/rf.py` |
| noise | a density against frequency, taken through the same stages: thermal noise, noise figures, both sidebands and the LO's odd harmonics at each mixer, and the LOs' phase noise as a skirt on every strong product | `sasim/rf.py` |
| second mixer's output to the ADC | a waveform at 320 MS/s: the IF amplifiers' gain, noise and distortion (a cubic applied to the waveform), the anti-alias filter, aperture jitter, the ADC's noise, INL and clipping | `sasim/backend.py` |
| the instrument | tuning, capture, FFT, amplitude calibration, sweep, image rejection, the budget | `sasim/analyzer.py` |

`Analyzer.explain(signals, f)` names what makes the reading at a frequency.

## Where the numbers come from

`run.py` prints this for every part.

| | source |
|---|---|
| printed filters (IF band-pass, two low-passes, two preselectors) | S-parameters from an EM simulation: synthesised by `dfsynth`, corrected against and solved by `mom25d` (both in [kicad2ems](https://github.com/lowprocess/kicad2ems)), 0.05 to 10-16 GHz (`make_filters.sh`; layouts in `filters/`, files in `data/`) |
| LMX2582 | TI datasheet SNAS680E: the open-loop VCO table, PLL noise floor and flicker, output power, harmonics, phase-detector spur. The model reproduces the datasheet's 900 MHz and 1.8 GHz rows to 0.6 dB from 10 kHz to 1 MHz |
| PE43711, PE42540 | pSemi datasheets: insertion loss and isolation by band, IIP3, compression |
| LMH6629, THS4541, ADC12040 | TI datasheets: noise, HD2 and HD3 at 10 MHz, SNR, INL, DNL, aperture jitter |
| TRF37D73 | TI datasheet: gain by frequency; noise figure, OIP3 and compression at 2 GHz. Its OIP2 is assumed |
| SIM-83+ | conversion loss, isolations and IP3 are datasheet typical values, read from search results (the datasheet could not be fetched). **Its spur table, compression point and out-of-band port response are a generic double-balanced mixer's, not this part's** |
| LFCN-2250+, PMA3-83LN+ | datasheet figures read from search results; the LFCN-2250+ is its specification limits (30 dB at 3 to 5 GHz), not its typical curve |
| BDA4601 | insertion loss from a distributor's summary (read from a search result); IIP3 and compression assumed |
| SD9609-40 | taken to be an AD9609-40: SNR 61.5 dBFS and SFDR 75 dBc from a search result; INL, DNL, jitter and full scale assumed. No datasheet was found for the SD part |
| the board's switches, 20 dB amplifier, ADC driver | stand-ins with real datasheets behind them: PE42540, TRF37D73, THS4541 |
| the board's 0 dB buffer, 6 dB and 20 dB IF amplifiers, IF attenuator, IF filters | the figure on the drawing, with assumed noise figure, intercepts and filter order |
| the board's two microwave filters | this folder's printed designs at 3.4 GHz, standing in for whatever the board will carry |

No manufacturer's S-parameter file is used: minicircuits.com refuses scripted
downloads and pSemi's are behind a licence click-through. Put the files in
`vendor/` ([how](vendor/README.md)) and the simulation uses them.

## Limits

- The board's chain is modelled from a block diagram: its conclusions about
  gain distribution, dither, the first IF and the image hold for any parts
  of those gains; its absolute noise and distortion figures move with the
  parts chosen.
- Stages are cascaded by |S21| in 50 ohm. Mismatch between stages (a mixer
  port against a filter, with no pad or diplexer between) is not modelled.
- The spur levels of both mixers rest on a generic table. Measure the
  SIM-83+ and replace `Mixer.spur` before trusting a spur prediction to
  better than 10 dB.
- A noise-like signal makes no distortion products and loads nothing.
- In the direct-sample path, signals above 160 MHz are taken as removed by
  the 18 MHz low-pass; a real LC filter leaks at those frequencies.
- No LO pulling between the two synthesizers, no coupling through the board
  or the supplies.
