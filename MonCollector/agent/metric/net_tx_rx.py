import commands
import logging


class NetTxRx(object):
    ''' Get upped iface names and read they Tx/Rx counters in bytes '''
    def __init__(self,):
        self.prevRX=0
        self.prevTX=0

    def columns(self,):
        return ['Net_tx', 'Net_rx', ]

    def check(self,):
        '''
        get network interface name which have ip addr
        which resolved fron  host FQDN.
        If we have network bonding or need to collect multiple iface
        statistic beter to change that behavior.
        '''
        data = commands.getoutput("/sbin/ifconfig -s | awk '{rx+=$4; tx+=$8} END {print rx, tx}'")
        logging.debug("TXRX output: %s", data)
        (rx,tx)=data.split(" ")
        rx=int(rx)
        tx=int(tx)
        
        if (self.prevRX==0):
            tTX=0
            tRX=0
        else:
            tRX=rx-self.prevRX
            tTX=tx-self.prevTX
        self.prevRX=rx
        self.prevTX=tx
        
        return [tRX, tTX]