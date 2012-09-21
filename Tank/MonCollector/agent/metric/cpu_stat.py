from subprocess import Popen, PIPE

class CpuStat(object):
    ''' read /proc/stat and calculate amount of time
        the CPU has spent performing different kinds of work.
    '''
    def __init__(self,):
        # cpu data
        self.check_prev = None
        self.check_last = None
        
        # csw, int data
        self.current = None
        self.last = None

    def columns(self,):
        columns = ['System_csw', 'System_int',
                   'CPU_user', 'CPU_nice', 'CPU_system', 'CPU_idle', 'CPU_iowait',
                   'CPU_irq', 'CPU_softirq', 'System_numproc', 'System_numthreads']
        return columns 

    def check(self,):

        # Empty symbol for no data
        EMPTY = ''

        # resulting data array
        result = []

        # Context switches and interrups. Check.
        try:
            output = Popen('cat /proc/stat | grep -E "^(ctxt|intr|cpu) "',
                            shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        except Exception:
            result.append([EMPTY] * 9)
        else: 
            err = output.stderr.read()
            if err:
                result.extend([EMPTY] * 9)
            else:
                info = output.stdout.read()

                # CPU. Fetch data
                cpus = info.split("\n")[0].split()[1:8]
                fetch_cpu = lambda: map(float, cpus)

                # Context switches and interrupts. Fetch data
                data = []
                for line in info.split("\n")[1:3]:
                    if line:
                        data.append(line.split()[1])
                fetch_data = lambda: map(float, data)

                # Context switches and interrups. Analyze.
                if self.last:
                    self.current = fetch_data()
                    delta = []
                    cnt = 0
                    for el in self.current:
                        delta.append(self.current[cnt] - self.last[cnt])
                        cnt += 1
                    self.last = self.current
                    result.extend(map(str, delta))
                else:
                    self.last = fetch_data()
                    result.extend([EMPTY] * 2)
#                logger.debug("Result: %s" % result)

                # CPU. analyze.
#                logger.debug("CPU start.")
                if self.check_prev is not None:
                    self.check_last = fetch_cpu()
                    delta = []
                    cnt = 0
                    sum_val = 0
                    for v in self.check_last:
                        column_delta = self.check_last[cnt] - self.check_prev[cnt]
                        sum_val += column_delta
                        delta.append(column_delta)
                        cnt += 1

                    cnt = 0
                    for column in self.check_last:
                        result.append(str((delta[cnt] / sum_val) * 100))
                        cnt += 1
                    self.check_prev = self.check_last
                else:
                    self.check_prev = fetch_cpu()
                    result.extend([EMPTY] * 7)
#                logger.debug("Result: %s" % result)
                    
        # Numproc, numthreads 
        command = ['ps axf | wc -l', 'ps -eLf | wc -l']
        for cmd in command:
            try:
                output = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
            except Exception:
                result.append(EMPTY)
            else:
                err = output.stderr.read()
                if err:
                    result.append(EMPTY)
                else:
                    result.append(str(int(output.stdout.read().strip()) - 1))
        return result
