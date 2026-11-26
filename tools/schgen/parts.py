"""The parts of the 6.4 GHz proposal, as schematic symbols.

Pin numbers are from the makers' data sheets (see docs/schematic.md for
which, and for the two parts whose numbers could not be checked)."""

import os

from . import symbols as sy
from .symbols import (amp_glyph, att_glyph, bandpass_glyph, box,
                      lowpass_glyph, standard, switch_glyph, two_pin)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
LIB = "spectre"


def _p(number, name, etype="passive"):
    return (number, name, etype)


def _shift(glyph, dx=0.0, dy=0.0):
    out = []
    for item in glyph:
        item = [list(x) if isinstance(x, list) else x for x in item]
        for i, x in enumerate(item):
            if isinstance(x, list) and x[0] == "pts":
                item[i] = ["pts"] + [["xy", p[1] + dx, p[2] + dy]
                                     for p in x[1:]]
            elif isinstance(x, list) and x[0] in ("start", "end", "center"):
                item[i] = [x[0], x[1] + dx, x[2] + dy]
        out.append(item)
    return out


# ------------------------------------------------------------------ passives

R = two_pin(LIB + ":R", "R", "R", footprint="ar_passives:R_0402",
            description="Resistor, 0402, 1%")
C = two_pin(LIB + ":C", "C", "C", footprint="ar_passives:C_0402",
            description="Ceramic capacitor, 0402")
L = two_pin(LIB + ":L", "L", "L", footprint="Inductor_SMD:L_0402_1005Metric",
            description="Inductor, 0402")
L_IF = two_pin(LIB + ":L_1008", "L", "L",
               footprint="Inductor_SMD:L_1008_2520Metric",
               description="Inductor, wire-wound, 1008")
FB = two_pin(LIB + ":FB", "FB", "FB", ref="FB",
             footprint="Inductor_SMD:L_0402_1005Metric",
             description="Ferrite bead, 0402")
TVS = two_pin(LIB + ":TVS", "D", "ESD131-B1-W0201", ref="D",
              footprint="Diode_SMD:D_0201_0603Metric",
              description="Two-way ESD diode, 0.2 pF, 5.5 V")
for _s, _pn, _mf in ((TVS, "ESD131-B1-W0201", "Infineon"),):
    sy._prop(_s, "PartNumber", _pn)
    sy._prop(_s, "Manufacturer", _mf)

_KNOWN_C = {      # value: (IPN in the project's database, part, voltage)
    "100nF": ("CAPC-00573", "GRM155R71A104K", "10V"),
    "1uF": ("CAPC-00622", "GRM155R70J105K", "6.3V"),
    "10uF": ("CAPC-00667", "GRM155R60J106M", "6.3V"),
    "10nF": ("CAPC-00514", "GRM155R71C103K", "16V"),
    "470nF": ("CAPC-00613", "GRM155R71A474K", "10V"),
    "1nF": ("", "GRM155R71H102KA01D", "50V"),
    "4.7uF": ("", "GRM155R60J475ME47D", "6.3V"),
}


def _ohms(value):
    v = value.upper().replace("Ω", "R")
    for unit, mult in (("M", 1e6), ("K", 1e3), ("R", 1.0)):
        if unit in v:
            a, b = v.split(unit)
            return float((a or "0") + "." + (b or "0")) * mult
    return float(v)


def passive_fields(kind, value):
    """Maker and part number of a resistor, capacitor or inductor from its
    value, by the maker's numbering scheme; {} when it is not a plain value
    (those are left for the designer)."""
    try:
        if kind == "R":
            ohm = _ohms(value)
            if ohm == 0:
                return {"IPN": "RESI-00694", "PartNumber": "CRCW04020000Z0ED",
                        "Manufacturer": "Vishay"}
            if ohm < 100:
                code = ("%04.1f" % ohm).replace(".", "R")
            elif ohm < 1e3:
                code = "%dR" % round(ohm)
            elif ohm < 1e4:
                code = ("%.2f" % (ohm / 1e3)).replace(".", "K")
            elif ohm < 1e5:
                code = ("%.1f" % (ohm / 1e3)).replace(".", "K")
            elif ohm < 1e6:
                code = "%dK" % round(ohm / 1e3)
            else:
                code = ("%.2f" % (ohm / 1e6)).replace(".", "M")
            return {"PartNumber": "CRCW0402%sFKED" % code,
                    "Manufacturer": "Vishay"}
        if kind == "C":
            if value in _KNOWN_C:
                ipn, pn, volt = _KNOWN_C[value]
                return {"IPN": ipn, "PartNumber": pn,
                        "Manufacturer": "Murata", "Voltage": volt}
            if value.endswith("pF"):
                pf = float(value[:-2])
                if pf < 10:
                    code, tol = ("%.1f" % pf).replace(".", "R"), "C"
                else:
                    exp = 0
                    while pf >= 100:
                        pf, exp = pf / 10, exp + 1
                    code, tol = "%d%d" % (round(pf), exp), "J"
                return {"PartNumber": "GRM1555C1H%s%sA01D" % (code, tol),
                        "Manufacturer": "Murata", "Voltage": "50V"}
        if kind in ("L", "L_IF") and value.endswith("nH"):
            nh = float(value[:-2])
            if nh < 10:
                code = ("%.1f" % nh).replace(".", "N")
            elif nh < 100:
                code = "%dN" % round(nh)
            else:
                exp = 0
                while nh >= 100:
                    nh, exp = nh / 10, exp + 1
                code = "%d%d" % (round(nh), exp)
            series, tail = (("1008CS", "XJLC") if kind == "L_IF"
                            else ("0402HP", "XJLU"))
            return {"PartNumber": "%s-%s%s" % (series, code, tail),
                    "Manufacturer": "Coilcraft"}
    except ValueError:
        pass
    return {}


# ---------------------------------------------------------------- RF switches

def _ic(name, value, fields, **kw):
    extra = {"IPN": "", "PartNumber": fields[0], "Manufacturer": fields[1]}
    return box(LIB + ":" + name, value, extra=extra, **kw)


PE42520 = _ic(
    "PE42520", "PE42520", ("PE42520C-Z", "pSemi"),
    left=[None, _p("7", "RFC"), None, _p("14", "CTRL", "input")],
    right=[_p("2", "RF1"), None, _p("11", "RF2"), None],
    top=[_p("16", "VDD", "power_in")],
    bottom=[_p("15", "LS", "input"), _p("13", "VSS", "passive"),
            _p("1,3,4,5,6,8,9,10,12,17", "GND", "power_in")],
    footprint="Package_DFN_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.7x1.7mm",
    datasheet="https://www.psemi.com/pdf/datasheets/pe42520ds.pdf",
    description="SPDT RF switch, 9 kHz to 13 GHz, absorptive",
    width=15.24, glyph=_shift(switch_glyph(2, span=5.08), 0, 2.54))

PE42540 = _ic(
    "PE42540", "PE42540", ("PE42540F-Z", "pSemi"),
    left=[None, None, None, _p("13", "RFC"), None, None, None,
          _p("29", "V1", "input"), _p("30", "V2", "input")],
    right=[_p("18", "RF1"), None, _p("7", "RF2"), None, _p("23", "RF3"),
           None, _p("2", "RF4"), None, None],
    top=[_p("27", "VDD", "power_in")],
    bottom=[_p("31", "VSS", "passive"),
            _p("1,3,4,5,6,8,9,10,11,12,14,15,16,17,19,20,21,22,24,25,26,28,"
               "32,33", "GND", "power_in")],
    footprint="Package_DFN_QFN:QFN-32-1EP_5x5mm_P0.5mm_EP3.1x3.1mm",
    datasheet="https://www.psemi.com/pdf/datasheets/pe42540ds.pdf",
    description="SP4T RF switch, 10 Hz to 8 GHz, absorptive",
    width=17.78, glyph=_shift(switch_glyph(4, span=15.24), 0, 2.54))

# ---------------------------------------------------------------- attenuators

_PAR4 = "32,31,30,29,28,27,26"
PE43704 = _ic(
    "PE43704", "PE43704", ("PE43704B-Z", "pSemi"),
    left=[_p("7", "RF1"), None, None, _p("25", "SI", "input"),
          _p("24", "CLK", "input"), _p("23", "LE", "input")],
    right=[_p("18", "RF2"), None, None, None, None, None],
    top=[_p("3", "P/~{S}", "input"), _p("2", "VDD", "power_in")],
    bottom=[_p("4,22,21", "A0-A2", "input"),
            _p(_PAR4, "C0.25-C16", "input"), _p("20", "VSS", "passive"),
            _p("5,6,8,9,10,11,12,13,14,15,16,17,19,33", "GND", "power_in"),
            _p("1", "NC", "no_connect")],
    footprint="Package_DFN_QFN:QFN-32-1EP_5x5mm_P0.5mm_EP3.1x3.1mm",
    datasheet="https://www.psemi.com/pdf/datasheets/pe43704ds.pdf",
    description="Digital step attenuator, 7 bit, 0.25 dB steps to 31.75 dB,"
                " 9 kHz to 8 GHz",
    width=22.86, glyph=_shift(att_glyph(), 0, 2.54))

PE43711 = _ic(
    "PE43711", "PE43711", ("PE43711A-Z", "pSemi"),
    left=[_p("5", "RF1"), None, None, _p("18", "SI", "input"),
          _p("17", "CLK", "input"), _p("16", "LE", "input")],
    right=[_p("14", "RF2"), None, None, None, None, None],
    top=[_p("3", "P/~{S}", "input"), _p("2", "VDD", "power_in")],
    bottom=[_p("1,24,23,22,21,20,19", "C0.25-C16", "input"),
            _p("4,6,7,8,9,10,11,12,13,15,25", "GND", "power_in")],
    footprint="Package_DFN_QFN:QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm",
    datasheet="https://www.psemi.com/pdf/datasheets/pe43711ds.pdf",
    description="Digital step attenuator, 7 bit, 0.25 dB steps to 31.75 dB,"
                " 9 kHz to 6 GHz",
    width=20.32, glyph=_shift(att_glyph(), 0, 2.54))

# ----------------------------------------------------------------- amplifiers

PMA3_83LN = _ic(
    "PMA3-83LN+", "PMA3-83LN+", ("PMA3-83LN+", "Mini-Circuits"),
    left=[_p("2", "RF-IN"), None, None],
    right=[_p("8", "RF-OUT"), None, None],
    bottom=[_p("13,1,3,4,5,6,7,9,10", "GND", "power_in"),
            _p("11", "NC", "no_connect"), _p("12", "NC", "no_connect")],
    footprint="Package_DFN_QFN:QFN-12-1EP_3x3mm_P0.5mm_EP1.65x1.65mm",
    datasheet="https://www.minicircuits.com/pdfs/PMA3-83LN+.pdf",
    description="Low-noise amplifier, 0.5 to 8 GHz, NF 1.3 dB, 5 V",
    width=22.86, glyph=_shift(amp_glyph(1.9), 0, 0.6))

TRF37D73 = _ic(
    "TRF37D73", "TRF37D73", ("TRF37D73IDSGR", "Texas Instruments"),
    left=[_p("2", "RFIN"), None, _p("5", "PWDN", "input")],
    right=[_p("7", "RFOUT"), None, None],
    top=[_p("1", "VCC", "power_in")],
    bottom=[_p("9,3,4,6,8", "GND", "power_in")],
    footprint="Package_SON:Texas_DSG0008A_WSON-8-1EP_2x2mm_P0.5mm_"
              "EP0.9x1.6mm",
    datasheet="https://www.ti.com/lit/ds/symlink/trf37d73.pdf",
    description="Gain block, 1 MHz to 6 GHz, 20 dB, power-down, 3.3 V",
    width=17.78, glyph=_shift(amp_glyph(1.9), 0, 0))

# ------------------------------------------------------------- printed filters

def _filter(name, glyph, ground):
    s = box(LIB + ":" + name, name, ref="FL",
            left=[_p("1", "1"), None], right=[_p("2", "2"), None],
            bottom=[_p("3", "GND", "power_in")] if ground else [],
            description="Printed microstrip filter on 0.508 mm RO4003C "
                        "(dfsynth); see sim/filters",
            width=12.7, glyph=_shift(glyph, 0, 0), min_height=7.62)
    return s


FILTER_LP = _filter("Filter_Printed_LP", lowpass_glyph(), False)
FILTER_BP = _filter("Filter_Printed_BP", bandpass_glyph(), False)
FILTER_BP_G = _filter("Filter_Printed_BP_Gnd", bandpass_glyph(), True)

LFCN = standard("RF_Filter", "LFCN-2250", rename="LFCN-2250+")

# ------------------------------------------------------- mixers, synthesizers

SIM83 = sy.lifted(os.path.join(HERE, "sim83.kicad_sym_fragment"),
                  "#bt-db:ic/ICIR-00218") if os.path.exists(
    os.path.join(HERE, "sim83.kicad_sym_fragment")) else None

# ------------------------------------------------------------ IF, ADC, clock

LMH6629 = standard("Amplifier_Operational", "LMH6609MF", rename="LMH6629MF")
sy._prop(LMH6629, "Datasheet",
         "https://www.ti.com/lit/ds/symlink/lmh6629.pdf")
sy._prop(LMH6629, "Description", "Op amp, 0.69 nV/rtHz, 4 GHz gain-"
         "bandwidth, stable for gains of 10 and more, SOT-23-5")
THS4541 = _ic(
    "THS4541", "THS4541", ("THS4541IRGTR", "Texas Instruments"),
    left=[_p("3", "IN-", "input"), None, _p("9", "VOCM", "input"), None,
          _p("2", "IN+", "input")],
    right=[_p("10", "OUT+", "output"), None, None, None,
           _p("11", "OUT-", "output")],
    top=[_p("4", "FB+", "passive"), None, None, _p("12", "~{PD}", "input"),
         _p("5,6,7,8", "VS+", "power_in")],
    bottom=[_p("1", "FB-", "passive"),
            _p("13,14,15,16,17", "VS-", "power_in")],
    footprint="Package_DFN_QFN:VQFN-16-1EP_3x3mm_P0.5mm_EP1.68x1.68mm",
    datasheet="https://www.ti.com/lit/ds/symlink/ths4541.pdf",
    description="Fully differential amplifier, 850 MHz, rail-to-rail "
                "output; FB+ and FB- are the outputs brought round to the "
                "inputs", width=25.4, glyph=_shift(amp_glyph(2.4), 0, 0))

# Only the numbers the data sheet search confirmed are given; the rest carry a
# "?" and must be filled in from the SD9609 data sheet before layout.
ADC = _ic(
    "SD9609-40", "SD9609-40", ("SD9609-40", "(AD9609-40 pin-compatible)"),
    left=[_p("?VIN+", "VIN+", "input"), None, None, None,
          _p("?VIN-", "VIN-", "input"), None, None,
          _p("?VCM", "VCM", "output"), None, _p("?VREF", "VREF", "passive"),
          None, _p("?SENSE", "SENSE", "input"), None,
          _p("?RBIAS", "RBIAS", "passive"), None, None, None, None,
          _p("1", "CLK+", "input"), None, _p("2", "CLK-", "input"),
          None, None, None, None, _p("4", "CSB", "input"),
          _p("5", "SCLK/DFS", "input"),
          _p("6", "SDIO/PDWN", "bidirectional")],
    right=[_p("?D%d" % i, "D%d" % i, "output") for i in range(9, -1, -1)]
    + [None, None, _p("?DCO", "DCO", "output"), None,
       _p("23", "MODE/OR", "bidirectional")] + [None] * 13,
    top=[_p("3,24,29,32", "AVDD", "power_in"),
         _p("?DRVDD", "DRVDD", "power_in")],
    bottom=[_p("33", "AGND", "power_in"), _p("7", "NC", "no_connect"),
            _p("8", "NC", "no_connect")],
    footprint="Package_CSP:LFCSP-32-1EP_5x5mm_P0.5mm_EP3.6x3.6mm",
    description="ADC, 10 bit, 40 MSPS, 1.8 V, parallel CMOS output",
    width=30.48, pin_length=7.62)

LMK1C1104 = _ic(
    "LMK1C1104", "LMK1C1104", ("LMK1C1104PWR", "Texas Instruments"),
    left=[_p("1", "CLKIN", "input")] + [None] * 9,
    right=[_p("3", "Y0", "output"), None, None, _p("8", "Y1", "output"),
           None, None, _p("5", "Y2", "output"), None, None,
           _p("7", "Y3", "output")],
    top=[_p("2", "1G", "input"), _p("6", "VDD", "power_in")],
    bottom=[_p("4", "GND", "power_in")],
    footprint="Package_SO:TSSOP-8_4.4x3mm_P0.65mm",
    datasheet="https://www.ti.com/lit/ds/symlink/lmk1c1104.pdf",
    description="Clock buffer, 1 to 4, LVCMOS, low additive jitter",
    width=22.86)

OSC = standard("Oscillator", "ECS-2520MV-xxx-xx", rename="ECS-2520MV-400")
LDO = standard("Regulator_Linear", "LP5907MFX-3.3")
LDO18 = standard("Regulator_Linear", "LP5907MFX-3.3",
                 rename="LP5907MFX-1.8")

# ----------------------------------------------------------------- controller

RP2350B = standard("MCU_RaspberryPi", "RP2350B")
FLASH = standard("Memory_Flash", "W25Q32JVSS")
USB_C = standard("Connector", "USB_C_Receptacle_USB2.0_16P")
USB_ESD = standard("Power_Protection", "USBLC6-2SC6")
SMA = standard("Connector", "Conn_Coaxial")
BUTTON = standard("Switch", "SW_Push")
HEADER3 = standard("Connector_Generic", "Conn_01x03")
LED = standard("Device", "LED")
TP = standard("Connector", "TestPoint")

GND = standard("power", "GND")
VCC = standard("power", "VCC")
PWR_FLAG = standard("power", "PWR_FLAG")
