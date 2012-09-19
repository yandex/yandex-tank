import commands


class NetTcp(object):
    ''' Read ss util output and count TCP socket's number grouped by state '''

    def __init__(self,):
        self.fields = ['Net_closewait', 'Net_estab', 'Net_listen', 'Net_timewait', ]
        self.keys = ['CLOSE-WAIT', 'ESTAB', 'LISTEN', 'TIME-WAIT', ]

    def columns(self,):
        return self.fields

    def check(self,):
        fetch = lambda: commands.getoutput("ss -an | cut -d' ' -f 1 | tail -n +2 | sort | uniq -c")
        data = {}
        result = []
        raw_lines = fetch().split('\n')
        for line in raw_lines:
            value = line.split()
            data[value[1].strip()] = int(value[0].strip())
        '''
        * check is there TCP connections in "field" state in last check
        if note set it to 0.
        * make output ordered as "fields" list
        '''
        for field in self.keys:
            if field in data:
                result.append(str(data[field]))
            else:
                result.append('0')
        return result
