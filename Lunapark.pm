package Lunapark;

require Exporter;
   @ISA = "Exporter";
   @EXPORT = qw(formatDate formatFn lp_log sleep gettimeofday getconfig frps time2sec frps_cut const_f frps_real_fps move_logs MinSec getTankAliaces formTD curLPproc UserDialog UserDialogSymbol getlocks lp_warn lp_big_warn format_bytes terminal_size formatTS lp_conf save_conf read_conf update_conf update_value_conf parse_monitoring_config);

use warnings;
use strict;

use Term::ReadKey;
use Time::HiRes qw(sleep gettimeofday);
use Time::Local;
use Config::General;
use Term::ANSIColor;
use Data::Dumper;
use XML::Simple;

##################
### Date Formating

###### Format for logs
sub formatDate($) {
   my $t = shift;
   my ($sec,$min,$hour,$mday,$mon,$year,$wday,$yday,$isdst) = localtime($t);
   return sprintf("%04d-%02d-%02d %02d:%02d:%02d",$year+1900,$mon+1,$mday,$hour,$min,$sec);
}

###### Format for filename
sub formatFn($) {
   my $t = shift;
   my ($sec,$min,$hour,$mday,$mon,$year,$wday,$yday,$isdst) = localtime($t);
   return  sprintf("%d%02d%02d-%02d%02d%02d", $year+1900, $mon+1, $mday, $hour, $min, $sec);
}

sub formatTS($)  {
   my $t = shift;
   my $time;
   if ($t =~ /(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})/) {
      $time = timelocal($6, $5, $4,$3, $2-1, $1);
   }
   return $time;
}

###### Format for elapsed/remaining time
sub MinSec($$$) {
   ($_, my $fmsec, my $frmt)=@_;
   my $pref = "";
   $pref = "-" if $_ < 0;
   $_ = abs($_);
   my $res = '';
   my $hour = int($_/3600000);
   $_ -= $hour*3600000;
   if ($hour != 0) {
      $res .= $hour.'h';
   }
   my $min = int($_/60000);
   $_ -= $min*60000;
   if ($min!=0) {
      $res .= $min.'m';
   }
   my $sec=int($_/1000);
   if (not $fmsec) {
      if ( ($_-$sec*1000) > 500) {
	 $sec++;
      }
   }
   if ($sec != 0) {
      $res .= $sec.'s';
   }
   my $msec = $_-$sec*1000;
   if (($msec != 0)&&($fmsec)) {
      if ($frmt != 0) {
	 $res .= ":";
      }
      $res .= substr('00'.$msec, length('00'.$msec)-3);
   }
   if ($res eq '') {
      $res = '000';
   }
   if ($frmt !=0 ) {
      $res = sprintf "%2.2d:%2.2d:%2.2d", $hour, $min, $sec;
      if ($fmsec) {
	 $res .= sprintf ":%3.3d",$msec;
      }
   }
   return $pref.$res;
}

####################
### Output Formating

sub formTD($$) {
   my ($l, $d) = @_;
   my $left = int(($l-length($d))/2);
   my $right = $l - length($d) - $left;
   return (" "x$left).$d.(" "x$right);
}

###################
#### Interactive

sub UserDialog($) {
   my $f = shift;
   print $f;
   my $str = <STDIN>;
   chomp($str);
   return $str;
}

sub UserDialogSymbol($) {
   my $f = shift;
   print $f;
   ReadMode 'cbreak';
   my $key = ReadKey(0);
   ReadMode 'normal';
   print "\n";
   return $key;
}


##################
#### System

sub getTankAliaces() {
   my %al = ();
   my $t = `hostname -f`;
   chomp($t);
   my $ping = `ping $t -c 1`;
   if ($ping =~ /^PING $t \((.+?)\)/) {
      $al{$1} = $t;
   }
   $t =~ s/\./-dummy\./;
   $ping = `ping $t -c 1`;
   if ($ping =~ /^PING $t \((.+?)\)/) {
      $al{$1} = $t;
   }
   return \%al;
}

### List of all processes running by current Lunapark
sub curLPproc($); # prototype
sub curLPproc($) {
   my $pid = shift;
   my $lpdec = 0;
   open(my $PS, "ps uh --ppid $pid |");
   my @kill = ();
   while(<$PS>) {
      if ($_ =~ /^\S+\s+(\S+)\s+/) {
            lp_log("Detected process to kill: ".$_);
            unshift @kill, $1;
            for my $cpid (@{curLPproc($1)}) {
                unshift @kill, $cpid;
            }
      } else {
        lp_log("Skipping line: ".$_);
      }
   }
   close($PS);
   return \@kill;
}

sub lp_conf($) {
   my $ref = shift;
   open(my $LP, ">>lp.conf");
      print $LP $_." = ".$ref->{$_}."\n" for (keys %{$ref});
   close($LP);
}

sub save_conf($) {
   lp_log("Saving lp.conf");
   my $ref = shift;
   open(my $LP, ">lp.conf");
      for (keys %{$ref}) {
         next if $_ eq '[DEFAULT]';
         unless(ref($ref->{$_})) {
            print $LP $_." = ".$ref->{$_}."\n";
         }
      }
   close($LP);
}

sub update_conf($$) {
   my ($pri, $sec) = @_;
   for (keys %{$sec}) {
      $pri->{$_} = $sec->{$_} unless defined $pri->{$_};
   }
   return $pri;
}

sub update_value_conf($$) {
   my ($pri, $sec) = @_;
   for (keys %{$sec}) {
      if ((not defined $pri->{$_}) || ($pri->{$_} ne $sec->{$_})) {
         $pri->{$_} = $sec->{$_};
      }
      print $_."\n" if not defined $sec->{$_};
   }
   return $pri;
}

### Logging
sub lp_log($)   {
   my $str = shift;
   chomp $str;
   my ($sec, $microsec, $ts) = (gettimeofday, time);
   my $mls = $microsec/1000000;
   my $ms = sprintf("%03d", int(1000*$mls));
   $0 =~ /^.+\/(.+?)$/;
   my $script = $1;
   if ($sec && $ms && $script && $str) {
      open(my $DEBUG, ">>lunapark.log") or die "Cannot open log-file\n";
	   print $DEBUG "[".formatDate($sec).".$ms] [$script] ".$str."\n";
      close($DEBUG);
   } else {
   		print $str."\n";
        print "Warning: Can't open log file [$sec / $ms / $script / $str]\n";
   }
}

sub move_logs($) {
   my $i = shift;
   if (!$i->{jobno}) {
        lp_log("No jobno, skip move logs");
        return;
   }

   my $prefix = "$i->{jobno}_$i->{fn}";
   my $lf = "logs/$i->{jobno}";

   mkdir("logs") unless (-r 'logs');
   mkdir($lf) unless (-r $lf);

	lp_log("Moving logs to $lf");
   `mv $i->{phantom_log_name}   $lf/phout_$prefix.txt` if -r "$i->{phantom_log_name}";
   `mv $i->{preproc_log_name}   $lf/prepr_$prefix.txt` if -r "$i->{preproc_log_name}";
   `mv $i->{answ_log_name}   $lf/answ_$prefix.txt`     if $i->{writelog} && -r $i->{answ_log_name};
#   `mv $i->{script_log}      $lf/script_$prefix.log`   if $i->{script} && -r $i->{script_log};

   `cp $i->{config} $lf/load.conf` if -r "$i->{config}";
   `cp lp.conf $lf/lp.conf` if -r "lp.conf";
   `mv lunapark_error.log $lf/lunapark_error_$i->{jobno}.log` if -r "lunapark_error.log";
   `mv lunapark.log $lf/lunapark_$i->{jobno}.log` if -r "lunapark.log";
   `mv phantom.conf $lf/phantom_$i->{jobno}.conf` if -r "phantom.conf";
   `mv sql.log $lf/sql.log` if -r "sql.log";
   `mv phantom.log $lf/phantom_$i->{jobno}.log` if -r "phantom.log";
   `mv fantom-debug.log $lf/fantom-debug.log` if -r "fantom-debug.log";
   `mv phantom_stat.log $lf/phantom_stat_$i->{jobno}.log` if -r "phantom_stat.log";

   if (-r 'monitoring.log') {
       `mv monitoring.log $lf/monitoring_$i->{jobno}.log`;
   }
 
  if (`ls monitoring_agent_*.log 2> /dev/null| wc -l`) {
      `mv monitoring_agent_*.log $lf/ 2> /dev/null`;
  } 

   if (-r "monitoring_$i->{jobno}.data") {
       `mv monitoring_$i->{jobno}.data $lf/monitoring_$i->{jobno}.data`;
   }
   if (defined $i->{monitoring_tmp} and -r $i->{monitoring_tmp}) {
       `mv $i->{monitoring_tmp} $lf/monitoring_$i->{jobno}.conf`;
   }
}

### Config Parsing
sub getconfig($) {
   return {} unless (-r $_[0]);
   my $conf = new Config::General($_[0]);
   my %conf = $conf->getall;
   my @loads = ();
   if (defined $conf{load}) {
      if (ref($conf{load}) eq "ARRAY") {
         for my $load (@{$conf{load}}) {

            my @tmp = split("[)][ ]+", $load);
            if (scalar(@tmp) == 1) {
               push @loads, @tmp;
            } else {
               push @loads, $tmp[$_].")" for (0 .. $#tmp-1);
               push @loads, $tmp[$#tmp];
            }
         }
      } else {
         my @tmp = split("[)][ ]+", $conf{load});
         if (scalar(@tmp) == 1) {
            push @loads, @tmp;
         } else {
            push @loads, $tmp[$_].")" for (0 .. $#tmp-1);
            push @loads, $tmp[$#tmp];
         }
      }
      @{$conf{loads}} = @loads;
      $conf{loads_str} = join(";", @loads);
   }
   return \%conf;
}

sub read_conf($) {
   die "Cannot open config '$_[0]'" unless (-r $_[0]);
   my $conf = new Config::General($_[0]);
   my %conf = $conf->getall;
   return \%conf;
}

###
sub getlocks() {
   my @ts = glob("/var/lock/lunapark*.lock");
   return \@ts;
}

###### [stepper.pl] functions
sub time2sec ($) {
   my $t = shift;
   if ($t =~ /(\d+)h$/) {
      return $1*3600;
   } elsif ($t =~ /(\d+)(m|min)$/)   {
      return $1*60;
   } elsif ($t =~ /(\d+)(s|sec|)$/) {
      return $1;
   }
   die "Wrong time format\n";
}

sub countAmmo($)  {
   my $a = shift;
   my $cnt = 0;
   while($a =~ /(\d+)\s+(\d+)\n/g)  {
      $cnt += $1*$2;
   }
   return $cnt;
}

### const fractional scheme from load.conf
sub const_f ($$) {
   my ($req, $dur_orig) = @_;
   if ($req =~ /(\d+)\/(\d+)/ and $dur_orig) {
      my ($a, $b, $dur, $e) = ($1, $2, time2sec($dur_orig), int($1/$2));
      my $fr = sprintf("%.3f", $1/$2);
      $a = $a % $b;
      $req = "$a/$b";
      my $ls = "$dur,const_f,$fr,$fr,($req,$dur_orig)\n";
      my $out = "";
	   my $tail = $dur % $b;
	   for (my $i = 1; $i <= int($dur/$b); $i++)  {
	      $out .= frps($req);
	   }
	   $out .= frps_cut($tail, $req) if $tail;
	   if ($e > 0)	{
	      $out = frps_expand($out, $e);
	   }
	   return ($out, $ls, countAmmo($out));
   } else {
      die "error in 'const_f' function. rps:$req, duration:$dur_orig\n";
   }
}

### fractional rps
sub frps_print($$) {
   my ($s, $t) = @_;
   my $out = "";
   for (my $i = 1; $i<= $t; $i++) {
      $out .= "$s 1\n";
   }
   return $out;
}

sub frps_vv($)	{
   return '0' if $_[0] eq '1';
   return '1' if $_[0] eq '0';
}

sub frps_scheme($) {
   my $c = shift;
   my $out = "";
   for (my $i = 1; $i <= $c->{chunks}; $i++) {
      $out .= frps_print($c->{first}, $c->{per_chunk});
      $c->{num1} -= $c->{per_chunk};
      $out .= frps_print(frps_vv($c->{first}), 1);
      $c->{num0} --;
   }
   $out .= frps_print($c->{first}, $c->{num1});
   $out .= frps_print(frps_vv($c->{first}), $c->{num0});
}

sub frps($)	{
   my $f = shift;
   if ($f =~ /(\d+)\/(\d+)/)  {
      my %c = ();
      my ($num1, $num0) = ($1, $2-$1);
      if ($num1 > $num0) {
	 ($c{per_chunk}, $c{space}, $c{first}) = (int($num1/$num0), $num1%$num0, '1');
	 $c{chunks} = int($num0);
	 ($c{num1}, $c{num0}) = ($num1, $num0);
      } else {
	 ($c{per_chunk}, $c{space}, $c{first}) = (int($num0/$num1), $num0%$num1, '0');
         $c{chunks} = int($num1);
	 ($c{num1}, $c{num0}) = ($num0, $num1);
      }
      return frps_scheme(\%c);
   } else {
      return "0"; 
   }
}

sub frps_cut($$)	  {
   my ($c, $r) = @_;
   if ($r =~ /(\d+)\/(\d+)/)  {
      my ($a, $b)  = ($1, $2);
      if ($c < $2) {
	 my ($frps, $out, $cnt) = (frps($r), "", 0);
	 while ($frps =~ /(\d+) (\d+)\n/g) {
	    $cnt++;
	    $out .= "$1 $2\n";
	    last if $cnt == $c;
	 }
	 return $out;
      } else {
	 die "Wrong cut:$c for rps $r\n";
      }
   } else {
      die "Wrong rps format in 'frps_cut' function\n";
   }
}

### Expand rps<1 to rps>1
sub frps_expand($$) {
   my ($s, $e) = @_;
   my $out = "";
   while ($s =~ /(\d+) (\d+)\n/g) {
      $out .= ($1+$e)." ".$2."\n";
   }
   return $out;
}

### Comparison of scheme rps and real rps
sub frps_real_fps($$) {
   my ($s, $r) = @_;
   my ($reqs, $dur) = 0;
   while ($s =~ /(\d+) (\d+)\n/g) {
      $reqs += $1;
      $dur += $2;
   }
   my $real_rps = $reqs/$dur;
   $r =~ /(\d+)\/(\d+)/;
   my $rps = $1/$2;
   return sprintf("%.6f", 100*abs($real_rps - $rps)/($rps));
}

sub lp_warn($) {
   print color 'yellow';
   print $_[0]."\n";
   print color 'reset';
}

sub lp_big_warn {
   lp_warn("########################");
   lp_warn("####### Warning ########");
   lp_warn("########################");
}

sub format_bytes($) {
   my $b = shift;
   my @suff = ("B", "K", "M", "G", "T", "P", "E", "Z", "Y");
   my $prev = $b.$suff[0];
   for (1 .. $#suff) {
      my $a = sprintf("%.1f", $b/(1024**$_));
      if ($a > 1) {
         $prev = $a.$suff[$_];
         next;
      } else {
         return $prev;
      }
   }
   return $prev;
}

sub terminal_size {
   my $w = `tput cols`;
   chomp($w);
   my $h = `tput lines`;
   chomp($h);
   return ($w, $h);
}

sub parse_monitoring_config($) {
    my $file = shift;
    my %default = (
        'CPU'       => 'idle,user,system,iowait',
        'System'    => 'csw,int',
        'Memory'    => 'free,used',
        'Disk'      => 'read,write',
        'Net'       => 'recv,send',
        'interval'  => 1,
        'priority'  => 0,
        'comment'   => '',
        );
    my @metrics = ('CPU', 'System', 'Memory', 'Disk', 'Net');
    my @default_summary;
    for my $m (@metrics) {
        push @default_summary,  map {$m."_".$_} split(",", $default{$m});
    }
    $default{metrics} = join(",", @default_summary);
    my %targets = ();
    my $conf = XML::Simple->new()->XMLin($file, ForceArray => 1);
    for my $host (@{$conf->{Host}}) {
        if ($host->{address}) {
            my $base_count = 0;
            my $adr = $host->{address};
            my @summary;

            # metrics
            for my $m (@metrics) {
                if (defined $host->{$m}) {
                    if (defined $host->{$m}->[0]->{measure}) {
                        $targets{$adr}{$m} = $host->{$m}->[0]->{measure};
                    } else {
                        $targets{$adr}{$m} = $default{$m};
                    }
                    push @summary,  map {$m."_".$_} split(",", $targets{$adr}{$m});
                } else {
                    $base_count ++;
                }
            }
            $targets{$adr}{metrics} = join(",", @summary);

            # custom
            if (defined $host->{Custom}) {
                if ($host->{Custom}) {
                    if (ref($host->{Custom}) eq 'ARRAY') {
                        for my $c (@{$host->{Custom}}) {
                            push @{$targets{$adr}{custom}}, $c;
                        }
                    } elsif (ref($host->{Custom}) eq 'HASH') {
                        push @{$targets{$adr}{custom}}, $host->{Custom};
                    }
                }
            } else {
                if ($base_count == @metrics) {
                    %{$targets{$adr}} = %default;
                }
            }

            # meta
            for my $m ('interval', 'priority', 'comment') { 
                if ($host->{$m}) {
                    $targets{$adr}{$m} = $host->{$m};
                } else {
                    $targets{$adr}{$m} = $default{$m};
                }
            }
        }
    }
    return \%targets;
}

sub create_agent_config($) {
    my $conf = shift;
    my $o = "[main]\n";
    $o .= "interval = ".$conf->{interval}."\n\n";
    $o .= "[metric]\n";
    $o .= "names = cpu-la,mem,cpu_stats\n";
    return $o;
}

sub create_monitoring_summary($) {
    my $conf = shift;
    
}

1;
