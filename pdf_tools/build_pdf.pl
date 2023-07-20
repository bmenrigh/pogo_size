#!/usr/bin/perl

use strict;
use warnings;

my %counts;
my $total = 0;

my $scale = 1.0; # The amount of area under the PDF
my $figs = 4;
if ((exists $ARGV[0]) && ($ARGV[0] =~ m/^\d+$/)) {
    $figs = $ARGV[0];
    warn 'Using ', $figs, ' significant figures after decimal', "\n";
}
else {
    warn 'Using default ', $figs, ' significant figures after decimal', "\n";
}

if ((exists $ARGV[1]) && ($ARGV[1] =~ m/^\d+(?:\.\d+)$/)) {
    $scale = $ARGV[1] * 1.0;
    warn 'Using ', $scale, ' for area under PDF', "\n";
}
else {
    warn 'Using default ', $scale, ' for area under PDF', "\n";
}

my $bfmt = sprintf('%%.0%df', $figs);
my $box_factor = 10 ** $figs;


my ($bmin, $bmax); # For filling in gaps

while (<STDIN>) {
    chomp;

    my $line = $_;

    if ($line =~ m/^(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)/) {

        my $b = sprintf($bfmt, $1);
        my $v = $2;

        if ($b =~ m/^-(0\.0+)$/) {
            $b = $1; # turn -0.0000 into positive 0
        }

        $bmin = $b unless (defined $bmin);
        $bmax = $b unless (defined $bmax);

        unless (exists $counts{$b}) {
            $counts{$b} = 0;
        }

        $counts{$b} += $v if ($v >= 0.0); # ignore negative probabilities

        $bmin = $b if ($b < $bmin);
        $bmax = $b if ($b > $bmax);

        $total += $v;
    }
}

if (scalar(keys %counts) == 0) {
    exit;
}

# Fill in gaps
my $b_width = 1.0 / $box_factor;
for (my $x = $bmin; $x < $bmax; $x += $b_width) {
    my $b = sprintf($bfmt, $x);

    $counts{$b} = 0 unless (exists $counts{$b});
}


foreach my $w (sort {$a <=> $b} keys %counts) {

    print sprintf('%.04f %.15f %.15f', $w, $counts{$w} * $scale, (($counts{$w} * $box_factor * $scale) / $total)), "\n";
}
