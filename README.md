# Yandex Tank
## Description
Yandex.Tank is a console HTTP load testing instrument.

### Installation and Configuration

You should add proper repositories on Debian-based environment. 

For instance, add following repos to ```sources.list``` :

```
# Ubuntu Lucid/Precise
deb http://ppa.launchpad.net/yandex-load/main/ubuntu precise main 
deb-src http://ppa.launchpad.net/yandex-load/main/ubuntu precise main
```
or this way

```
sudo apt-get install python-software-properties
sudo add-apt-repository ppa:yandex-load/main
```

Then update package list and install ```yandex-load-tank-base``` package:
```sudo apt-get update && sudo apt-get install yandex-load-tank-base```

For mild load tests (less then 1000rps) an average laptop with 32/64bit Ubuntu (Lucid/Precise) would be sufficient.
The tank could be easily used in virtual machine if queries aren't too heavy and load isn't too big.
Otherwise it is recommended to request a physical server or a more capable virtual machine from your admin. 
See also https://github.com/yandex-load/yandex-tank#load-server-configuration-and-tunning

## Usage
So, you've installed Yandex.Tank to a proper server, close to target, access is permitted and server is tuned.
How to make a test?

### First Step
Create a file on a server with Yandex.Tank:
**load.conf**
```
[phantom]
address=23.23.23.23:80 #Target's address and port .
rps_schedule=line(1, 100, 10m) #load scheme 
```
Yandex.Tank have 3 primitives for describing load scheme:
   1. ```step (a,b,step,dur)``` makes stepped load, where a,b are start/end load values, step - increment value, dur - step duration.
   2. ```line (a,b,dur)``` makes linear load, where a,b are start/end load, dur - the time for linear load increase from a to b.
   3. ```const (load,dur)``` makes constant load. load - rps amount, dur - load duration.
You can set fractional load like this: ```const (a/b,dur)``` -- a/b rps, where a >= 0, b > 0.
Note: ```const(0, 10)``` - 0 rps for 10 seconds, in fact 10s pause in a test.

```step``` and ```line``` could be used with increasing and decreasing intensity:
```step(25, 5, 5, 60)``` - stepped load from 25 to 5 rps, with 5 rps steps, step duration 60s.
```step(5, 25, 5, 60)``` - stepped load from 5 to 25 rps, with 5 rps steps, step duration 60s
```line(100, 1, 10m)``` - linear load from 100 to 1 rps, duration - 10 minutes
```line(1, 100, 10m)``` - linear load from 1 to 100 rps, duration - 10 minutes

Time duration could be defined in seconds, minutes (m) and hours (h). For example: ```27h103m645```

For a test with constant load at 10rps for 10 minutes, load.conf should have next lines:
```
[phantom]
address=23.23.23.23:80 #Target's address and port .
rps_schedule=const(10, 10m) #load scheme
```
Voilà, Yandex.Tank setup is done.

### Preparing requests
There are two ways to set up requests.
#### URI-style
URIs listed in load.conf or in a separate file.

##### URIs in load.conf
Update configuration file with HTTP headers and URIs:
```
[phantom]
address=23.23.23.23:80 #Target's address and port .
rps_schedule=const(10, 10m) #load scheme# Headers and URIs for GET requests
header_http = 1.1
headers = [Host: www.target.example.com]
  [Connection: close]
uris = /
  /buy
  /sdfg?sdf=rwerf
  /sdfbv/swdfvs/ssfsf
```
Parameters ```header``` define headers values.
```uri``` contains uri, which should be used for requests generation.

##### URIs in file
Create a file with declared requests:
**ammo.txt**
```
[Connection: close]
[Host: target.example.com]
[Cookies: None]
/?drg
/
/buy
/buy/?rt=0&station_to=7&station_from=9
```

File begins with optional lines [...], that contain headers which will be added to every request. After that section there is a list of URIs. Every URI must begin from a new line, with leading '/'.
#### Request-style
Full requests listed in a separate file.
For more complex requests, like POST, you'll have to create a special file. 
File format is:
```
[size_of_request] [tag]\n
[body_request]
\r\n
[size_of_request2] [tag]\n
[body_request2]
\r\n
```
where size_of_request – request size in bytes. 
'\r\n' symbols after body_requests are ignored and not sent anywhere, but it is required to include it in a file after each request. '\r' is also required.
**sample GET requests**
```
73 good
GET / HTTP/1.0
Host: xxx.tanks.example.com
User-Agent: xxx (shell 1)

77 bad
GET /abra HTTP/1.0
Host: xxx.tanks.example.com
User-Agent: xxx (shell 1)

78 unknown
GET /ab ra HTTP/1.0
Host: xxx.tanks.example.com
User-Agent: xxx (shell 1)
```
**sample POST requests**
```
904
POST /upload/2 HTTP/1.0
Content-Length: 801
Host: xxxxxxxxx.dev.example.com
User-Agent: xxx (shell 1)


^.^........W.j^1^.^.^.²..^^.i.^B.P..-!(.l/Y..V^.      ...L?...S'NR.^^vm...3Gg@s...d'.\^.5N.$NF^,.Z^.aTE^.
._.[..k#L^ƨ`\RE.J.<.!,.q5.F^՚iΔĬq..^6..P..тH.`..i2
.".uuzs^^F2...Rh.&.U.^^..J.P@.A......x..lǝy^?.u.p{4..g...m.,..R^.^.^......].^^.^J...p.ifTF0<.s.9V.o5<..%!6ļS.ƐǢ..㱋....C^&.....^.^y...v]^YT.1.#K.ibc...^.26...   ..7.
b.$...j6.٨f...W.R7.^1.3....K`%.&^..d..{{      l0..^\..^X.g.^.r.(!.^^...4.1.$\ .%.8$(.n&..^^q.,.Q..^.D^.].^.R9.kE.^.$^.I..<..B^..^.h^^C.^E.|....3o^.@..Z.^.s.$[v.
527
POST /upload/3 HTTP/1.0
Content-Length: 424
Host: xxxxxxxxx.dev.example.com
User-Agent: xxx (shell 1)


^.^........QMO.0^.++^zJw.ر^$^.^Ѣ.^V.J....vM.8r&.T+...{@pk%~C.G../z顲^.7....l...-.^W"cR..... .&^?u.U^^.^.....{^.^..8.^.^.I.EĂ.p...'^.3.Tq..@R8....RAiBU..1.Bd*".7+.
.Ol.j=^.3..n....wp..,Wg.y^.T..~^..
```
**sample POST multipart:**
```
533
POST /updateShopStatus? HTTP/1.0
User-Agent: xxx/1.2.3
Host: xxxxxxxxx.dev.example.com
Keep-Alive: 300
Content-Type: multipart/form-data; boundary=AGHTUNG
Content-Length:334
Connection: Close

--AGHTUNG
Content-Disposition: form-data; name="host"

load-test-shop-updatestatus.ru
--AGHTUNG
Content-Disposition: form-data; name="user_id"

1
--AGHTUNG
Content-Disposition: form-data; name="wsw-fields"

<wsw-fields><wsw-field name="moderate-code"><wsw-value>disable</wsw-value></wsw-field></wsw-fields>
--AGHTUNG--

```

### Run Test!

1. Request specs in load.conf
```
yandex-tank
```

2. Request specs in ammo.txt
```
yandex-tank ammo.txt
```

Yandex.Tank detects requests format and generates ultimate requests versions.

```yandex-tank``` here is an executable file name of Yandex.Tank.

If Yandex.Tank has been installed properly and configuration file is correct, the load will be given in next few seconds.

### Results
During test execution you'll see HTTP and net errors, answer times distribution, progressbar and other interesting data.
At the same time file ```phout.txt``` is being written, which could be analyzed later.

### Tags
Requests could be grouped and marked by some tag. Example of file with requests and tags:
```
73 good
GET / HTTP/1.0
Host: xxx.tanks.example.com
User-Agent: xxx (shell 1)

77 bad
GET /abra HTTP/1.0
Host: xxx.tanks.example.com
User-Agent: xxx (shell 1)

75 unknown
GET /ab HTTP/1.0
Host: xxx.tanks.example.com
User-Agent: xxx (shell 1)
```
'good', 'bad' and 'unknown' here are the tags.
**RESTRICTION: latin letters allowed only.**

### SSL
To activate SSL add 'ssl = 1' to load.conf. Don't forget to change port number to appropriate value.
Now, our basic config looks like that: 
```
[phantom]
address=23.23.23.23:80 #Target's address and port .
rps_schedule=const (10,10m) #Load scheme
ssl=1
```
### Autostop
Autostop is an ability to automatically halt test execution if some conditions are reached.
#### HTTP and Net codes conditions
There is an option to define specific codes (404,503,100) as well as code groups (3xx, 5xx, xx). Also you can define relative threshold (percent from the whole amount of answer per second) or absolute (amount of answers with specified code per second). 
Examples:
```autostop = http(4xx,25%,10)``` – stop test, if amount of 4xx http codes in every second of last 10s period exceeds 25% of answers (relative threshold)
```autostop = net(101,25,10)``` – stop test, if amount of 101 net-codes in every second of last 10s period is more than 25 (absolute threshold)
```autostop = net(xx,25,10)``` – stop test, if amount of non-zero net-codes in every second of last 10s period is more than 25 (absolute threshold)

#### Average time conditions
Example:
```autostop = time(1500,15)``` – stop test, if average answer time exceeds 1500ms

So, if we want to stop test when all answers in 1 second period are 5xx plus some network and timing factors - add autostop line to load.conf:
```
[phantom]
address=23.23.23.23:80 #Target's address and port .
rps_schedule=const(10, 10m) #load scheme
[autostop]
autostop=time(1,10)
  http(5xx,100%,1s)
  net(xx,1,30)
```

### Logging
Looking into target's answers is quite useful in debugging. For doing that add 'writelog = 1' to load.conf.
**ATTENTION: Writing answers on high load leads to intensive disk i/o usage and can affect test accuracy.**
Log format:
```
<metrics>
<body_request>
<body_answer>
```

Where metrics are:
```size_in size_out response_time(interval_real) interval_event net_code``` (request size, answer size, response time, time to wait for response from the server, answer network code)
Example:
```
user@tank:~$ head answ_*.txt 
553 572 8056 8043 0
GET /create-issue HTTP/1.1
Host: target.yandex.net
User-Agent: tank
Accept: */*
Connection: close


HTTP/1.1 200 OK
Content-Type: application/javascript;charset=UTF-8
```

For ```load.conf``` like this:
```
[phantom]
address=23.23.23.23:80 #Target's address and port .
rps_schedule=const(10, 10m) #load scheme
writelog=1
[autostop]
autostop=time(1,10)
  http(5xx,100%,1s)
  net(xx,1,30)

```

### Results in phout
phout.txt - is a per-request log. It could be used for service behaviour analysis (Excel/gnuplot/etc)
It has following fields: ```time, tag, interval_real, connect_time, send_time, latency, receive_time, interval_event, size_out, size_in, net_code proto_code```

Phout example:
```
1326453006.582          1510    934     52      384     140     1249    37      478     0       404
1326453006.582   others       1301    674     58      499     70      1116    37      478     0       404
1326453006.587   heavy       377     76      33      178     90      180     37      478     0       404
1326453006.587          294     47      27      146     74      147     37      478     0       404
1326453006.588          345     75      29      166     75      169     37      478     0       404
1326453006.590          276     72      28      119     57      121     53      476     0       404
1326453006.593          255     62      27      131     35      134     37      478     0       404
1326453006.594          304     50      30      147     77      149     37      478     0       404
1326453006.596          317     53      33      158     73      161     37      478     0       404
1326453006.598          257     58      32      106     61      110     37      478     0       404
1326453006.602          315     59      27      160     69      161     37      478     0       404
1326453006.603          256     59      33      107     57      110     53      476     0       404
1326453006.605          241     53      26      130     32      131     37      478     0       404
```
**NOTE:** as Yandex.Tank uses phantom as an http load engine and this file is written by phantom, it contents depends on phantom version installed on your Yandex.Tank system.

### Graph and statistics
Use included charting tool that runs as a webservice on localhost
OR
use your favorite stats packet, R, for example.
### Custom timings
You can set custom timings in ```load.conf``` with ```time_periods``` parameter like this:
```
[phantom]
address=23.23.23.23:80 #Target's address and port .
rps_schedule=const(10, 10m) #load scheme
[aggregator]
time_periods = 10 45 50 100 150 300 500 1s 1500 2s 3s 10s # the last value - 10s is considered as connect timeout.
```

### Thread limit
```instances=N``` in ```load.conf``` limits number of simultanious connections (threads).
Test with 10 threads:
```
[phantom]
address=23.23.23.23:80 #Target's address and port .
rps_schedule=const(10, 10m) #load scheme
instances=10
```

### Dynamic thread limit
```instances_schedule = <instances increasing scheme>``` -- test with active instances schedule will be performed if load scheme is not defined. Bear in mind that active instances number cannot be decreased and final number of them must be equal to ```instances``` parameter value.
load.conf example:
```
[phantom]
address=23.23.23.23:80 #Target's address and port .
instances_schedule = line(1,10,10m)
#load = const (10,10m) #Load scheme is excluded from this load.conf as we used instances_schedule parameter
```

### Custom stateless protocol
In necessity of testing stateless HTTP-like protocol, Yandex.Tank's HTTP parser could be switched off, providing ability to generate load with any data, receiving any answer in return.
To do that add ```tank_type = 2``` to ```load.conf```. 
**Indispensable condition: Connection close must be initiated by remote side**
load.conf example:
```
[phantom]
address=23.23.23.23:80 #Target's address and port .
rps_schedule=const(10, 10m) #load scheme
instances=10
tank_type=2
```
### Gatling
If server with Yandex.Tank have several IPs, they may be used to avoid outcome port shortage. Use ```gatling_ip``` parameter for that.
Load.conf:
```
[phantom]
address=23.23.23.23:80 #Target's address and port .
rps_schedule=const(10, 10m) #load scheme
instances=10
gatling_ip = 23.23.23.24 23.23.23.26
```
**run yandex-tank with -g key**

## Advanced usage

### Command line options
There are three executables in Yandex.Tank package: ```yandex-tank```, ```yandex-tank-ab``` и ```yandex-tank-jmeter```. Last two of them just use different king of load gen utilities, ```ab``` (Apache Benchmark) and ```jmeter``` (Apache JMeter), accordingly. Command line options are common for all three:
* **-h, --help** - show command line options
* **-c CONFIG, --config=CONFIG** - read options from INI file. It is possible to set multiple INI files by specifying the option serveral times. Default: ```./load.conf```
* **-i, --ignore-lock** - ignore lock files
* **-f, --fail-lock** - don't wait for lock file, quit if it's busy. The default behaviour is to wait for lock file to become free.
* **-l LOG, --log=LOG** - main log file location. Default: ```./tank.log```
* **-n, --no-rc** - don't read ```/etc/yandex-tank/*.ini``` and ```~/.yandex-tank```
* **-o OPTION, --option=OPTION** - set an option from command line. Options set in cmd line override those have been set in configuration files. Multiple times for multiple options. Format: ```<section>.<option>=value``` Example: ```yandex-tank -o "console.short_only=1" --option="phantom.force_stepping=1"```
* **-q, --quiet** - only print WARNINGs and ERRORs to console
* **-v, --verbose** - print ALL messages to console. Chatty mode

Add an ammo file name as a nameless parameter, e.g.: ```yandex-tank ammo.txt```

### Advanced configuration
Configuration files organized as standard INI files. Those are files partitioned into named sections that contain 'name=value' records. For example:
```
[phantom]
address=target-mulca.targetnets.yandex.ru:8080
rps_schedule=const(100,60s)

[autostop]
autostop=instances(80%,10)
```
A common rule: options with same name override those set before them (in the same file or not).

#### Default configuration files
If no ```--no-rc``` option passed, Yandex.Tank reads all ```*.ini``` from ```/etc/yandex-tank``` directory, then a personal config file ```~/.yandex-tank```. So you can easily put your favourite settings in ```~/.yandex-tank```, for example, ```tank.artifacts_base_dir```, ```phantom.cache_dir```, ```console.info_panel_width```

#### The ```DEFAULT``` section
One can use a **magic** ```DEFAULT``` section, that contains global options. Those options are in charge for every section:
```
[autostop]
autostop=time(1,10)

[console]
short_only=1

[aggregator]
time_periods=10 20 30 100

[meta]
job_name=ask
```
is an equivalent for:
```
[DEFAULT]
autostop=time(1,10)
short_only=1
time_periods=10 20 30 100
job_name=ask
```
!!! Don't use global options wich have same name in different sections.

#### Multiline options
Use indent to show that a line is a continuation of a previous one:
```
[autostop]
autostop=time(1,10)
  http(404,1%,5s)
  net(xx,1,30)
```
**Ask Yandex.Tank developers to add multiline capability for options where you need it!**

#### Time units
Time units encoding is as following:
* ```ms``` = millisecons
* ```s``` = seconds
* ```m``` = minutes
* ```h``` = hours
Default time unit is a millisecond. For example, ```30000 == 30s```

```time(30000,120)``` is an equivalent to ```time(30s,2m)```
You can also mix them: ```1h30m15s``` or ```2s15ms```

### Artifacts
As a result Yandex.Tank produces some files (logs, results, configs etc). Those files are placed with care to the **artifact directory**. An option for that is ```artifacts_base_dir``` in the ```tank``` section. It is recommended to set it to a convinient place, for example, ```~/yandex-tank-artifacts```, it would be easier to manage the artifacts there.

### Modules

#### Phantom
Load generator module that uses phantom utility.

##### Options

INI file section: **[phantom]**

Basic options:
* **ammofile** - ammo file path (ammo file is a file containing requests that are to be sent to a server)
* **rps_schedule** - load schedule in terms of RPS
* **instances** - max number of instances (concurrent requests)
* **instances_schedule** - load schedule in terms of number of instances
* **loop** - number of times requests from ammo file are repeated in loop
* **autocases** - enable marking requests automatically (1 -- enable, 0 -- disable)

Additional options:
* **writelog** - enable verbose request/response logging. Available options: 0 - disable, all - all messages, proto_warning - 4хх+5хх+network errors, proto_error - 5хх+network errors. Default: 0
* **ssl** - enable SSL, 1 - enable, 0 - disable, default: 0
* **address** - address of service to test. May contain port divided by colon for IPv4 or DN. For DN, DNS request is performed, and then reverse-DNS request to verify the correctness of name. Default: ```127.0.0.1```
* **port** - port of service to test. Default: ```80```
* **gatling_ip** - use multiple source addresses. List, divided by spaces.
* **tank_type** - protocol type: http, none (raw TCP). Default: ```http```

URI-style options:
* **uris** - URI list, multiline option.
* **headers** - HTTP headers list in the following form: ```[Header: value]```, multiline option.
* **header_http** - HTTP version, default: ```1.1```

stpd-file cache options:
* **use_caching** - enable cache, default: ```1```
* **cache_dir** - cache files directory, default: base artifacts directory.
* **force_stepping** - force stpd file generation, default: ```0```

Advanced options:
* **phantom_path** - phantom utility path, default: ```phantom```
* **phantom_modules_path** - phantom modules path, default:```/usr/lib/phantom```
* **config** - use given (in this option) config file for phantom instead of generated.
* **phout_file** - import this phout instead of launching phantom (import phantom results)
* **stpd_file** - use this stpd-file instead of generated
* **threads** - phantom thread count, default: ```<processor cores count>/2 + 1```

http-module tuning options:
* **phantom_http_line** 
* **phantom_http_field_num**
* **phantom_http_field**
* **phantom_http_entity**

#####Artifacts
* **phantom_*.conf** - generated configuration files
* **phout_*.log** - raw results file
* **phantom_stat_*.log** - phantom statistics, aggregated by seconds
* **answ_*.log** - detailed request/response log
* **phantom_*.log** - internal phantom log

#### Auto-stop
The Auto-stop module gets the data from the aggregator and passes them to the criteria-objects that decide if we should stop the test.

INI file section: **[autostop]**

##### Options
* **autostop** - criteria list divided by spaces, in following format: ```type(parameters)```

Available criteria types:
* **time** - stop the test if average response time is higher then specified for as long as the time period specified. E.g.: ```time(1s500ms, 30s) time(50,15)```
* **http** - stop the test if the count of responses in last time period (specified) with HTTP codes fitting the mask is larger then the specified absolute or relative value. Examples: ```http(404,10,15) http(5xx, 10%, 1m)```
* **net** - like ```http```, but for network codes. Use ```xx``` for all non-zero codes.
* **quantile** - stop the test if the specified percentile is larger then specified level for as long as the time period specified. Available percentile values: 25, 50, 75, 80, 90, 95, 98, 99, 100. Example: ```quantile (95,100ms,10s)```
* **instances** - available when phantom module is included. Stop the test if instance count is larger then specified value. Example: ```instances(80%, 30) instances(50,1m)```
* **total_time** — like ```time```, but accumulate for all time period (responses that fit may not be one-after-another, but only lay into specified time period). Example: ```total_time(300ms, 70%, 3s)```
* **total_http** — like ```http```, but accumulated. See ```total_time```. Example: ```total_http(5xx,10%,10s) total_http(3xx,40%,10s)```
* **total_net** — like ```net```, but accumulated. See ```total_time```. Example: ```total_net(79,10%,10s) total_net(11x,50%,15s)```
* **negative_http** — ```http```, inversed. Stop if there are not enough responses that fit the specified mask. Use to be shure that server responds 200. Example: ```negative_http(2xx,10%,10s)```

#### Console on-line screen
Shows usefull information in console while running the test

INI file section: **[console]**

##### Options
* **short_only** - show only one-line summary instead of full-screen (usefull for scripting), default: 0 (disable)
* **info_panel_width** - relative right-panel width in percents, default: 33

#### Aggregator
The aggregator module is responsible for aggregation of data received from different kind of modules and transmitting that aggregated data to consumer modules (Console screen module is an example of such kind).
INI file section: **[aggregator]**
##### options:
* **time_periods** - time intervals list divided by zero. Default: ```1ms 2 3 4 5 6 7 8 9 10 20 30 40 50 60 70 80 90 100 150 200 250 300 350 400 450 500 600 650 700 750 800 850 900 950 1s 1500 2s 2500 3s 3500 4s 4500 5s 5500 6s 6500 7s 7500 8s 8500 9s 9500 10s 11s```

#### ShellExec
The ShellExec module executes the shell-scripts (hooks) on different stages of test, for example, you could start/stop some services just before/after the test. Every hook must return 0 as an exit code or the test is terminated. Hook's stdout will be written to DEBUG, stderr will be WARNINGs.

INI file section: **[shellexec]**

##### Options:
* **prepare** - the script to run on prepare stage
* **start** - the script to run on start stage
* **poll** - the script to run every second while the test is running
* **end** - the script to run on end stage
* **postprocess** - the script to run on postprocess stage

#### JMeter
JMeter load generator module. 

INI file section: **[jmeter]**

##### Options
* !!mandatory option!! **jmx** - test plan file
* **args** - JMeter command line parameters
* **jmeter_path** - JMeter path, default: ```jmeter```

##### Artifacts
* **_original_jmx.jmx>** - original test plan file
* **modified_*.jmx** - modified test plan with results output section
* **jmeter_*.jtl** - JMeter results
* **jmeter_*.log** - JMeter log

#### AB
Apache Benchmark load generator module. As the ab utility writes results to file only after the test is finished, Yandex.Tank is unable to show the on-line statistics for the tests with ab. The data are reviewed after the test.

INI file section: **[ab]**
##### Options
* **url** - requested URL, default: ```http:**localhost/```
* **requests** - total request count, default: 100
* **concurrency** - number of concurrent requests: 1
* **options** - ab command line options

##### Artifacts
* **ab_*.log** - request log with response times

#### Tips&Tricks
Shows tips and tricks in fullscreen console. **If you have any tips&tricks, tell the developers about them**

INI-file section: **[tips]**
##### Options
* **disable** - disable tips and tricks, default: don't (0)

### Sources
Yandex.Tank sources ((https://github.com/yandex-load/yandex-tank here)).

### load.conf.example
```
# Yandex.Tank config file
address=23.23.23.23:443 #Target's address and port
load = const (10,10m) #Load scheme
#  Headers and URIs for GET requests
header_http = 1.1
headers = [Host: www.target.example.com]
  [Connection: close]
uri = /
#ssl=1
#autostop = http(5xx,100%,1)
#instances=10
#writelog=1
#time_periods = 10 45 50 100 150 300 500 1s 1500 2s 3s 10s # the last value - 10s is considered as connect timeout.
#instances_schedule = line (1,1000,10m)
#tank_type=2
#gatling_ip = 141.8.153.82 141.8.153.81

```
## Load Server Configuration and Tunning
### Firewall

Before test execution, please, check service availability. If service is running on server with IP x.x.x.x and listening for TCP port zz, try to connect to it with ```telnet``` like this:
```telnet x.x.x.x zz```
If everything OK, you'll see:
```
$ telnet 23.23.23.23 80
Trying 23.23.23.23...
Connected to 23.23.23.23.
Escape character is '^]'.
```
Otherwise if port is unreacheable:
```
$ telnet 8.8.8.8 80
Trying 8.8.8.8...
telnet: Unable to connect to remote host: Connection timed out
```
(it's just an example, programs like ```nc/nmap/wget/curl``` could be used as well, but not ping!)
### Routing
OK, service is reachable, next thing you should know is how far Yandex.Tank is located from the service you'd like to test. Heavy load can make switch to be unresponsible or to reboot, or at least it may lead to network losses, so the test results would be distorted. Be careful. Path estimation could be done by execution of ```tracepath``` command or it analogs (```tracert/traceroute```) on Yandex.Tank machine:

```
$ tracepath 23.23.23.24
 1:  tank.example.com (23.23.23.23)            0.084ms pmtu 1450
 1:  target.load.example.com (23.23.23.24)           20.919ms reached
 1:  target.example.com (23.23.23.24)            0.128ms reached
     Resume: pmtu 1450 hops 1 back 64
```
Hops count = 1 means that tank and target are in closest location.

```
$ tracepath 24.24.24.24
 1:  1.example.com (124.24.24.24)                 0.084ms pmtu 1450
 1:  2.example.com (24.124.24.24)          0.276ms 
 1:  3.example.com (24.24.124.24)          0.411ms 
 2:  4.example.com (24.24.24.124)                0.514ms 
 3:  5.example.com (241.24.24.24)              10.690ms 
 4:  6.example.com (24.241.24.24)                  0.831ms asymm  3 
 5:  7.example.com (24.24.241.24)                 0.512ms 
 6:  8.example.com (24.24.24.241)                 0.525ms asymm  5 
 7:  no reply
```
In this example you'd better find another closer located tank.

### Tuning
To achieve the top most performance you should tune the source server system limits:
```
ulimit -n 30000

net.ipv4.tcp_max_tw_buckets = 65536
net.ipv4.tcp_tw_recycle = 1
net.ipv4.tcp_tw_reuse = 0
net.ipv4.tcp_max_syn_backlog = 131072
net.ipv4.tcp_syn_retries = 3
net.ipv4.tcp_synack_retries = 3
net.ipv4.tcp_retries1 = 3
net.ipv4.tcp_retries2 = 8
net.ipv4.tcp_rmem = 16384 174760 349520
net.ipv4.tcp_wmem = 16384 131072 262144
net.ipv4.tcp_mem = 262144 524288 1048576
net.ipv4.tcp_max_orphans = 65536
net.ipv4.tcp_fin_timeout = 10
net.ipv4.tcp_low_latency = 1
net.ipv4.tcp_syncookies = 0
```



## See also
Evgeniy Mamchits' [phantom](https://github.com/mamchits/phantom) - Phantom scalable IO Engine

Gregory Komissarov's [firebat](https://github.com/greggyNapalm/firebat-console) - test tool based on Phantom

Andrey Pohilko's [loadosophia](http://loadosophia.org/) - service for storing and analysing performance test results

Russian Community [YandexTankClub](http://clubs.ya.ru/yandex-tank/) - Yandex Team Blog

![Yandex.Metrics counter](https://mc.yandex.ru/watch/17743264)