#!/usr/bin/perl

use Lunapark;
use POSIX;
use List::Util qw(max);
use Data::Dumper;
use FileHandle;

use strict;
use warnings;

lp_log("Started");

our $debug           = 1;
our $last_prined_sec = 0;
our @percentiles     = ( 50, 75, 80, 85, 90, 95, 98, 99, 100 );

### Error codes
our %err;
$err{0}  = "No error";
$err{1}  = "phantom.conf not found";
$err{2}  = "error in phantom.conf - timeout error";
$err{3}  = "step.conf is empty";
$err{4}  = "step.conf not found";
$err{5}  = "can't write phout file";
$err{33} = "load-scheme in step.conf is empty";
$err{77} = "unnecessary case in log";
$err{99} = "unknown string";

our %run = ( debug => 1, );

sub dout($) {
    print $_[0] if $run{debug};
}

sub percentile($$) {
    my ( $y, $p ) = @_;
    my @y = sort { $a <=> $b } @$y;
    my $n = int( scalar(@y) * $p ) - 1;
    return $y[$n];
}

sub checkStep($) {
    my ( %cases, @load );
    my $lp = read_conf("lp.conf");
    lp_log( Dumper($lp) );
    while ( $lp->{cases} =~ /'(.*?)'/g ) {
        $cases{ ( $1 ? $1 : "sysempty" ) } = 1;
    }

    if ( !$lp->{steps} ) { lp_log("No steps!"); }
    for ( split( " ", $lp->{steps} ) ) {
        if ( $_ =~ /\((\d+);(\d+)\)/ ) {
            for ( my $count = 0 ; $count < $2 ; $count++ ) {
                push @load, $1;
            }
        }
    }
    while (@load) {
        if ( $load[0] == '0' ) {
            shift @load;
        }
        else {
            last;
        }
    }
    my $detailed = 'interval_real';

    #   print $lp->{detailed_time};
    if ( defined $lp->{detailed_time} && $lp->{detailed_time} ) {
        $detailed = $lp->{detailed_time};
    }
    return ( 0, \@load, \%cases, $lp->{ammo_count}, $detailed );
}

sub checkPhantom($) {

    #   print "Checking Phantom Conf\n";
    my $path = shift;
    my ( $timeout, $terr, $verr, $tverr1, $tverr2, $values ) =
      ( 0, 1, 1, 1, 1, "" );
    open( my $SRC, "<$path/phantom.conf" ) or return 1;
    while (<$SRC>) {
        if ( $_ =~ /timeout = (\d+)(s|)/ ) {
            $timeout = $1 . ( ( $2 eq 's' ) ? "000" : "" );
            $terr = 0;
        }
        if ( $_ =~ /values = \{(.+)\}/ ) {
            my @values = ( 0, split( " ", $1 ) );
            $values = \@values;
            for my $i ( 0 .. $#values ) {
                if ( $values[$i] =~ /(\d+)s/ ) {
                    $values[$i] = $1 . "000";
                }
                if ( $values[$i] == $timeout ) {
                    $tverr1 = 0;
                }
                if ( $values[$i] > $timeout ) {
                    $tverr2 = 0;
                }
            }
            $verr = 0;
        }
    }
    close($SRC);
    if ( $terr || $verr || $tverr1 || $tverr2 ) {
        return 2;
    }
    else {

        #print Dumper($values);
        return ( 0, $values );
    }
}

sub std($$) {
    my ( $y, $m ) = @_;
    my $sum = 0;
    my $len = scalar(@$y);
    for ( my $i = 0 ; $i < $len ; $i++ ) {
        $sum += ( $y->[$i] - $m )**2;
    }

    return sprintf( "%.2f", sqrt( $sum / $len ) );
}

sub printAbout();

sub time_from_ts($) {
    my $ts = shift;
    my ( $sec, $min, $hour, $mday, $mon, $year ) = localtime($ts);
    my $time = sprintf(
        "%d%02d%02d%02d%02d%02d",
        $year + 1900,
        $mon + 1, $mday, $hour, $min, $sec
    );
    return $time;
}

sub check_case($$) {
    my ( $case, $cases ) = @_;
    if ( !$cases->{$case} ) {
        lp_log ( Dumper( \@_ ) );
        lp_log ( "errcode:77 (wrong case!)" );
        exit 1;
    }
}

if (@ARGV) {
    if ( $ARGV[0] =~ /(--help|--about)/ ) {
        print printAbout();
        exit 0;
    }
}

lp_log("Starting preproc...");
my $PATH = ".";
my ( $lastsec, $cur, $seconds, $count, $out, $tag, $ts, $confout, $start, $ts2 )
  = ( 0, 0, 0, 0, "", "", 0, 1, 0, 0 );
my %agg;
my @errs;
my $overall;
my $tot_answ_tmp = 0;

lp_log("Checking preproc.conf... ");

#my $prconf = getconfig("preproc.conf");
my $prconf = read_conf("lp.conf");
our %prconf = %{$prconf};
lp_log("Checking preproc.conf... Done");

lp_log("Checking step.conf... ");
my ( $errstep, $load, $cases, $ammo_cnt, $detailed ) = checkStep($PATH);
lp_log("Checking step.conf... Done");

lp_log("Checking phantom.conf... ");
my ( $errph, $values ) = checkPhantom($PATH);
if ( !$values ) {
    lp_log("Took time periods from lp.conf");
    my @values = ( 0, split( " ", $prconf{time_periods} ) );
    $values = \@values;
}
lp_log("Checking phantom.conf... Done");

if ( !$prconf{preproc_log_name} ) { die("No out file specified"); }
else { lp_log( "Out file:" . $prconf{preproc_log_name} ); }

open( my $DS, ">$prconf{preproc_log_name}" )
  or die "Cannot create '$prconf{preproc_log_name}'.";

if ($errstep) { push @errs, $errstep; }
if ($errph)   { push @errs, $errph; }

my $errs = join( "", sort { $a <=> $b } (@errs) );
my $errcode = ( $errs ? $errs : "0" );

if (@ARGV) {
    if ( $ARGV[0] =~ /(--check|-ch)/ ) {
        print "errcode: $errcode (" . $err{$errcode} . ")\n";
        exit 0;
    }
    if ( $ARGV[0] =~ /(--bunny|-bn)/ ) {
        print
"(\\_/)\n(O.o)\n(> <)  <-- Help Bunny on his way to world domination!\n";
        exit 0;
    }
    if ( $ARGV[0] =~ /--overall=(0|1)/ ) {
        $overall = $1;
        print "Overall: $overall\n";
    }
}

sub printStack($) {
    my $y = shift;
    my @res = grep { $y->{$_} == 1 && $_ } keys %$y;
    @res = sort { $a <=> $b } @res;
    return \@res;
}

sub outputStack($$$$$$$$$$$) {
    my (
        $y,     $d,    $ag,      $prconf,   $cases, $values,
        $start, $load, $errcode, $detailed, $task_data
    ) = @_;
    my $out = '';
    my @outed;
    for ( sort { $a <=> $b } keys %$y ) {

        # Output second.
        if ( $_ > $last_prined_sec ) {
            if ( $y->{$_} ) {
                push @outed, $_;

                my $reqps = (
                    ( defined $load->[ $_ - $start + 1 ] )
                    ? $load->[ $_ - $start + 1 ]
                    : 0
                );
                $reqps = ( ( $errcode == 33 ) ? '-1' : $reqps );

                # Template for empty data. Content.
                my $empty_out = "HTTPcode=200:0\nnetwcode=0:0\n";
                $empty_out .=
                  "answ_time=" . $values->[0] . "-" . $values->[1] . ":0\n";
                $empty_out .= "selfload=0\noutput=0\ninput=0\n";
                for (
                    'interval_real', 'connect_time', 'send_time',
                    'latency',       'receive_time', 'interval_event'
                  )
                {
                    $empty_out .= $_ . "_expect=0\n";
                }
                $empty_out .= $detailed . "_dispersion=0\n";
                for (@percentiles) {
                    $empty_out .= $detailed . "_q" . $_ . "=0\n";
                }

                # Template for empty second. End.
                my $out_end = "delta_plan=0\n===\n";

                if ( defined $ag->{$_} ) {

                    #   if ( defined %{ $ag->{$_} } ) {

                    # Output cases if exists
                    for my $key ( keys %{$cases} ) {
                        $out .= "overall=0\n";
                        $out .= 'time=' . time_from_ts($_) . "\n";
                        $out .=
                          "case=" . ( $key eq 'sysempty' ? '' : $key ) . "\n";
                        $out .= "reqps=$reqps\n";
                        $out .= "tasks=0\n";
                        if ( defined ${ $ag->{$_} }{$key} ) {
                            $out .= printSec( ${ $ag->{$_} }{$key},
                                $values, $prconf, $detailed );
                        }
                        else {
                            $out .= $empty_out;
                        }
                        $out .= $out_end;
                    }

                    # Output data for whole second.
                    $out .= "overall=1\n";
                    $out .= 'time=' . time_from_ts($_) . "\n";
                    $out .= "case=\n";
                    $out .= "reqps=$reqps\n";
                    if ( $task_data->{$_} ) {
                        $out .= "tasks=" . $task_data->{$_} . "\n";
                    }
                    else {
                        $out .= "tasks=0\n";
                    }
                    $out .= printSec( \%{ ${ $ag->{$_} }{overall} },
                        $values, $prconf, $detailed );
                    $out .= "===\n";
                    $last_prined_sec = $_;
                }
                else {

                    # Empty second overall = 0
                    for my $key ( keys %{$cases} ) {
                        $out .= "overall=0\n";
                        $out .= 'time=' . time_from_ts($_) . "\n";
                        $out .=
                          "case=" . ( $key eq 'sysempty' ? '' : $key ) . "\n";
                        $out .= "reqps=$reqps\n";
                        $out .= "tasks=0\n";
                        $out .= $empty_out . $out_end;
                    }

                    # Empty second overall = 1
                    $out .= "overall=1\n";
                    $out .= 'time=' . time_from_ts($_) . "\n";
                    $out .= "case=\n";
                    $out .= "reqps=$reqps\n";
                    if ( $task_data->{$_} ) {
                        $out .= "tasks=" . $task_data->{$_} . "\n";
                    }
                    else {
                        $out .= "tasks=0\n";
                    }
                    $out .= $empty_out . $out_end;
                }
                $d->{$_} = 1;
                $last_prined_sec = $_;
            }
        }
    }
    return ( $d, $out, \@outed );
}

sub printSec($$$$) {
    my ( $ref, $v, $prconf, $detailed ) = @_;
    my $out = '';

    # Calculating std, mean, self-load to %.2f format
    my $out_expect = "";
    for my $key ( sort keys %{$ref} ) {
        if ( $key =~ /(.+?)_expect/ ) {
            my $terme = $1 . "_expect";
            $ref->{$terme} = 0 + sprintf( "%.2f", $ref->{$terme} );
            $out_expect .= $terme . '=' . $ref->{$terme} . "\n";

            if ( $1 eq $detailed ) {
                my $termd = $1 . "_dispersion";
                $ref->{$termd} =
                  0 + std( \@{ $ref->{ $1 . "_values" } }, $ref->{$terme} );
                $out_expect .= $termd . '=' . $ref->{$termd} . "\n";
            }
        }
    }

    $ref->{selfload} = 0 + sprintf( "%.2f", $ref->{selfload} / $ref->{count} );

    # Output http codes if tank type: http (1)
    $out .= proutCodes( $ref->{http}, 'http' ) if $prconf->{tank_type} ne '2';

    # Output net codes
    $out .= proutCodes( $ref->{net}, 'net' );

    # Output time intervals
    if ( $ref->{diap} ) {
        for ( my $i = 0 ; $i < scalar( @{ $ref->{diap} } ) ; $i++ ) {
            if ( defined $ref->{diap}->[$i] ) {
                $out .=
                    "answ_time="
                  . $values->[$i] . "-"
                  . $values->[ $i + 1 ] . ":"
                  . $ref->{diap}->[$i] . "\n";
            }
        }
    }
    else {
        $out .= "answ_time=" . $values->[0] . "-" . $values->[1] . ":0\n";
    }

    # Output selfload, size in, size out
    $out .= 'selfload=' . $ref->{selfload} . "%\n";
    $out .= 'output=' . $ref->{sizeout} . "\n";
    $out .= 'input=' . $ref->{sizein} . "\n";

    $out .= $out_expect;

    # Calculating percentiles
    my $ref_detailed_values = $ref->{ $detailed . "_values" };
    my @sorted_detailed_values = sort { $a <=> $b } @$ref_detailed_values;
    for (@percentiles) {
        my $q = 0 + sprintf( "%.2f",
            $sorted_detailed_values[
              int( scalar(@sorted_detailed_values) * $_ / 100 ) - 1 ] );
        $out .= $detailed . "_q$_=" . $q . "\n";
    }
    return $out;
}

sub proutCodes($$) {
    my ( $y, $t ) = @_;
    my ( $tb, $out ) = ( 0, '' );
    $t = 'netwcode' if $t eq 'net';
    ( $t, $tb ) = ( 'HTTPcode', '200' ) if ( $t eq 'http' );
    if ($y) {
        for ( keys %{$y} ) {
            $out .= "$t=$_:" . $y->{$_} . "\n";
        }
    }
    else {
        $out .= "$t=$tb:0\n";
    }
    return $out;
}

sub show($) {
    my $y   = shift;
    my $out = '';
    for ( sort { $a <=> $b } keys %{$y} ) {
        $out .= $_ . " " if ( $y->{$_} );
    }
    return $out;
}

#open(my $SRC, ">$ARGV[1]");
my ( $fsec, $cur_sec, $prev_sec, $new_sec, $WAITTIME, $add_prev ) =
  ( 0, 0, 0, 0, 100000, 0 );
my $jump          = 0;
my %out_stack     = ();
my %done          = ();
my $last_agg      = "";
my $prev_last_agg = "";
my $wait_sec      = 0;
my $wait_time     = 0;

# debug
my ( $wait, $previous ) = ( 0, 0 );
lp_log("Reading STDIN... ");

my ( $task_ts, %task_data );

# my $phout_parse_timings = '(\d+)\.(\d+)\s+(.*)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)';
# my $regexp_phout_parse_timings = '(\d+)\.(\d+)\s+(.*)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)';
# my $regexp_time = 'time\s+(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})';
# my $regexp_phantom = '^phantom';

# my %dt;

#my %dt =
#(
#  'interval_real'  => $4,
#  'connect_time'   => $5,
#  'send_time'      => $6,
#  'latency'        => $7,
#  'receive_time'   => $8,
#  'interval_event' => $9,
#);

#my %ot = (
#    'sizeout' => $10,
#    'sizein'  => $11,
#    'net'     => $12,
#    'http'    => $13,
#);

if ($confout) {
    lp_log("Print config information... ");
    $out .= "tank_type=$prconf{tank_type}\n";
    $out .= "job_n=$prconf{jobno}\n" if $prconf{jobno};
    print $DS $out;
    $confout = 0;
}

lp_log (Dumper(\%ENV));
    
while (<STDIN>) {
	if ($ENV{'DEBUG'}) { lp_log("Read line: $_"); }

    #lp_log("Iteration: $tot_answ_tmp ... ");

    # Parse phantom stdout
#    if ( substr( $_, 0, 7 ) eq 'phantom' ) {
     if ( $_ =~ /phantom/o ) {
        if ( $_ =~ /time\s+(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})/o )
        {
            $task_ts = mktime( $6, $5, $4, $3, $2 - 1, $1 - 1900 );
        }
        elsif (/tasks\s+(\d+)/) {
            if ($task_ts) {
                $task_data{$task_ts} = $1;
                $task_ts = '';
            }
        }
    }
    # Parse phantom phout log
    else {
        my @matched_vars;
        #print $_;
        unless ( @matched_vars = ($_ =~ /^(\d{10})\.(\d+)\s+(\S*)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)/o)
          )
        {
            print " wrong line: $_\n";
            lp_log( "ERROR: wrong line: " . $_ );
            print $errcode = 99;
            #print Dumper($cases);
            $_ =
                "0000000000.999\t"
              . ( keys %$cases )[0]
              . "\t1\t1\t1\t1\t1\t1\t1\t1\t999\t999";
            @matched_vars = ($_ =~ /^(\d{10})\.(\d+)\s+(\S*)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)/o);
        }
###        else {    # но по-моему, тут не нужен else

            $tot_answ_tmp++;

            # Detailed time values
            #	%dt = (
            #	    'interval_real'  => $4,
            #	    'connect_time'   => $5,
            #	    'send_time'      => $6,
            #	    'latency'        => $7,
            #	    'receive_time'   => $8,
            #	    'interval_event' => $9
            #	);

            my (
                $dt_interval_real, $dt_connect_time, $dt_send_time,
                $dt_latency,       $dt_receive_time, $dt_interval_event,
                $ot_sizeout,       $ot_sizein,       $ot_net,
                $ot_http,          $ms
              )
              = ( $matched_vars[3],  $matched_vars[4],  $matched_vars[5],
		  $matched_vars[6],  $matched_vars[7],  $matched_vars[8],
		  $matched_vars[9],  $matched_vars[10], $matched_vars[11],
		  $matched_vars[12], 1000 * $matched_vars[1] + $matched_vars[4] );

            #	my $ms = 1000 * $2 + $5;

            my ( $delta, $ts ) = ( $ms % 1000000, $matched_vars[0] + int( $ms / 1000000 ) );

            $wait_time = 1000000 * ( $ts - $wait_sec ) + $delta;

            if ( $ts != $cur_sec ) {
                if ( $ts == $prev_sec ) {
                    $add_prev = 1;
                }

                if ( $ts > $cur_sec ) {
                    $new_sec  = 1;
                    $wait_sec = $cur_sec;
                    $prev_sec = $cur_sec;
                    $cur_sec  = $ts;
                }
            }

            #     my $cur_prevd = 0;
            if (   ( $cur_sec - $prev_sec > 1 )
                && ( $prev_sec > 0 )
                && ( $cur_sec > 0 ) )
            {

                #    $cur_prevd = $cur_sec - $prev_sec;
                for ( my $i = $prev_sec + 1 ; $i < $cur_sec ; $i++ ) {
                    $out_stack{$i} = 1;
                }
                $jump = 1;
            }

            if ( $tot_answ_tmp == 1 ) {
                ( $new_sec, $start ) = ( 0, $ts );
            }

            if ( $new_sec == 1 && $ts == $cur_sec ) {
                if ( $jump == 1 ) {
                    $out_stack{ $prev_sec - 1 } = 1;
                    $out_stack{$prev_sec} = 1;
                }

                if ( ( $wait_time > 1000000 + $WAITTIME ) ) {
                    $out_stack{$prev_sec} = 1;
                    $new_sec = 0;
                }
                else {
                    $new_sec = 1;
                }
            }

            if ( $new_sec == 0 && $ts < $cur_sec ) {
                $ts = $cur_sec;
            }

            $tag = ( $matched_vars[2] ? $matched_vars[2] : "sysempty" );
            if ( scalar keys %$cases > 1 ) {

                #            check_case( $tag, $cases );
                unless ( $cases->{$tag} ) {
                    print Dumper( \@_ );
                    print "errcode:77 (wrong case!)\n";
                    exit 1;
                }
            }

            ### Calculating non-time values
###     for my $v ( $tag, 'overall' ) {

            $agg{$ts}{$tag}{count}++;
            $agg{$ts}{overall}{count}++;

            my $ref_agg_ts_tag = $agg{$ts}{$tag};
            my $ref_agg_ts_all = $agg{$ts}{overall};

            #   $ref_agg_ts_tag->{count}++;
            #        $ref_agg_ts_all->{count}++;

            # Calculating input/output
            $ref_agg_ts_tag->{sizein}  += $ot_sizein;
            $ref_agg_ts_tag->{sizeout} += $ot_sizeout;
            $ref_agg_ts_all->{sizein}  += $ot_sizein;
            $ref_agg_ts_all->{sizeout} += $ot_sizeout;

            # Calculating httpq codes
            if ($ot_http) {
                $ref_agg_ts_tag->{http}{$ot_http}++;
                $ref_agg_ts_all->{http}{$ot_http}++;
            }

            # Calculating net codes
            $ref_agg_ts_tag->{net}{$ot_net}++;
            $ref_agg_ts_all->{net}{$ot_net}++;

            # Calculating selfload
            if ($dt_interval_real) {
                my $tmp_self_load =
                  ( ( $dt_interval_real - $dt_interval_event ) /
                      $dt_interval_real ) * 100;
                $ref_agg_ts_tag->{selfload} += $tmp_self_load;
                $ref_agg_ts_all->{selfload} += $tmp_self_load;
            }
            else {
                $ref_agg_ts_tag->{selfload} += 100;
                $ref_agg_ts_all->{selfload} += 100;
                $ref_agg_ts_tag->{ie_null}++;
                $ref_agg_ts_all->{ie_null}++;
            }

            # Time periods distribution
            my $is_interval_found = 0;
            for ( my $i = 0 ; $i < scalar(@$values) - 1 ; $i++ ) {
                if ( $dt_interval_real < 1000 * $values->[ $i + 1 ] ) {
                    $ref_agg_ts_tag->{diap}->[$i]++;
                    $ref_agg_ts_all->{diap}->[$i]++;
                    $is_interval_found = 1;
                    last;
                }
            }
            unless ($is_interval_found) {
                lp_log("WARNING: interval_real > timeout, assigning to last interval.  interval_real = $dt_interval_real "                );
                $agg{$ts}{$tag}{diap}->[ scalar(@$values) - 2 ]++;
                $ref_agg_ts_all->{diap}->[ scalar(@$values) - 2 ]++;
            }
###     }

            ### Calculating mean time values
#       $t = interval_real connect_time send_time latency receive_time interval_event
#	$v = $tag 'overall'
###	for my $t ( keys %dt ) {
###	   for my $v ( $tag, 'overall' ) {

            # $ref_agg_ts_tag = $agg{$ts}{$tag};
            my $cnt = $ref_agg_ts_tag->{count};

            # First value
            if ( $cnt == 1 ) {
                $ref_agg_ts_tag->{interval_real_expect}  = $dt_interval_real;
                $ref_agg_ts_tag->{connect_time_expect}   = $dt_connect_time;
                $ref_agg_ts_tag->{send_time_expect}      = $dt_send_time;
                $ref_agg_ts_tag->{latency_expect}        = $dt_latency;
                $ref_agg_ts_tag->{receive_time_expect}   = $dt_receive_time;
                $ref_agg_ts_tag->{interval_event_expect} = $dt_interval_event;

                # Recursive mean for other values
            }
            else {
                my $count_count1 = $cnt - 1;
                $ref_agg_ts_tag->{interval_real_expect} =
                  ( $count_count1 * $ref_agg_ts_tag->{interval_real_expect} +
                      $dt_interval_real ) / $cnt;
                $ref_agg_ts_tag->{connect_time_expect} =
                  ( $count_count1 * $ref_agg_ts_tag->{connect_time_expect} +
                      $dt_connect_time ) / $cnt;
                $ref_agg_ts_tag->{send_time_expect} =
                  ( $count_count1 * $ref_agg_ts_tag->{send_time_expect} +
                      $dt_send_time ) / $cnt;
                $ref_agg_ts_tag->{latency_expect} =
                  ( $count_count1 * $ref_agg_ts_tag->{latency_expect} +
                      $dt_latency ) / $cnt;
                $ref_agg_ts_tag->{receive_time_expect} =
                  ( $count_count1 * $ref_agg_ts_tag->{receive_time_expect} +
                      $dt_receive_time ) / $cnt;
                $ref_agg_ts_tag->{interval_event_expect} =
                  ( $count_count1 * $ref_agg_ts_tag->{interval_event_expect} +
                      $dt_interval_event ) / $cnt;
            }

            # Save all exact values (for calculating std)
            push @{ $ref_agg_ts_tag->{interval_real_values} },
              $dt_interval_real;
            push @{ $ref_agg_ts_tag->{connect_time_values} }, $dt_connect_time;
            push @{ $ref_agg_ts_tag->{send_time_values} },    $dt_send_time;
            push @{ $ref_agg_ts_tag->{latency_values} },      $dt_latency;
            push @{ $ref_agg_ts_tag->{receive_time_values} }, $dt_receive_time;
            push @{ $ref_agg_ts_tag->{interval_event_values} },
              $dt_interval_event;

            #		$ref_agg_ts_tag = $agg{$ts}{overall};
            $cnt = $ref_agg_ts_all->{count};
            if ( $cnt == 1 ) {
                $ref_agg_ts_all->{interval_real_expect}  = $dt_interval_real;
                $ref_agg_ts_all->{connect_time_expect}   = $dt_connect_time;
                $ref_agg_ts_all->{send_time_expect}      = $dt_send_time;
                $ref_agg_ts_all->{latency_expect}        = $dt_latency;
                $ref_agg_ts_all->{receive_time_expect}   = $dt_receive_time;
                $ref_agg_ts_all->{interval_event_expect} = $dt_interval_event;

                # Recursive mean for other values
            }
            else {
                my $count_count1 = $cnt - 1;
                $ref_agg_ts_all->{interval_real_expect} =
                  ( $count_count1 * $agg{$ts}{overall}{interval_real_expect} +
                      $dt_interval_real ) / $cnt;
                $ref_agg_ts_all->{connect_time_expect} =
                  ( $count_count1 * $agg{$ts}{overall}{connect_time_expect} +
                      $dt_connect_time ) / $cnt;
                $ref_agg_ts_all->{send_time_expect} =
                  ( $count_count1 * $agg{$ts}{overall}{send_time_expect} +
                      $dt_send_time ) / $cnt;
                $ref_agg_ts_all->{latency_expect} =
                  ( $count_count1 * $agg{$ts}{overall}{latency_expect} +
                      $dt_latency ) / $cnt;
                $ref_agg_ts_all->{receive_time_expect} =
                  ( $count_count1 * $agg{$ts}{overall}{receive_time_expect} +
                      $dt_receive_time ) / $cnt;
                $ref_agg_ts_all->{interval_event_expect} =
                  ( $count_count1 * $agg{$ts}{overall}{interval_event_expect} +
                      $dt_interval_event ) / $cnt;
            }

            push @{ $ref_agg_ts_all->{interval_real_values} },
              $dt_interval_real;
            push @{ $ref_agg_ts_all->{connect_time_values} }, $dt_connect_time;
            push @{ $ref_agg_ts_all->{send_time_values} },    $dt_send_time;
            push @{ $ref_agg_ts_all->{latency_values} },      $dt_latency;
            push @{ $ref_agg_ts_all->{receive_time_values} }, $dt_receive_time;
            push @{ $ref_agg_ts_all->{interval_event_values} },
              $dt_interval_event;

###	    }
###       }
###        }
    }

    my ( $status, $s, $d, $out, $outed ) = (0);
    if (%out_stack) {
        $s = printStack( \%out_stack );
        ( $d, $out, $outed ) = outputStack(
            \%out_stack, \%done,    \%agg,  \%prconf,
            $cases,      $values,   $start, $load,
            $errcode,    $detailed, \%task_data
        );
        $status = 1;

        print $DS $out;
        $DS->autoflush(1);
    }

    if ($status) {
        for my $ot (@$outed) {
            delete $agg{$ot};
            delete $out_stack{$ot};
            delete $done{$ot};
        }

        for my $os ( keys %out_stack ) {
            if ( $os < $last_prined_sec ) {
                delete $out_stack{$os};
            }
        }
    }
    $add_prev = 0;
}

if ( $new_sec == 1 ) {
    $out_stack{$prev_sec} = 1;
}

$out_stack{$cur_sec} = 1;

my ( $d, $out1, $outed ) = outputStack(
    \%out_stack, \%done, \%agg,    \%prconf,  $cases, $values,
    $start,      $load,  $errcode, $detailed, \%task_data
);
if ($out1) {
    sleep(0.1);
}

print $DS $out1;
$DS->autorflush(1);

#print $out1;

sub printAbout() {
    my ( @about, @pr );
    $pr[0] = "                                 #############################";
    $pr[1] = "                                 ######## Preprocessor #######";
    push @about, "_____________________\$\$\$\n",
      "____________________\$___\$\n", "_____________________\$\$\$\n",
      "_____________________\$_\$\n",  "_____________________\$_\$\n",
      "___________________\$\$\$_\$\$\$\n",
      "_________________\$\$__\$\$\$__\$\$\$\n",
      "_______________\$\$__\$\$\$\$\$\$\$___\$\n",
      "______________\$_______________\$\n",
      "_____________\$_________________\$\n",
      "_____________\$_________________\$\n",
      "_____________\$_____\$\$\$\$\$\$\$\$\$\$\$\$\$\$\$\n",
      "_____________\$____\$_______________\$\n",
      "_____________\$____\$___\$\$\$\$\$\$\$\$\$\$\$\$\$\n",
      "_____________\$___\$___\$___________\$\$\$\n",
      "_____________\$___\$___\$_\$\$\$___\$\$\$__\$\$\n",
      "_____________\$___\$___\$_\$\$\$___\$\$\$__\$\$\n",
      "_____________\$___\$___\$___________\$\$\$\n",
      "_____________\$____\$___\$\$\$\$\$\$\$\$\$\$\$\$\$\n",
      "_____________\$_____\$\$\$\$\$\$\$\$\$\$\$\$\$\$\n",
      "_____________\$_________________\$\n",
      "_____________\$____\$\$\$\$\$\$\$\$\$\$\$\$\$\$\n",
      "_____________\$___\$__\$__\$__\$__\$$pr[0]\n",
      "_____________\$__\$\$\$\$\$\$\$\$\$\$\$\$\$\$$pr[1]\n",
      "_____________\$__\$___\$__\$__\$__\$$pr[0]\n",
      "_____________\$___\$\$\$\$\$\$\$\$\$\$\$\$\$\$\$\n",
      "____________\$\$\$_________________\$\$\$\n",
      "__________\$\$___\$\$\$_________\$\$\$\$\$___\$\$\n",
      "________\$\$________\$\$\$\$\$\$\$\$\$__________\$\$\$\n",
      "_______\$__\$\$_____________________\$\$\$\$___\$\$\n",
      "____\$\$\$\$\$___\$\$\$\$\$\$\$\$______\$\$\$\$\$\$\$_______\$_\$\n",
      "__\$______\$\$_________\$\$\$\$\$\$______________\$_\$\$\n",
      "_\$____\$____\$____________________________\$_\$_\$\n",
      "_\$_____\$___\$______________\$\$\$\$\$\$\$\$\$\$\$___\$_\$_\$\$\n",
      "_\$\$\$____\$___\$__\$\$\$\$\$\$\$\$\$\$\$\$__________\$___\$_\$_\$\$\n",
      "\$___\$\$\$\$____\$__\$_____________________\$___\$_\$\$_\$\n",
      "\$\$\$____\$___\$\$__\$_____________________\$\$__\$_\$__\$\n",
      "\$___\$__\$__\$\$___\$______________________\$__\$\$\$__\$\n",
      "\$_____\$\$_\$\$____\$_______________\$\$\$____\$__\$_\$__\$\n";
    for (@about) {
        print $_;
        sleep(0.1);
    }
}
