"""
The analyzer: its signal paths built from the parts, its tuning (where each
LO sits for a wanted input frequency), one capture (4096 ADC samples, an FFT,
and the bins mapped back to input frequency and input power), and a sweep of
captures.

Two designs, built by Analyzer._build_proposal and Analyzer._build_board:
their docstrings draw each chain.  A band is one of three kinds:

    superhet  up-conversion in the first mixer to the first IF (LO1 = f +
              IF1), the IF band-pass, the second mixer down to the second IF
    direct    straight into the second mixer, LO2 the second IF away
    sample    no mixer: the ADC samples the input

Image rejection in software: every step can be captured twice, the second
time with the second LO on the other side of the signal (and, in a superhet
band, both LOs moved 10 MHz), and the lower of the two readings kept.  A real
response reads the same both times; an image, and most spurs, do not.
"""

import os
from dataclasses import dataclass

import numpy as np

from . import backend, parts
from .lo import lmx2572, lmx2582
from .parts import GHZ, MHZ
from .rf import KT0, Chain, Lin, Mix, Mixer, State, Tones, dbm, mw


@dataclass
class Signal:
    """A carrier (bw = 0), or a noise-like signal of bandwidth bw (a flat
    density over it: an OFDM or spread-spectrum signal as an analyzer sees
    it).  The noise-like kind goes through the chain as noise does: every
    conversion, image and filter acts on it, but it makes no distortion
    products and does not compress anything, so keep it small."""
    f: float                 # Hz (the centre, when it has a bandwidth)
    dbm: float               # total power
    bw: float = 0.0          # Hz
    duty: float = 1.0        # the chance it is on during a capture
    name: str = ""

    def label(self):
        return self.name or "%.6g MHz" % (self.f / MHZ)


def passband_centre(part, lo=2.5 * GHZ, hi=4.0 * GHZ):
    f = np.arange(lo, hi, 1 * MHZ)
    g = part.g(f)
    inside = f[g > g.max() - 3.0]
    return 0.5 * (inside[0] + inside[-1])


class Analyzer:
    """design: 'board', the chain of the repository's docs/block-diagram and
    schematic notes, or 'proposal', the 6.4 GHz chain of block_diagram.svg.

    What `preamp` switches in differs: the board's input buffer (its 20 dB
    amplifier after the attenuator is always in circuit, unless
    fixed_lna=False takes it out to show what it costs); the proposal's
    preamp in each band."""
    step = 10 * MHZ          # one capture's share of the span

    def __init__(self, design="board", lo1=None, lo2=None, att_db=10.0,
                 if_att_db=None, preamp=False, nfft=4096, seed=1,
                 mixer1=None, mixer2=None, adc=None,
                 lna_powered_in_band_a=False, pad1_db=3.0, pad2_db=6.0,
                 fixed_lna=True):
        if design not in ("board", "proposal"):
            raise ValueError("design: 'board' or 'proposal'")
        self.design = design
        board = design == "board"
        # both LOs are LMX2572 (lo.kicad_sch); the second sits 12 MHz from
        # the first IF or the signal, which a 2 MHz phase detector reaches
        self.lo1 = lo1 or lmx2572()
        self.lo2 = lo2 or lmx2572(fpd=2e6)
        self.att_db, self.preamp = att_db, preamp
        # None: the board's 0 dB, the proposal's own trim for each band
        self.if_att_db = if_att_db if if_att_db is not None else (
            0.0 if board else None)
        self.nfft, self.seed = nfft, seed
        self.mx1 = mixer1 or Mixer()
        self.mx2 = mixer2 or Mixer()
        self.adc = adc or parts.adc_sd9609_40()
        self.lna_powered_in_band_a = lna_powered_in_band_a
        self.pad1_db, self.pad2_db = pad1_db, pad2_db
        self.fixed_lna = fixed_lna
        if board:
            self._build_board()
        else:
            self._build_proposal()
        self.adc_model = backend.AdcModel(self.adc, self.fs_node_dbm)

    def like(self, **kw):
        """This analyzer with some settings changed."""
        d = dict(design=self.design, lo1=self.lo1, lo2=self.lo2,
                 att_db=self.att_db, if_att_db=self.if_att_db,
                 preamp=self.preamp, nfft=self.nfft, seed=self.seed,
                 mixer1=self.mx1, mixer2=self.mx2, adc=self.adc,
                 lna_powered_in_band_a=self.lna_powered_in_band_a,
                 pad1_db=self.pad1_db,
                 pad2_db=self.pad2_db, fixed_lna=self.fixed_lna)
        d.update(kw)
        return Analyzer(**d)

    # ------------------------------------------------------------ the designs

    def _build_board(self):
        """docs/block-diagram and the notes on spectre.kicad_sch: DC to
        3 GHz, a 3.4 GHz first IF, a 12 MHz second IF, a direct-sample path.

            in - termination switch - buffer (or bypass) - BDA4601 - 20 dB -
            switch -+- low-pass - MIX1 - 6 dB - band-pass - MIX2 - 6 dB -
                    |    2-18 MHz - 20 dB - attenuator - 2-16 MHz -+
                    +----------- the direct-sample path -----------+- switch
            - ADC driver - 18 MHz low-pass - ADC

        The drawing names the attenuator, the mixers, the synthesizers and
        the ADC.  Everything else is a stand-in, and says so in its source:
        the switches are PE42540, the 20 dB amplifier a TRF37D73, the two
        printed filters are this folder's, and the amplifiers and IF filters
        it gives only a figure for are that figure with assumed noise and
        linearity."""
        P = parts
        self.if2 = 12 * MHZ
        self.if1_bpf = P.em_filter(
            "IF1 band-pass (hairpin N=5)", "if1_bpf_3g4_hairpin.s2p",
            "3.4 GHz, 180 MHz, RO4003C 0.508 mm: a stand-in for the board's")
        self.in_lpf = P.em_filter(
            "input low-pass (radial stub N=7)", "in_lpf_3g4_radial.s2p",
            "3.4 GHz, RO4003C 0.508 mm: a stand-in for the board's")
        self.if1 = round(passband_centre(self.if1_bpf) / self.step) * self.step
        self.a_top = min(3.0 * GHZ, np.floor(
            (self.lo1.fmax - self.if1) / self.step) * self.step)
        self.top = self.a_top
        self.kinds = {"D": "sample", "S": "superhet"}

        def sw(name):
            return Lin(P.pe42540("on", "%s (stand-in: PE42540)" % name))

        buf = [sw("buffer switch (in)")] + ([Lin(P.gain_block(
            "input buffer (0 dB)", 0.0, 8.0, 30.0, 15.0, oip2=50.0))]
            if self.preamp else []) + [sw("buffer switch (out)")]
        lna = ([Lin(P.trf37d73("20 dB amp (stand-in: TRF37D73)"))]
               if self.fixed_lna else [])
        front = ([sw("termination switch")] + buf
                 + [Lin(P.bda4601(self.att_db, "BDA4601"))] + lna
                 + [sw("direct-sample switch")])
        if2_out = (0.0, backend.OSR * self.adc.fs / 2)
        s = front + [
            Lin(self.in_lpf),
            Mix(self.mx1, "lo1", "up", out=(0.2 * GHZ, 14 * GHZ)),
            Lin(P.gain_block("IF1 amp (6 dB)", 6.0, 4.0, 30.0, 15.0,
                             oip2=50.0)),
            Lin(self.if1_bpf),
            Mix(self.mx2, "lo2", "down", out=if2_out)]
        self.chains = {"S": Chain("S", s),
                       "D": Chain("D", front, out=if2_out)}
        tail = [P.pe42540("on", "ADC select switch (stand-in: PE42540)"),
                P.ths4541("ADC driver (0 dB; stand-in: THS4541)", 0.0),
                P.antialias(18 * MHZ)]
        self.if_chain = {
            "S": [P.gain_block("IF2 amp (6 dB)", 6.0, 4.0, 35.0, 16.0,
                               oip2=70.0, fmax=200 * MHZ),
                  P.lc_bandpass(2 * MHZ, 18 * MHZ),
                  P.gain_block("IF2 amp (20 dB)", 20.0, 4.0, 40.0, 16.0,
                               oip2=74.0, fmax=200 * MHZ),
                  P.if_attenuator(self.if_att_db),
                  P.lc_bandpass(2 * MHZ, 16 * MHZ)] + tail,
            "D": tail}
        # the ADC's 2 Vpp differential full scale, in 50 ohm terms
        self.fs_node_dbm = self.adc.fs_dbm_at_driver_input

    def _build_proposal(self):
        """block_diagram.svg: 0.1 MHz to 6.4 GHz with two LMX2572, two
        SIM-83+ and the board's 10 bit ADC.

            low band   L1 to 2.29 GHz, L2 to 3.0 GHz: each its own input
                       filter, then the first mixer up to a 3.4 GHz first IF
                       (LO1 = f + 3.4 GHz, to 6.4 GHz) and the second down
                       to 12 MHz
            high band  H1 to 4.4 GHz, H2 to 6.4 GHz: a preselector each,
                       straight into the second mixer, LO2 12 MHz away
            direct     under 15 MHz, into the IF chain with no mixer

        No gain ahead of a mixer that cannot be switched out, a preamp
        after each band's first filter, and IF gain enough to dither the
        ADC in every band (the IF attenuator trims it per band)."""
        P = parts
        self.if2 = 12 * MHZ

        def em(name, file, what):
            return P.em_filter(name, file, what + ", RO4003C 0.508 mm")
        self.if1_bpf = em("IF1 band-pass (hairpin N=5)",
                          "if1_bpf_3g4_hairpin.s2p", "3.4 GHz, 180 MHz")
        self.if1 = round(passband_centre(self.if1_bpf) / self.step) * self.step
        self.l_split = 2.29 * GHZ
        self.a_top = min(3.0 * GHZ, np.floor(
            (self.lo1.fmax - self.if1) / self.step) * self.step)
        self.h_split = 4.4 * GHZ
        # the second LO can sit below a signal up to its own top, and on
        # both sides of it (which the image rejection needs) to if2 less
        self.top = np.floor(self.lo2.fmax / self.step) * self.step
        self.two_sided_top = self.lo2.fmax - self.if2
        self.kinds = {"D": "sample", "L1": "superhet", "L2": "superhet",
                      "H1": "direct", "H2": "direct"}

        def sw(name):
            return Lin(P.pe42540("on", name))

        def preamp(band, lna):
            """A preamp between two switches: through it, or past it."""
            return ([sw("%s preamp switch (in)" % band)]
                    + ([Lin(lna)] if lna is not None else [])
                    + [sw("%s preamp switch (out)" % band)])

        on = self.preamp
        pre_l = preamp("low band", P.trf37d73("low band preamp TRF37D73")
                       if on else None)
        pre_h = preamp("high band", P.pma3_83ln("high band preamp PMA3-83LN+")
                       if on else None)
        # the high band's preamp while the low band is selected: switched
        # in and powered down, for the isolation that adds
        pre_h_idle = preamp("high band", P.pma3_83ln(
            "high band preamp PMA3-83LN+") if self.lna_powered_in_band_a
            else P.amplifier_off("high band preamp (unpowered)"))
        if2_out = (0.0, backend.OSR * self.adc.fs / 2)
        front = [Lin(P.dc_block_limiter()),
                 Lin(P.pe43704(self.att_db, "input PE43704"))]

        low_in = {
            "L1": [Lin(P.lfcn2250()), Lin(P.lfcn2250())],
            "L2": [Lin(em("L2 band-pass 2.3-3.0 GHz (interdigital N=7)",
                          "l2_bpf_2g3_3g0_interdigital.s2p",
                          "2.25-3.05 GHz"))]}
        high_in = {
            "H1": [Lin(em("H1 band-pass 3.0-4.5 GHz (stub N=5)",
                          "h1_bpf_3g0_4g5_stub.s2p", "2.95-4.55 GHz")),
                   Lin(em("H1 low-pass 5.0 GHz (radial stub N=7)",
                          "h1_lpf_5g0_radial.s2p", "5.0 GHz"))],
            "H2": [Lin(em("H2 band-pass 4.3-6.4 GHz (stub N=5)",
                          "h2_bpf_4g3_6g4_stub.s2p", "4.25-6.45 GHz")),
                   Lin(em("H2 low-pass 7.0 GHz (radial stub N=7)",
                          "h2_lpf_7g0_radial.s2p", "7.0 GHz"))]}
        low_tail = (
            [sw("SW2 (L1/L2)"),
             Lin(em("low band low-pass 4.0 GHz (radial stub N=7)",
                    "if1_lpf_4g0_radial.s2p", "4.0 GHz"))]
            + pre_l
            + [Lin(P.pad(self.pad1_db, "%g dB pad (mixer 1 IF port)"
                         % self.pad1_db)),
               Mix(self.mx1, "lo1", "up", out=(0.2 * GHZ, 14 * GHZ)),
               Lin(P.pma3_83ln("IF1 amp PMA3-83LN+")),
               Lin(P.pad(self.pad2_db, "%g dB pad (after the IF1 amp)"
                         % self.pad2_db)),
               Lin(em("IF1 low-pass 4.0 GHz (radial stub N=7)",
                      "if1_lpf_4g0_radial.s2p", "4.0 GHz")),
               Lin(self.if1_bpf),
               sw("SW5 (mixer 2 select)"),
               Mix(self.mx2, "lo2", "down", out=if2_out)])
        leak = ([Lin(P.pe42540("off", "SW1")), sw("SW3 (H1/H2)")]
                + high_in["H2"] + [sw("SW4 (H1/H2)")] + pre_h_idle
                + [Lin(P.pe42540("off", "SW5"))])
        self.chains = {}
        for b in ("L1", "L2"):
            main = (front + [sw("SW1 (band select)")] + low_in[b]
                    + low_tail)
            self.chains[b] = Chain(b, main, leak, fork=2, join=len(main) - 1)
        for b in ("H1", "H2"):
            self.chains[b] = Chain(b, (
                front + [sw("SW1 (band select)"), sw("SW3 (H1/H2)")]
                + high_in[b] + [sw("SW4 (H1/H2)")] + pre_h
                + [sw("SW5 (mixer 2 select)"),
                   Mix(self.mx2, "lo2", "down", out=if2_out)]))
        self.chains["D"] = Chain("D", front + [
            sw("SW1 (band select)"),
            Lin(P.diplexer_lp(30 * MHZ, "direct-sample low-pass (30 MHz)"))],
            out=if2_out)

        # the IF attenuator trims the gain so that each band's noise is
        # just under an LSB rms at the ADC: enough to dither it, and no
        # more of its range spent on noise than that takes.  A preamp
        # brings its own gain, which the attenuator takes back out
        lo, hi = (14.0, 9.0) if on else (3.0, 0.0)
        trim = {"L1": lo, "L2": lo, "H1": hi, "H2": hi, "D": 0.0}
        self.if_trim = trim
        self.if_chain = {}
        for b in self.chains:
            att = self.if_att_db if self.if_att_db is not None else trim[b]
            tail = [P.pe42540("on", "SW6 (IF select)"),
                    P.lmh6629(26.0, "LMH6629 #1 (26 dB)"),
                    P.pe43711(att, "IF PE43711"),
                    # ninth order: 70 dB from 21.5 MHz, where the first
                    # alias of the kept 7-17 MHz starts at 23 (a seventh
                    # order's stop band starts at 25.5)
                    P.antialias(17.5 * MHZ, order=9),
                    P.lmh6629(26.0, "LMH6629 #2 (26 dB)"),
                    P.ths4541()]
            self.if_chain[b] = (tail if b == "D" else
                                [P.diplexer_lp()] + tail)
        self.fs_node_dbm = (self.adc.fs_dbm_at_driver_input
                            + float(tail[-1].g(self.if2)))

    def all_parts(self):
        out = []
        for c in self.chains.values():
            for s in c.main + c.leak:
                out.append(s.part if isinstance(s, Lin) else s.mx)
        for ps in self.if_chain.values():
            out += ps
        return out + [self.lo1, self.lo2, self.adc]

    # ---------------------------------------------------------------- tuning

    def band(self, fc):
        if self.design == "board":
            if fc <= self.step:
                return "D"
            if fc <= self.a_top:
                return "S"
            raise ValueError("%.4f GHz is above the board's %.4f GHz"
                             % (fc / GHZ, self.a_top / GHZ))
        if fc <= self.step:
            return "D"
        if fc <= self.l_split:
            return "L1"
        if fc <= self.a_top:
            return "L2"
        if fc < self.h_split:
            return "H1"
        if fc <= self.top:
            return "H2"
        raise ValueError("%.4f GHz is above the analyzer's %.4f GHz"
                         % (fc / GHZ, self.top / GHZ))

    def tune(self, fc, shifted=False):
        """The LOs for a capture centred on fc, and how an IF bin maps to
        an input frequency: f_in = base + sign * f_if."""
        band = self.band(fc)
        kind = self.kinds[band]
        if kind == "sample":
            # no mixer: an ADC bin is its own input frequency
            lo1 = lo2 = None
            base, sign = 0.0, +1
        elif kind == "superhet":
            if not shifted:
                lo1, lo2 = fc + self.if1, self.if1 - self.if2
                base, sign = lo1 - lo2, -1
            elif fc < 4 * self.step:
                # the two LOs would be fc - if2 apart, and the first LO's
                # leak through the first mixer would land in the IF at
                # full strength: here the second capture keeps its side
                # and moves the second LO 4 MHz, which moves an image 8
                lo1, lo2 = fc + self.if1, self.if1 - self.if2 + 4 * MHZ
                base, sign = lo1 - lo2, -1
            else:
                lo1 = fc + self.if1 - self.step
                lo2 = self.if1 - self.step + self.if2
                base, sign = lo1 - lo2, +1
            self.lo1.check(lo1)
            self.lo2.check(lo2)
        else:
            # (above the second LO's top less the IF, it can only sit
            # below the signal: both captures are then the same one)
            lo1 = None
            below = shifted or fc + self.if2 > self.lo2.fmax
            lo2 = fc - self.if2 if below else fc + self.if2
            base, sign = lo2, (+1 if below else -1)
            self.lo2.check(lo2)
        st = State(lo={"lo1": lo1, "lo2": lo2},
                   synth={"lo1": self.lo1, "lo2": self.lo2})
        return band, st, base, sign

    # --------------------------------------------------------------- capture

    def _rng(self, fc, shifted, sweep=0):
        return np.random.default_rng(
            [self.seed, int(round(fc / 1e3)), int(shifted), sweep])

    def rf(self, signals, fc, shifted=False, rng=None):
        """The second mixer's output for a capture at fc: (band, state,
        base, sign, tones, noise function)."""
        rng = rng or self._rng(fc, shifted)
        band, st, base, sign = self.tune(fc, shifted)
        on = [s for s in signals
              if s.duty >= 1.0 or rng.uniform() < s.duty]
        cw = [s for s in on if s.bw <= 0]
        tin = Tones([s.f for s in cw], [s.dbm for s in cw],
                    [s.label() for s in cw])
        wide = [(s.f - s.bw / 2, s.f + s.bw / 2, mw(s.dbm) / s.bw)
                for s in on if s.bw > 0]

        def psd_in(f):
            f = np.asarray(f, float)
            return sum(d * ((f >= a) & (f <= b)) for a, b, d in wide)
        t, noise = self.chains[band].run(tin, st, psd_in if wide else None)
        return band, st, base, sign, t, noise

    def capture(self, signals, fc, shifted=False, sweep=0):
        """One capture centred on fc: (input frequency of each kept bin,
        the power it reads in dBm at the input connector, details)."""
        rng = self._rng(fc, shifted, sweep)
        band, st, base, sign, t, noise = self.rf(signals, fc, shifted, rng)
        n = backend.OSR * (self.nfft + 2 * backend.GUARD)
        fs = backend.OSR * self.adc.fs
        f = np.fft.rfftfreq(n, 1 / fs)
        # the noise density: every bin under 40 MHz (the skirts are sharp),
        # every sixteenth above (the anti-alias filter removes it anyway)
        fine = f <= 40 * MHZ
        idx = np.unique(np.concatenate([np.flatnonzero(fine),
                                        np.arange(0, f.size, 16),
                                        [f.size - 1]]))
        psd = mw(np.interp(f, f[idx], dbm(noise(f[idx]))))
        x = backend.synthesize(t, psd, n, fs, rng)
        x, load = backend.if_chain(x, self.if_chain[band], fs, rng, f)
        codes, clipped = self.adc_model.convert(x, fs, rng)
        # what the ADC was given, in LSB rms, and whether it answered
        at_adc = float(np.std(x) / self.adc_model.a_fs
                       * 2 ** (self.adc.bits - 1))
        fb, dbfs, enbw = backend.spectrum(codes, self.adc.bits, self.adc.fs)
        fin = base + sign * fb
        keep = (fin >= fc - self.step / 2 - 1) & (fin < fc + self.step / 2 - 1)
        if self.kinds[band] == "sample":
            keep &= fb >= 50e3          # the converter's DC, and its 1/f
        fin, fb, dbfs = fin[keep], fb[keep], dbfs[keep]
        order = np.argsort(fin)
        fin, fb, dbfs = fin[order], fb[order], dbfs[order]
        gain = self.gain_to_adc(band, st, fin, fb)
        info = dict(band=band, lo=st.lo, clipped=clipped, if_load=load,
                    adc_in_lsb=at_adc, stuck=bool(codes.max() == codes.min()),
                    levels=list(st.levels), enbw=enbw, if_tones=t,
                    base=base, sign=sign)
        return fin, dbfs + self.fs_node_dbm - gain, info

    def gain_to_adc(self, band, st, fin, fif):
        """The wanted response's gain, in dB, from the input connector to
        the ADC's input node: what the analyzer's amplitude calibration
        takes out."""
        _, g = self.chains[band].wanted_gain(fin, st)
        return g + sum(p.g(fif) for p in self.if_chain[band])

    # ----------------------------------------------------------------- sweep

    def centres(self, f0, f1):
        k0 = int(np.floor(f0 / self.step + 0.5))
        k1 = int(np.ceil(f1 / self.step - 0.5))
        return [k * self.step for k in range(max(k0, 0), max(k1, k0) + 1)]

    def _step(self, signals, fc, image_reject, sweep=0):
        f, p, info = self.capture(signals, fc, False, sweep)
        clipped = info["clipped"]
        if image_reject and self.kinds[info["band"]] != "sample":
            f2, p2, info2 = self.capture(signals, fc, True, sweep)
            p = np.minimum(p, p2)
            clipped = max(clipped, info2["clipped"])
        return f, p, clipped

    def sweep(self, signals, f0, f1, image_reject=True, workers=None,
              sweep=0):
        """A sweep from f0 to f1: (f, dBm, the worst fraction of clipped ADC
        samples in any capture)."""
        cs = self.centres(f0, f1)
        workers = workers or min(os.cpu_count() or 1, 8)
        if workers > 1 and len(cs) > 3:
            import multiprocessing as mp
            global _JOB
            _JOB = (self, signals, image_reject, sweep)
            with mp.get_context("fork").Pool(workers) as pool:
                res = pool.map(_work, cs, chunksize=1)
        else:
            res = [self._step(signals, fc, image_reject, sweep) for fc in cs]
        f = np.concatenate([r[0] for r in res])
        p = np.concatenate([r[1] for r in res])
        keep = (f >= f0) & (f <= f1)
        return f[keep], p[keep], max(r[2] for r in res)

    # ------------------------------------------------------------- analysis

    def explain(self, signals, f, shifted=False, top=6, span=None):
        """What makes the reading at input frequency f, strongest first,
        as (displayed frequency, dBm referred to the input, what).  Two
        kinds: the products at the second mixer's output that land within
        `span` of f, and (with the level None: the time-domain half makes
        them, and only a capture gives their size) the harmonics that the
        IF amplifiers and the ADC make of a strong IF tone, aliased."""
        fc = self.centres(f, f)[0]
        band, st, base, sign, t, _ = self.rf(signals, fc, shifted)
        span = span or 2 * self.adc.fs / self.nfft
        out = []
        if len(t):
            fdisp = base + sign * t.f
            near = np.flatnonzero(np.abs(fdisp - f) <= span)
            if near.size:
                g = self.gain_to_adc(band, st, fdisp[near], t.f[near])
                gif = sum(p.g(t.f[near]) for p in self.if_chain[band])
                lev = t.p[near] + gif - g
                for i in np.argsort(-lev)[:top]:
                    out.append((float(fdisp[near][i]), float(lev[i]),
                                str(t.tag[near][i])))
            fs = self.adc.fs
            at_adc = t.p + sum(p.g(t.f) for p in self.if_chain[band])
            # a tone past the ADC's Nyquist frequency, through what the
            # anti-alias filter leaves of it
            fal = t.f % fs
            fal = np.minimum(fal, fs - fal)
            fda = base + sign * fal
            for i in np.flatnonzero((t.f > fs / 2)
                                    & (np.abs(fda - f) <= span)):
                g = self.gain_to_adc(band, st, fda[i:i + 1], fal[i:i + 1])
                out.append((float(fda[i]), float(at_adc[i] - g[0]),
                            "alias of [%s] at an IF of %.1f MHz, through "
                            "the anti-alias filter" % (t.tag[i],
                                                       t.f[i] / MHZ)))
            out.sort(key=lambda x: -x[1])
            for i in np.argsort(-at_adc)[:4]:
                if at_adc[i] < self.fs_node_dbm - 80 or t.f[i] > fs / 2:
                    continue
                # (an ADC that is not dithered makes high harmonics of a
                # signal a few LSB in size)
                for k in range(2, 13):
                    fa = (k * t.f[i]) % fs
                    fa = min(fa, fs - fa)
                    if abs(base + sign * fa - f) <= span:
                        out.append((float(base + sign * fa), None,
                                    "harmonic %d of [%s] in the IF "
                                    "amplifiers and ADC" % (k, t.tag[i])))
        return out

    def budget(self, fin, shifted=False):
        """The wanted path at fin, stage by stage, and the system's figures
        there.  Returns (rows, summary)."""
        fc = self.centres(fin, fin)[0]
        band, st, base, sign = self.tune(fc, shifted)
        chain = self.chains[band]
        chain.run(Tones(), st)          # the LO leaks, for the noise pass
        rows, f = [], float(fin)
        g_cum, f_cum, ip3_inv, p1 = 0.0, 1.0, 0.0, 1e9
        if_parts = self.if_chain[band]
        stages = list(chain.main) + [Lin(p) for p in if_parts]
        for s in stages:
            if isinstance(s, Lin):
                g = float(s.part.g(f))
                nf = float(s.part.noise_figure(f))
                ip3, ip1 = s.part.in_ip3(f), s.part.in_p1db(f)
                fo = f
            else:
                fo, g = s.wanted(f, st)
                fo, g = float(fo), float(g)
                nf, ip3, ip1 = -g, s.mx.iip3, s.mx.ip1db
            f_cum += (mw(nf) - 1) / mw(g_cum)
            ip3_inv += mw(g_cum) / mw(ip3)
            p1 = min(p1, ip1 - g_cum)
            g_cum += g
            rows.append(dict(stage=s.name, f=f, gain=g, nf=nf, iip3=ip3,
                             cum_gain=g_cum, cum_nf=float(dbm(f_cum)),
                             cum_iip3=float(-dbm(ip3_inv))))
            f = fo
        # the noise that really arrives (images and LO noise included)
        _, noise = chain.run(Tones(), st)
        fif = abs(fin - base)
        n = float(noise(np.array([fif]))[0])
        for p in if_parts:
            g = mw(p.g(fif))
            n = (g * n + max(1 - g, 0) * KT0 if p.nf is None else
                 g * (n + (mw(p.noise_figure(fif)) - 1) * KT0))
        n_adc = mw(self.fs_node_dbm + self.adc.snr_ref_dbfs - self.adc.snr_db
                   - 10 * np.log10(self.adc.fs / 2))
        # all the chain's noise that reaches the sampler, in LSB rms: under
        # about half an LSB the converter is not dithered, and a signal
        # smaller than an LSB does not move it
        fg = np.linspace(1e4, backend.OSR * self.adc.fs / 2, 4000)
        ng = noise(fg)
        for p in if_parts:
            g = mw(p.g(fg))
            ng = (g * ng + np.maximum(1 - g, 0) * KT0 if p.nf is None else
                  g * (ng + (mw(p.noise_figure(fg)) - 1) * KT0))
        total = float(np.sum(ng) * (fg[1] - fg[0]))
        lsb = float(np.sqrt(total / mw(self.fs_node_dbm))
                    * 2 ** (self.adc.bits - 1) / np.sqrt(2))
        gain = float(self.gain_to_adc(band, st, np.array([fin]),
                                      np.array([fif]))[0])
        danl = float(dbm(n + n_adc)) - gain
        iip3 = float(-dbm(ip3_inv))
        summary = dict(
            band=band, f=fin, lo1=st.lo["lo1"], lo2=st.lo["lo2"],
            gain_to_adc=gain, nf_friis=float(dbm(f_cum)),
            danl_dbm_hz=danl, nf_effective=danl + 174.0,
            chain_noise_over_adc_db=float(dbm(n) - dbm(n_adc)),
            iip3=iip3, ip1db=p1, adc_full_scale_dbm=self.fs_node_dbm - gain,
            noise_at_adc_lsb=lsb,
            one_lsb_dbm=(self.fs_node_dbm - gain
                         - 20 * np.log10(2 ** (self.adc.bits - 1))),
            sfdr_db_1hz=2.0 / 3.0 * (iip3 - danl))
        return rows, summary


_JOB = None


def _work(fc):
    sa, signals, image_reject, sweep = _JOB
    return sa._step(signals, fc, image_reject, sweep)
