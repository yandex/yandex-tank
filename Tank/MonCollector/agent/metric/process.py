import commands

def check_cpu_mem(process_dict):
    '''
    Read 'ps' tool output and
    collect POSIX process %CPU,%MEM,VSZ,RSS values
    '''
    result = []
    for name in process_dict:
        result.extend(commands.getoutput('ps aux | grep ' + str(process_dict[name]['pid']) + ' | grep -v grep | awk \'{print $3";"$4";"$5";"$6}\'').split(';'))
    return result
