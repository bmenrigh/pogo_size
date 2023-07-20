#!/bin/bash

$DIG = 4

#    | ~/projects/misc_perl/smooth_savitzky_golay.pl 5 1001 \
#    | ~/projects/misc_perl/smooth_savitzky_golay.pl 5 701 \
#    | ~/projects/misc_perl/smooth_savitzky_golay.pl 5 501 \
#    | ~/projects/misc_perl/smooth_savitzky_golay.pl 5 301 \

~/projects/misc_perl/build_pdf.pl $DIG | awk '{print $1"\t"$2}' \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 5 201 \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 5 151 \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 5 101 \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 5 75 \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 3 51 \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 3 31 \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 3 21 \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 3 15 \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 3 11 \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 3 7 \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 3 5 \
    | ~/projects/misc_perl/smooth_savitzky_golay.pl 1 3 \
    | ~/projects/misc_perl/build_pdf.pl $DIG
