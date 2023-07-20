#!/usr/bin/perl

use strict;
use warnings;

my $P = 5; # Number of points next to the boundary to smooth
my $N = 25; # If this exceedes the distance between boundaries smoothing will be poor
my $PASSES = 1; # Must be >= 1
my @protected_points = ();


if ((exists $ARGV[0]) &&
    (defined $ARGV[0])) {
    $P = $ARGV[0];

    unless ($P =~ m/^\d+$/) {
        die 'Provided P ', $P, ' must be a number', "\n";
    }
}


if ((exists $ARGV[1]) &&
    (defined $ARGV[1])) {
    $N = $ARGV[1];

    unless ($N =~ m/^\d+$/) {
        die 'Provided N ', $N, ' must be a number', "\n";
    }
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


warn sprintf('Smoothing boundaries of %d points with linear interpolation over %d points with %d passes and %d protected points', $P, $N, $PASSES, scalar @protected_points), "\n";



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


    # Smooth the middle points
    my $i = 0;
    while ($i < $xcount) {

        my $at_boundary = 0;
        my $btype = 0; # 0: no boundary, 1: boundary-to-left, 2: boundary-to-right
        if ($i - 1 < 0) {
            $at_boundary = 1;
            $btype = 1;
        }

        if ($i + $N >= $xcount) {
            $at_boundary = 1;
            $btype = 2;
        }

        if ($at_boundary == 0) {
            foreach my $prot (@protected_points) {
                if (($xlist[$i - 1] < $prot) &&
                    ($xlist[$i] > $prot)) {
                    $at_boundary = 1;
                    $btype = 1;
                    last;
                }
                if (($xlist[$i] < $prot) &&
                    ($xlist[$i + $N] > $prot)) {
                    $at_boundary = 1;
                    $btype = 2;
                    last;
                }
            }
        }

        if ($at_boundary == 1) {
            my $xsum = 0;
            my $ysum = 0;
            for (my $o = 0; $o < $N; $o++) {
                $xsum += $xlist[$i + $o];
                $ysum += $data_raw{$xlist[$i + $o]};
            }
            my $xhat = $xsum / ($N * 1.0);
            my $yhat = $ysum / ($N * 1.0);

            my $cov = 0; # covariance
            my $var = 0; # variance
            for (my $o = 0; $o < $N; $o++) {
                $cov += ($xlist[$i + $o] - $xhat) * ($data_raw{$xlist[$i + $o]} - $yhat);
                $var += ($xlist[$i + $o] - $xhat) ** 2.0;
            }
            my $bhat = $cov / $var;
            my $ahat = $yhat - ($bhat * $xhat);

            # Now that we have the linear interpolation params bhat and ahat
            # smooth the first or last P points
            for (my $o = 0; $o < $N; $o++) {
                my $lin = 0;
                if ($btype == 1) {
                    if ($o < $P) {
                        $lin = 1;
                    }
                }
                if ($btype == 2) {
                    if ($o >= ($N - $P)) {
                        $lin = 1;
                    }
                }

                if ($lin == 1) {
                    $data_smooth{$xlist[$i + $o]} = $ahat + $bhat * $xlist[$i + $o];
                } else {
                    $data_smooth{$xlist[$i + $o]} = $data_raw{$xlist[$i + $o]};
                }
            }

            $i += $N;

        } else {
            # Just copy this point
            $data_smooth{$xlist[$i]} = $data_raw{$xlist[$i]};

            $i += 1;
        }

    }

    %data_raw = %data_smooth;
}

foreach my $smx (sort {$a <=> $b} keys %data_smooth) {
    print $smx, ' ', sprintf("%.7f", $data_smooth{$smx}), "\n";
}
