#!/bin/bash

DIG=1

#    | ~/projects/misc_perl/smooth_savitzky_golay.pl 5 1001 \
#    | ~/projects/misc_perl/smooth_savitzky_golay.pl 5 701 \
#    | ~/projects/misc_perl/smooth_savitzky_golay.pl 5 501 \
#    | ~/projects/misc_perl/smooth_savitzky_golay.pl 5 301 \




~/projects/misc_perl/build_pdf.pl $DIG | awk '{print $1"\t"$2}' \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 5 301 1 $1 \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 5 201 1 $1 \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 5 151 1 $1 \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 5 101 1 $1 \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 5 75 1 $1 \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 3 51 1 $1 \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 3 31 1 $1 \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 3 21 1 $1 \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 3 15 1 $1 \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 3 11 1 $1 \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 3 7 1 $1 \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 3 5 3 $1 \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 1 3 5 $1 \
    | ~/projects/misc_perl/smooth_linear_boundaries.pl 10 30 1 $1 \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 1 5 1 $1 \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 1 3 5 $1 \
    | ~/projects/misc_perl/build_pdf.pl $DIG
