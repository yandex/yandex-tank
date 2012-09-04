#!/usr/bin/perl

use strict;
use warnings;

use Time::HiRes qw(sleep);
use IO::Handle;
use Lunapark;

$| = 1; # disable buffering

sub checkReader() {
    my %r;
    open( my $SRC, "<step.conf" ) or die "Cannot open 'step.conf'.";
    while (<$SRC>) {
        $r{ammo_cnt} = $1 if ( $_ =~ /^ammo_cnt=(.+)$/ );
    }
    close($SRC);
    if ( !$r{ammo_cnt} ) {
        open( my $AM, "<ammo_cnt" );
        $_ = <$AM>;
        chomp;
        $r{ammo_cnt} = $_;
        close($AM);
    }
    return \%r;
}

### Return 1 if phantom.log contains 'phantom Exit' in last 5 lines. Otherwise - 0.
sub checkPhantomStop($) {
    my $f = shift;
    if (! -r $f) { return 0; }
    open( my $T, "tail -n 5 $f |" );
    while (<$T>) {
        return 1 if (/phantom Exit/);
        return 1 if (/Test has ended/);
    }
    return 0;
}

### Return line count in file $f
sub getFlines($) {
    my $f = shift;
    open( my $L, "wc -l $f |" );
    if ( <$L> =~ /(\d+).+$f/ ) {
        return $1;
    }
    else {
        return 0;
    }
}

### Return array of last $c lines from file $f
sub getFtail($$) {
    my ( $f, $c ) = @_;
    if (! -r $f) { return 0; }
    open( my $T, "tail -n $c $f | " );
    my @t;
    while (<$T>) {
        push @t, $_;
    }
    return \@t;
}

lp_log("Start");

#my %r = %{checkReader()};
my ( $phantom_stop, $total_lines ) = ( 0, 0 );

my $S;
my $L;
my $flag;

$flag = 1 if ($ARGV[1] && -r $ARGV[1] );
my $chunked_preproc=0;

open( $S, "<$ARGV[0]" ) or die("Have no phout file to read");
open( $L, "<$ARGV[1]" ) if $flag;

while ( 1 ) {
    if ($flag) {
        while (<$L>) {
            print "phantom " . $_;
        }
    }
    
	my $lines_read = 0;
	$chunked_preproc=0;
    read_S: while (<$S>) {
        print $_;

        #	      lp_log($_);
        $total_lines++;

        $lines_read++;

        # 5000 rps is enough to have a break
        if ( $lines_read > 5000 ) {
            lp_log("Break each 5000 lines read");
            $lines_read = 0;
			$chunked_preproc=1;
            last read_S;
        }
    }
    
	sleep(0.01);

    if (!$phantom_stop) {
    $phantom_stop = checkPhantomStop("phantom.log");
        if ( $phantom_stop == 1 ) {
            lp_log("Phantom Stopped");
    	}
    } else {
        last if not $chunked_preproc;
	}
}
    
close($S);

close($L) if $flag;

lp_log("Finish");
