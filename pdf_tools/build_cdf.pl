#!/usr/bin/perl

use strict;
use warnings;

my %counts;
my $total = 0;

while (<STDIN>) {
    chomp;

    my $line = $_;

    if ($line =~ m/^\s*(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?(?:e-?\d+)?)(?:\s+[iuo]\s*)?(\s|$)/) {

        unless (exists $counts{$1}) {
            $counts{$1} = 0.0;
        }
        $counts{$1} += $2;

        $total += $2;
    }

}

my $running = 0.0;
my @p = sort {$a <=> $b} keys %counts;
my $l = scalar @p;
print sprintf('%.04f %.015f %.015f %.015f', $p[0] - ($p[1] - $p[0]), 0, 0, 0), "\n";
for (my $i = 0; $i < ($l - 1); $i++) {
    $running += $counts{$p[$i]};

    # This would be for a centered bucket
    #print sprintf('%f %.015f %.015f %.015f', (($p[$i] + $p[$i + 1]) / 2.0), $counts{$p[$i]}, (($running * 1.0) / ($total * 1.0)), ($running * 1.0)), "\n";

    # A left-aligned bucket
    print sprintf('%.04f %.015f %.015f %.015f', $p[$i], ($counts{$p[$i]} * 10000.0) / ($total * 1.0), (($running * 1.0) / ($total * 1.0)), ($running * 1.0)), "\n";
}

$running += $counts{$p[$l - 1]};
print sprintf('%.04f %.015f %.015f %.015f', $p[$l - 1], ($counts{$p[$l - 1]} * 10000.0) / ($total * 1.0), (($running * 1.0) / ($total * 1.0)), ($running * 1.0)), "\n";

# Final line is redundant but shows the CDF's cutoff
print sprintf('%.04f %.015f %.015f %.015f', $p[$l - 1] + ($p[1] - $p[0]), 0.0, 1.0, ($running * 1.0)), "\n";
