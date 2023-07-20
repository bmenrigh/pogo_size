#!/usr/bin/perl

use strict;
use warnings;

# https://en.wikipedia.org/wiki/Savitzky–Golay_filter

# GP/PARI> sgolay_c(m, j) = ((3*m^2 - 7 - 20 * j^2) / 4) / ((m * (m^2 - 4) / 3))
# GP/PARI> sgolay_ft(m, x) = {my(y); y = 0; for(X = (1 - m) / 2, (m - 1) / 2, y = y + sgolay_c(m, X) * cos(X * x);); y}
# GP/PARI> plot(X = 0, Pi, sgolay_ft(9, X))
#
#         1 """""""xx_'''''''''''''''''''''''''''''''''''''''''''''''''''''|
#           |         "_                                                   |
#           |           x                                                  |
#           |            "_                                                |
#           |              _                                               |
#           |               _                                              |
#           |                                                              |
#           |                "                                             |
#           |                 "                                            |
#           |                  x                                           |
#           |                   _                                          |
#           |                                                              |
#           |                    "                                         |
#           |                     _                         _              |
#           |                                           _x"" ""_           |
#           |                      "                   x        "_         |
#           |                       "                _"           "_       |
#           -------------------------x--------------x---------------x-------
#           |                         x            x                 "_    |
#           |                          x         _"                    "_  |
#           |                           x       x                        """
# -0.265344 |............................"x___x"...........................|
#           0                                                       3.141593
#

my $ORD = 3; # Default to 2nd / 3rd order polynomial smoothing
my $N = 25; # Must be odd and > $ORD
my $PASSES = 1; # Must be >= 1
my @protected_points = ();

if ((exists $ARGV[0]) &&
    (defined $ARGV[0])) {
    $ORD = $ARGV[0];

    unless ($ORD =~ m/^(?:[12345])$/) {
        die 'Provided order ', $ORD, ' must be in the range [1,5]', "\n";
    }

    $ORD += 1 if ($ORD & 1 == 0); # Make order odd (2 -> 3 and 4 -> 5)
}


if ((exists $ARGV[1]) &&
    (defined $ARGV[1])) {
    $N = $ARGV[1];

    unless ($N =~ m/^(?:[3579]|\d+[13579])$/) {
        die 'Provided N ', $N, ' must be odd and > the order', "\n";
    }
}

if ($N <= $ORD) {
    die 'Provided N ', $N, ' must be greater than the order ', $ORD, "\n";
}


if ((exists $ARGV[2]) &&
    (defined $ARGV[2])) {
    $PASSES = $ARGV[2];

    unless (($PASSES =~ m/^\d+$/) && (int($PASSES) >= 1)) {
        die 'Provided passes ', $PASSES, ' must be >= 1', "\n";
    }
}


if ((exists $ARGV[3]) &&
    (defined $ARGV[3]) &&
    (-e $ARGV[3])) {

    warn 'Loading protected points from ', $ARGV[3], "\n";
    open(my $pfh, '<', $ARGV[3]) or die 'Unable to open points file ', $ARGV[3], ' ', $?, ' ', $!, "\n";
    while (<$pfh>) {
        my $line = $_;
        chomp($line);

        if ($line =~ m/^\s*(-?\d+(?:\.\d+)?)\s*$/) {
            push @protected_points, $1;
        } else {
            warn 'Unable to parse protected point ', $line, "\n";
        }
    }
    close($pfh);

    warn 'Loaded ', scalar(@protected_points), ' protected points', "\n";
}


warn sprintf('Smoothing with order %d/%d polynomials over %d points, using %d passes with %d protected points', ($ORD - 1), $ORD, $N, $PASSES, scalar @protected_points), "\n";


my $NH = (($N - 1) / 2);

# http://www.statistics4u.info/fundstat_eng/cc_savgol_coeff.html
# The correct point for a5 for 25-point smoothing is 342 not 322 or 343.

# https://en.wikipedia.org/wiki/Savitzky%E2%80%93Golay_filter#Algebraic_expressions

#my %h = ('25' => 5175.0);
#my %coeff = ('25' => [(467, 462, 447, 422, 387, 342, 287, 222, 147, 62, -33, -138, -253)]);

# https://pubs.acs.org/doi/abs/10.1021/ac50031a048
# GP/PARI> ps0_45(m, s) = (15/4)*((15*m^4 + 30*m^3 - 35*m^2 - 50*m + 12) - (35 * (2*m^2 + 2 * m - 3)) + 63*s^4) / ((2 * m + 5) * (2*m + 3) * (2 * m + 1) * (2 * m - 1)*(2 * m - 3))
# GP/PARI> ps0_45((m - 1)/2,i)
# = (225*m^4 + (-4200*i^2 - 3450)*m^2 + (15120*i^4 + 29400*i^2 + 6105))/(64*m^5 - 1280*m^3 + 4096*m)


# h can be computed as (N * (N^2 - 4)) / 3
my $h;
if ($ORD == 1) {
    $h = $N;
} elsif ($ORD == 3) {
    $h = ($N * ($N * $N - 4.0)) / 3.0;
} elsif ($ORD == 5) {
    $h = (64 * $N ** 5 - 1280 * $N ** 3 + 4096 * $N)
} else {
    die 'Can not do ', $ORD, ' (yet?)', "\n";
}


# coeff can be computed as (3*N^2 - 7 - 20*i^2) / 4 for i = 0 .. NH
my @coeff;
for (my $i = 0; $i <= $NH; $i++) {
    if ($ORD == 1) {
        push @coeff, 1;
    } elsif ($ORD == 3) {
        push @coeff, (((3.0 * $N * $N) - 7.0 - (20.0 * $i * $i)) / 4.0);
    } elsif ($ORD == 5) {
        push @coeff, (225 * $N ** 4 + (-4200 * $i ** 2 - 3450) * $N ** 2 + (15120 * $i ** 4 + 29400 * $i ** 2 + 6105));
    } else {
        die 'Can not do ', $ORD, ' (yet?)', "\n";
    }
}

my $f = gcd_list((@coeff, $h));

if ($f > 1) {
    warn 'Found a common factor of ', $f, ': reducing coefficients', "\n";

    $h /= $f;
    for (my $i = 0; $i <= $NH; $i++) {
        $coeff[$i] /= $f;
    }
}

#warn 'h: ', $h, "\n";
#warn 'coeff: ', join(', ', @coeff), "\n";
#exit(0);


# Don't use these points in the smoothing
my $START_PROTECT = 1;
my $END_PROTECT = 1;


my %data_raw;
while (<STDIN>) {
    chomp;

    my $line = $_;

    unless ($line =~ m/^\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)(?:\s|$)/) {
        warn 'Got unparsable line: ', $line, "\n";
        next;
    }
    my ($x, $y) = ($1, $2);

    unless (exists $data_raw{$x}) {
        $data_raw{$x} = 0;
    }
    $data_raw{$x} += $y;
}

my @xlist = sort {$a <=> $b} keys %data_raw;

# The gap between each x must be constant
my $xcount = scalar @xlist;
if ($xcount > 1) {
    my $d = sprintf("%.07f", $xlist[1] - $xlist[0]);

    for (my $i = 2; $i < $xcount; $i++) {
        if (sprintf("%.07f", $xlist[$i] - $xlist[$i - 1]) ne $d) {
            warn 'Unable to smooth the data, the gap between points must be constant!', "\n";
            warn 'Got delta of ', $d, ' but ', $xlist[$i], ' - ', $xlist[$i - 1], ' = ', ($xlist[$i] - $xlist[$i - 1]), "\n";
            die 'Exiting', "\n";
        }
    }
}


my %data_smooth;
for (my $p = 0; $p < $PASSES; $p++) {

    %data_smooth = ();

    # Copy the protected start points
    for (my $i = 0; ($i < $START_PROTECT) && ($i < $xcount); $i++) {
        $data_smooth{$xlist[$i]} = $data_raw{$xlist[$i]};
    }

    # Copy the first ((N - 1) / 2) unsmoothable points
    for (my $i = $START_PROTECT; ($i < $START_PROTECT + $NH) && ($i < $xcount); $i++) {
        $data_smooth{$xlist[$i]} = $data_raw{$xlist[$i]};
    }

    # Copy the protected end points
    for (my $i = ($xcount - 1); ($i > (($xcount - 1) - $END_PROTECT)) && ($i >= 0); $i--) {
        $data_smooth{$xlist[$i]} = $data_raw{$xlist[$i]};
    }

    # Copy the last ((N - 1) / 2) unsmoothable points
    for (my $i = ($xcount - 1) - $END_PROTECT; ($i > (($xcount - 1) - $END_PROTECT) - $NH) && ($i >= 0); $i--) {
        $data_smooth{$xlist[$i]} = $data_raw{$xlist[$i]};
    }

    # Smooth the middle points
    for (my $i = $START_PROTECT + $NH; $i < ($xcount - $END_PROTECT) - $NH; $i++) {

        my $skip = 0;
        foreach my $prot (@protected_points) {
            if (($xlist[$i - $NH] < $prot) &&
                ($xlist[$i + $NH] > $prot)) {
                $skip = 1;
                last;
            }
        }

        if ($skip == 0) {
            my $smy = $coeff[0] * $data_raw{$xlist[$i]}; # The middle point

            for (my $j = 1; $j <= $NH; $j++) {
                $smy += ($coeff[$j] * $data_raw{$xlist[$i + $j]});
                $smy += ($coeff[$j] * $data_raw{$xlist[$i - $j]});
            }
            $smy /= $h;

            $data_smooth{$xlist[$i]} = $smy

        } else {
            $data_smooth{$xlist[$i]} = $data_raw{$xlist[$i]};
        }
    }

    %data_raw = %data_smooth;
}

foreach my $smx (sort {$a <=> $b} keys %data_smooth) {
    print $smx, ' ', sprintf("%.7f", $data_smooth{$smx}), "\n";
}


# d = a * x + b * y  where d is the GCD
sub euclid_gcd {
    my $a = shift;
    my $b = shift;

    if ($b == 0) {
        return ($a, 1, 0);
    }

    my ($d2, $x2, $y2) = euclid_gcd($b, $a % $b);

    my ($d, $x, $y) = ($d2, $y2, $x2 - (int($a / $b) * $y2));

    return ($d, $x, $y);
}


sub gcd_list {
    my @l = @_;

    my $len = scalar @l;

    if ($len == 0) {
        die 'Can not GCD an empty list!', "\n";
    } elsif ($len == 1) {
        return $l[0];
    }

    my ($d, $x, $y) = euclid_gcd($l[0], $l[1]);
    for (my $i = 2; $i < $len; $i++) {
        ($d, $x, $y) = euclid_gcd($d, $l[$i]);
    }

    return $d;
}
