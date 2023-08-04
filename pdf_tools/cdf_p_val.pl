#!/usr/bin/perl

use strict;
use warnings;

my @cdf_v;
my @cdf_p;


# Assume CDF is sorted
while (<STDIN>) {
    chomp;

    my $line = $_;

    #if ($line =~ m/^\s*(\d+(?:\.\d+(?:e-?\d+)?)?)\s+(\d+(?:\.\d+(?:e-?\d+)?)?)(?:\s+(\d+(?:\.\d+(?:e-?\d+)?)?))?(?:\s+[iou]\s*)?$/) {
    if ($line =~ m/^\d/) {
        my @numlist = split(/\s+/, $line);


        push @cdf_v, $numlist[0];
        push @cdf_p, $numlist[3];
    }
}

# my $test_v = 0.014125;
# print sprintf("P-val for test v: %.015f is %.015f\n", $test_v, pval($test_v));
# $test_v = 0.014150;
# print sprintf("P-val for test v: %.015f is %.015f\n", $test_v, pval($test_v));
# my $test_v = 0.014199;
# print sprintf("P-val for test v: %.015f is %.015f\n", $test_v, pval($test_v));
# exit(0);


#print sprintf('%.015f', pval(1.38889375) - pval(1.38888125)), "\n";
#print sprintf('%.015f', pval(888.885 / 800.0) - pval(888.875 / 800.0)), "\n";
#print sprintf('%.015f', pval(999.995 / 800.0) - pval(999.985 / 800.0)), "\n";
#print sprintf('%.015f', pval(1111.115 / 800.0) - pval(1111.105 / 800.0)), "\n";
#print sprintf('%.015f', pval(1111.125 / 800.0) - pval(1111.115 / 800.0)), "\n";

#report('Big Karp', 13.125, 10.0, 1);
#report('Big Karp', 13.1255, 10.0, 1);
#report('Big Karp', 13.126, 10.0, 1);
#exit(0);

report('Tiny Rat (regular)', 2.40625, 3.5, 0);
report('Tiny Rat (regular)', 3.14159265, 3.5, 0);
#report('Flabebe', 0.025, 0.1, 0);
#report('Flabebe', 0.015, 0.1, 0);
#report('Tiny Rat (alolan)', 2.40625, 3.8, 0);
#print sprintf('%.015f', pval(11.0/16.0)), "\n";
#report('Big Karp', 13.125, 10.0, 1);
#report('Ursa Luna', 91.91, 290.0, 0);
#report('Ursa Luna', 19.01, 290.0, 0);
#report('Kaito Small Alakazam', 17.825, 48.0, 0);
#report('Kaito Big Alakazam', 85.385, 48.0, 1);
#report('Kaito 1-in-4299', find_weight_from_p_val(1/4299.0, 48.0, 0), 48.0, 0);
#report('Kaito 1-in-4299', find_weight_from_p_val(1/4299.0, 48.0, 1), 48.0, 1);
#print '20.59  Karp: ', sprintf('%.015f', 1.0 - pval(20.585/10.0)), "\n";
#print '20.29  Karp: ', sprintf('%.015f', 1.0 - pval(20.285/10.0)), "\n";
#print '21.00  Karp: ', sprintf('%.015f', 1.0 - pval(20.995/10.0)), "\n";
#print '23.33  Karp: ', sprintf('%.015f', 1.0 - pval(23.325/10.0)), "\n";
#print sprintf('%.015f', 1.0 - pval(13.125 / 10.0)), "\n";
#print '0.01kg Squirtle: ', sprintf('%.015f', pval(0.015 / 9.0)), "\n";
#print '0.01kg Rat: ', sprintf('%.015f', pval(0.0149999 / 3.5)), "\n";
#print '22.66kg Karp: ', sprintf('%.015f', 1.0 - pval(22.655 / 10.0)), "\n";
#print '0.4kg Karp: ', sprintf('%.015f', pval(0.405 / 10.0)), "\n";

#print sprintf('%.015f', (pval(2.40625 / 3.5) - pval(2.405 / 3.5)) / (pval(2.415 / 3.5) - pval(2.405 / 3.5))), "\n";

sub report {
    my $str = shift;
    my $m = shift;
    my $mean = shift;
    my $r = shift; # right side

    my $pv = pval($m / $mean);

    if ($r == 1) {
        $pv = 1.0 - $pv;
    }

    print sprintf('%s weight at %s %.06f kg: p=%.06f; %.06f%% (1 in %.04f)', $str, ($r == 0)? 'most' : 'least', $m, $pv, $pv * 100.0, ($pv == 0)? "inf" : (1.0 / $pv)), "\n";

}


sub find_weight_from_p_val {
    my $tpv = shift;
    my $mean = shift;
    my $r = shift; # right side

    my $m;
    if ($r == 0) {
        # left side search
        for ($m = 0.005; $m < (2.75 * $mean); $m += 0.005) {

            my $pv = pval($m / $mean);

            if ($pv >= $tpv) {
                last;
            }
        }
    } elsif ($r == 1) {
        # right side search
        for ($m = (2.75 * $mean) - 0.005; $m >= 0.005; $m -= 0.005) {

            my $pv = 1.0 - pval($m / $mean);

            if ($pv >= $tpv) {
                last;
            }
        }
    }

    return $m;
}

# new right-aligned bins
sub pval {
    my $v = shift;

    my $l = scalar @cdf_v;

    if ($v <= $cdf_v[0]) {
        return 0.0;
    }

    if ($v >= $cdf_v[$l - 1]) {
        return 1.0;
    }

    for (my $i = 0; $i < ($l - 1); $i++) {
        if  (($v >= $cdf_v[$i]) && ($v < $cdf_v[$i + 1])) {

            #warn sprintf('Search value %.015f is >= %.015f in bucket %d with p-val %.015f (1 - p: %0.15f)', $v, $cdf_v[$i], $i, $cdf_p[$i], 1.0 - $cdf_p[$i]), "\n";

            my $vdelta = $cdf_v[$i + 1] - $cdf_v[$i]; # The width of this bucket
            my $pdelta = $cdf_p[$i + 1] - $cdf_p[$i]; # The height of this bucket

            my $voffset = $v - $cdf_v[$i];

            return ($cdf_p[$i] + (($voffset / $vdelta) * $pdelta));
        }
    }

    die 'Failed to find pval', "\n";
}

# Old left-aligned bins
sub pval_left {
    my $v = shift;

    my $l = scalar @cdf_v;

    if ($v <= $cdf_v[0]) {
        return 0.0;
    }

    if ($v >= $cdf_v[$l - 1]) {
        return 1.0;
    }

    for (my $i = 1; $i < ($l - 1); $i++) {
        if  (($v >= $cdf_v[$i]) && ($v < $cdf_v[$i + 1])) {

            #warn sprintf('Search value %.015f is >= %.015f in bucket %d with p-val %.015f (1 - p: %0.15f)', $v, $cdf_v[$i], $i, $cdf_p[$i], 1.0 - $cdf_p[$i]), "\n";

            my $vdelta = $cdf_v[$i + 1] - $cdf_v[$i]; # The width of this bucket
            my $pdelta = $cdf_p[$i] - $cdf_p[$i - 1]; # The height of this bucket

            my $voffset = $v - $cdf_v[$i];

            return ($cdf_p[$i - 1] + (($voffset / $vdelta) * $pdelta));
        }
    }

    die 'Failed to find pval', "\n";
}

# Old function for center-aligned cdf bins
sub pval_center {
    my $v = shift;

    my $l = scalar @cdf_v;

    if ($v < $cdf_v[0]) {
        return 0.0;
    }

    if ($v == $cdf_v[0]) {
        return $cdf_v[0];
    }

    if ($v >= $cdf_v[$l - 1]) {
        return 1.0;
    }


    for (my $i = 1; $i < $l; $i++) {
        if  ($v <= $cdf_v[$i]) {

            my $vdelta = $cdf_v[$i] - $cdf_v[$i - 1];
            my $pdelta = $cdf_p[$i] - $cdf_p[$i - 1];

            my $voffset = $v - $cdf_v[$i - 1];

            return ($cdf_p[$i - 1] + (($voffset / $vdelta) * $pdelta));
        }
    }
}
