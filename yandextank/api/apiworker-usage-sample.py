from yandextank.api.apiworker import ApiWorker
import logging
import traceback
import sys

logger = logging.getLogger('')
logger.setLevel(logging.DEBUG)

#not mandatory options below:
options = dict()
options['config'] = '/path/to/config/load.ini'
options['manual_start'] = "1"
options['user_options'] = [
    'phantom.ammofile=/path/to/ammofile',
    'phantom.rps_schedule=const(1,2m)',
]
log_filename = '/path/to/log/tank.log'
#======================================

apiworker = ApiWorker()
apiworker.init_logging(log_filename)
try:
    apiworker.configure(options)
    apiworker.perform_test()
except Exception, ex:
    logger.error('Error trying to perform a test: %s', ex)
