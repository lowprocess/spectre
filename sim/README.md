# The analyzer's signal chain, simulated

A behavioural simulation of this spectrum analyzer: what it reads for a given
set of input signals, with its noise, images, spurs, distortion and ADC in
it. It holds two designs, on the same part models and the same tests:

- **proposal**: 0.1 MHz to 6.4 GHz, a low band to 3 GHz and a high band to
  6.4 GHz, with the board's own LMX2572, SIM-83+ and 10 bit ADC;
- **board**: the chain of [docs/block-diagram.svg](../docs/block-diagram.svg)
  and the notes on `spectre.kicad_sch`, as it stands.

```bash
pip install numpy scipy scikit-rf matplotlib
python sim/run.py --design proposal    # the proposal: every case, 2.5 minutes
python sim/run.py                      # the board's chain
python sim/run.py compare              # one against the other
python -m pytest sim/test_sasim.py
```

`run.py` writes `out/report.md` and its figures. The reports as they stand
are [results/proposal/report.md](results/proposal/report.md) and
[results/board/report.md](results/board/report.md).

## The proposal

![Block diagram: a step attenuator and a four-way band switch; the low band
in two filtered halves through the first mixer to a 3.4 GHz first IF; the
high band in two preselected halves straight into the second mixer; a direct
path under 15 MHz; a 12 MHz second IF, a 10 bit 40 MSPS ADC and an
RP2350](block_diagram.svg)

`make_block_diagram.py` draws it.

| band | range | path | LO1 | LO2 |
|---|---|---|---|---|
| direct | 0.1 to 15 MHz | attenuator, 30 MHz low-pass, IF chain: no mixer | off | off |
| L1 | 15 MHz to 2.29 GHz | 2x LFCN-2250+, then up to the 3.4 GHz first IF and down to 12 MHz | f + 3.4 GHz | 3.388 GHz (3.402 on the second capture) |
| L2 | 2.29 to 3.0 GHz | the same, behind a 2.3-3.0 GHz band-pass | f + 3.4 GHz, to 6.4 GHz | the same |
| H1 | 3.0 to 4.4 GHz | band-pass and low-pass, straight into the second mixer | off | f + 12 MHz, then f - 12 MHz |
| H2 | 4.4 to 6.4 GHz | the same | off | the same |

What sets its shape:

- **6.4 GHz is the LMX2572's top.** With the first LO at f + IF1 and the
  first IF above the band, 3.0 GHz + 3.4 GHz is all of it: the low band
  cannot end higher, and the first IF cannot sit further from it.
- **The low band is split at 2.29 GHz** because no low-pass passes 3.0 GHz
  and stops 3.3 GHz. A band-pass over the top 700 MHz does (its upper
  skirt is much steeper than a low-pass's), and under 2.29 GHz the two
  LFCN-2250+ do it with room to spare.
- **The high band is split at 4.4 GHz** so that each half is under an
  octave: a signal at twice the LO, and one at half the tuned frequency, are
  then outside the half's own preselector.
- **No gain ahead of a mixer that cannot be switched out.** Each band has a
  preamp after its first filter, between two switches. The gain that dithers
  the 10 bit ADC is in the IF, and the IF attenuator trims it per band
  (3 dB low, 0 dB high; 14 and 9 dB with the preamps in) to keep the noise
  at the ADC near 0.8 LSB rms.
- **The second IF is 12 MHz, not a quarter of the sampling rate.** At 10 MHz
  the image in one capture and the alias in the other land on the same
  frequency; at 12 MHz they do not.
- **Changed from the board's drawing:** a PE43704 attenuator (the BDA4601
  ends at 4 GHz); no fixed 20 dB amplifier and no 0 dB buffer ahead of the
  mixer; no termination switch (the attenuator at 31.75 dB is the
  termination for a noise-floor reading).

### Recommended filters

All printed filters are on 0.508 mm RO4003C, synthesised by `dfsynth` and
solved by `mom25d` ([kicad2ems](https://github.com/lowprocess/kicad2ems));
their layouts are in `filters/`, their S-parameters in `data/`, and
`make_filters.sh` makes them again. The figures are the EM result.

| where | filter | pass band | what it has to stop, and does |
|---|---|---|---|
| L1 input | 2x Mini-Circuits LFCN-2250+ (LTCC low-pass) | to 2.29 GHz, about 1 dB each at the top | the first IF: 60 dB at 3.3-3.5 GHz (datasheet limits) |
| L2 input | printed interdigital band-pass, N=7, 2.25-3.03 GHz, 20 x 22 mm | 2.29-3.0 GHz, 1 to 3 dB with 1 dB of ripple | the first IF: 39 / 45 / 50 dB at 3.31 / 3.4 / 3.5 GHz. Passes again at 8 GHz (-8 dB) |
| low band, after either | printed radial-stub low-pass, N=7, 4.0 GHz | to 3.45 GHz, 0.2 dB | the first mixer's image at f + 6.8 GHz and the band-pass's 8 GHz: 44 / 51 / 57 dB at 7 / 8 / 9 GHz |
| after the IF1 amplifier | the same 4.0 GHz low-pass | 3.4 GHz, 0.2 dB | the band-pass's second pass band: 38 dB at 6.4 GHz |
| first IF | printed hairpin band-pass, N=5, 3.4 GHz, 190 MHz wide, 36 x 21 mm | 3.31-3.50 GHz, 2.2 dB | 38 dB at 3.2 GHz, 31 dB at 3.6 GHz. Passes again at 6.4 GHz (-4 dB), where the first LO ends: hence the low-pass before it |
| H1 input | printed stub band-pass, N=5, 2.9-4.5 GHz, then a radial-stub low-pass, N=7, 5.0 GHz | 3.0-4.4 GHz, 0.4 to 1 dB together | twice the LO (6.2-8.8 GHz): 31 dB and more; half the frequency: 21 / 32 / 41 dB at 2.5 / 2.25 / 2.0 GHz. The band-pass alone passes again at 7 GHz |
| H2 input | printed stub band-pass, N=5, 4.3-6.4 GHz, then a radial-stub low-pass, N=7, 7.0 GHz | 4.4-6.4 GHz, 0.6 to 2 dB together | twice the LO (8.8-12.8 GHz): 22 / 34 / 40 dB at 8.6 / 10 / 11 GHz; half the frequency: 28 / 37 / 42 dB at 3.5 / 3.2 / 3.0 GHz. The band-pass alone passes 8.6-11 GHz |
| direct path | LC low-pass, 3rd order, 30 MHz | to 15 MHz | keeps the rest of the spectrum off the first IF amplifier |
| second mixer's IF port | LC diplexer, 30 MHz | to 17 MHz | ends the mixer in 50 ohm at its sum products |
| ahead of the ADC | LC elliptic low-pass, 9th order, 17.5 MHz, 0.1 dB ripple | 7-17 MHz | the aliases of the kept band, from 23 MHz: 70 dB from 21.5 MHz. A 7th order's stop band starts at 25.5 MHz and leaves 41 dB at 23 |

The two LC filters and the diplexer are ideal prototypes in the simulation.
The interdigital band-pass is the one that needs work: mom25d's tuning left
it with 1 dB of ripple and a 5 dB return loss in band.

### What it gives up

From [results/proposal/report.md](results/proposal/report.md).

- **Noise figure 22 to 26 dB with the preamps bypassed** (-152 to -148
  dBm/Hz), 11 to 15 dB with them in. The board's front end is 7 dB, but its
  ADC never sees it.
- **The second mixer's image is removed in software only.** Every signal
  reads again about 24 MHz below itself in one capture. Two captures per
  step take it into the noise (more than 70 dB on a 0 dBm signal), at twice
  the sweep time. A signal on for 35 % of the captures is then shown over 16 %
  of its band, and noise reads 3 dB low.
- **The top 20 MHz has no image rejection.** Above 6.38 GHz the second LO
  can only sit below the signal, so both captures are the same one.
- **L2, 2.29 to 3.0 GHz, is the weak part of the low band.** A signal on the
  first IF (3.31-3.50 GHz, which is 5G band n78 in many places) reads 66 dB
  down there in one capture, against more than 78 dB in L1; and the
  band-pass has the loss and ripple above.
- **The 10 bit ADC sets the range of one capture.** Its own distortion is
  what is left of a two-tone test at 10 dB of attenuation and more
  (-62 to -69 dBc), and it clips at +5 dBm in with all the input
  attenuation; more IF attenuation takes that to +15 dBm, where the mixer
  ends it, but undithers the ADC.
- **Twice-the-LO responses in the high band are 68 to 80 dB down**, on the
  filters above and an assumed 35 dB of mixer balance.
- **Under 40 MHz** the second capture moves the second LO 4 MHz and does not
  change sides, and the first LO's leak leaves about -79 dBm at 20-30 MHz in
  one capture.
- **Phase noise** is -62 dBc in a 19.6 kHz RBW at 100 kHz from a carrier
  (LMX2572, integer-N from 10 and 2 MHz phase detectors).
- **Nine microwave switches and eight printed filters**: more board than the
  drawing's.

## The proposal against the board's chain

|  | board, as drawn | proposal, preamp bypassed | proposal, preamp in |
|---|---|---|---|
| highest frequency | 3.00 GHz | 6.40 GHz | 6.40 GHz |
| noise figure of the chain alone, dB | 7.3 | 20.1 | 8.6 |
| noise figure with the image and the ADC, dB | 20.7 | 22.5 | 12.0 |
| noise floor, dBm/Hz | -153.3 | -151.5 | -162.0 |
| chain noise at the ADC, LSB rms (0.5 or more dithers it) | 0.08 | 0.83 | 0.78 |
| smallest signal seen alone in a 19.6 kHz RBW, dBm | -73 (one LSB) | -109 | -119 |
| IIP3, dBm | -7.0 | +4.7 | -9.3 |
| ADC full scale at the input, dBm | -19.2 | -26.5 | -36.6 |
| level at the first mixer when the ADC is at full scale, dBm | -2.5 | -35.1 | -24.1 |
| largest input that keeps the first mixer at -25 dBm (most attenuation), dBm | -10.2 | +15.3 | -5.7 |
| largest input before the ADC clips or the mixer compresses, dBm | +12.3 | +5.2 | -4.8 |
| a signal on the first IF reads this many dB down | 33 | 86 | 90 |
| two -30 dBm signals at 3.90 and 4.95 GHz make, at 1050 MHz, dBm | -97 | nothing | nothing |

At 1 GHz with the input attenuator at 0 dB, except the two largest-input
rows. From [results/board/report.md](results/board/report.md).

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
| printed filters | S-parameters from an EM simulation: synthesised by `dfsynth`, corrected against and solved by `mom25d` (both in [kicad2ems](https://github.com/lowprocess/kicad2ems)), 0.05 to 10-18 GHz (`make_filters.sh`; layouts in `filters/`, files in `data/`) |
| LMX2572 | TI datasheet: -106 dBc/Hz at 100 kHz from 6.4 GHz and the PLL figure of merit. The shape of its VCO profile is the LMX2582's (whose datasheet table the model reproduces to 0.6 dB), moved to that figure |
| PE43704, PE43711, PE42540 | pSemi datasheets: insertion loss and isolation by band, IIP3, compression |
| TRF37D73, LMH6629, THS4541 | TI datasheets: gain by frequency, noise, HD2 and HD3 at 10 MHz, compression. The TRF37D73's OIP2 is assumed |
| SIM-83+ | conversion loss, isolations and IP3 are datasheet typical values, read from search results (the datasheet could not be fetched). **Its spur table, compression point and out-of-band port response are a generic double-balanced mixer's, not this part's** |
| LFCN-2250+, PMA3-83LN+ | datasheet figures read from search results; the LFCN-2250+ is its specification limits (30 dB at 3 to 5 GHz), not its typical curve |
| SD9609-40 | taken to be an AD9609-40: SNR 61.5 dBFS and SFDR 75 dBc from a search result; INL, DNL, jitter and full scale assumed. No datasheet was found for the SD part |
| BDA4601 (board) | insertion loss from a distributor's summary (read from a search result); IIP3 and compression assumed |
| the board's switches, 20 dB amplifier, ADC driver | stand-ins with real datasheets behind them: PE42540, TRF37D73, THS4541 |
| the board's 0 dB buffer, 6 dB and 20 dB IF amplifiers, IF attenuator, IF filters | the figure on the drawing, with assumed noise figure, intercepts and filter order |
| the board's two microwave filters | this folder's printed designs at 3.4 GHz, standing in for whatever the board will carry |

No manufacturer's S-parameter file is used: minicircuits.com refuses scripted
downloads and pSemi's are behind a licence click-through. Put the files in
`vendor/` ([how](vendor/README.md)) and the simulation uses them.

## Limits

- Stages are cascaded by |S21| in 50 ohm. Mismatch between stages (a mixer
  port against a filter, two reflective filters in a row) is not modelled;
  the pads and the diplexer are there for it.
- The spur levels of both mixers rest on a generic table. Measure the
  SIM-83+ and replace `Mixer.spur` before trusting a spur prediction to
  better than 10 dB.
- The board's chain is modelled from a block diagram: its conclusions about
  gain distribution, dither, the first IF and the image hold for any parts
  of those gains; its absolute noise and distortion figures move with the
  parts chosen.
- mom25d's results are 2.5D: no enclosure, no radiation between filters.
  The printed filters past 10 GHz are at the edge of what that is good for.
- A noise-like signal makes no distortion products and loads nothing.
- In the direct-sample path, signals above 160 MHz are taken as removed by
  the low-pass filters; a real LC filter leaks at those frequencies.
- No LO pulling between the two synthesizers, no coupling through the board
  or the supplies, no leakage between the bands' paths beyond the one
  modelled (the high band's, into the second mixer).
