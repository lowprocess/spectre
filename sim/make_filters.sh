#!/bin/bash
# The printed filters, as the simulation uses them: dfsynth synthesises each
# on 0.508 mm RO4003C and corrects it against mom25d (--em-tune), then mom25d
# solves the corrected layout over a wide band, so that the simulation has
# its far stop band and its spurious pass bands.  About 25 minutes on 4 cores.
# A rerun gives the same filters to a few hundredths of a dB in the pass
# band, not the same bytes (dfsynth's refinement is timed).
#
#   ./make_filters.sh            writes filters/ (layouts) and data/ (.s2p)
#   ./make_filters.sh NAME...    only these (the names are data/'s)
#
# Needs kicad2ems (https://github.com/lowprocess/kicad2ems) installed, with
# its mom25d core built (python -m kicad2ems.mom25d.core.build).
set -e
here=$(cd "$(dirname "$0")" && pwd)
work=${WORK:-$here/out/filters}
sub=RO4003C-0.508
mkdir -p "$work" "$here/filters" "$here/data"

only=" $* "
make() {  # name fmax_GHz points dfsynth-arguments...
    local name=$1 fmax=$2 points=$3; shift 3
    local d=$work/$name
    if [ "$only" != "  " ] && [ "${only/ $name /}" = "$only" ]; then
        return 0
    fi
    dfsynth "$@" --substrate $sub -o "$d/f" --validate mom > "$d.log" 2>&1
    sed -e "s/^fmin .*/fmin    = 0.05/" -e "s/^fmax .*/fmax    = $fmax/" \
        -e "s/^points .*/points  = $points/" "$d/f.toml" > "$d/f_wide.toml"
    kicad2ems "$d/f_wide.toml" --solvers mom --out "$d/wide" --no-report \
        > "$d.wide.log" 2>&1
    cp "$d/f.kicad_pcb" "$here/filters/$name.kicad_pcb"
    cp "$d/f.kicad_mod" "$here/filters/$name.kicad_mod"
    cp "$d/f_design.json" "$here/filters/${name}_design.json"
    python3 "$here/compact_s2p.py" "$d/wide/f_mom25d.s2p" \
        "$here/data/$name.s2p"
    echo "$name: done"
}

# the board's own plan (a 3.4 GHz first IF, DC to 3 GHz)
make if1_bpf_3g4_hairpin 10.0 1991 --type bandpass --topology hairpin \
     --f0 3.4G --bw 180M --order 5 --em-tune 2
make in_lpf_3g4_radial 12.0 1196 --type lowpass --topology radial \
     --f0 3.4G --order 7 --em-tune 1
# the proposal's: it shares the 3.4 GHz band-pass
make if1_lpf_4g0_radial 12.0 1196 --type lowpass --topology radial \
     --f0 4.0G --order 7 --em-tune 1
make l2_bpf_2g3_3g0_interdigital 12.0 1196 --type bandpass \
     --topology interdigital --f0 2.59G --bw 740M --order 7 --em-tune 3
make h1_bpf_3g0_4g5_stub 14.0 1396 --type bandpass --topology stub \
     --f0 3.75G --bw 1.6G --order 5 --em-tune 1
make h1_lpf_5g0_radial 14.0 1396 --type lowpass --topology radial \
     --f0 5.0G --order 7 --em-tune 1
make h2_bpf_4g3_6g4_stub 16.0 1596 --type bandpass --topology stub \
     --f0 5.35G --bw 2.2G --order 5 --em-tune 1
make h2_lpf_7g0_radial 18.0 1796 --type lowpass --topology radial \
     --f0 7.0G --order 7 --em-tune 1
