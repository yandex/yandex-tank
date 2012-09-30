'''
Module to have Loadosophia.org integration
'''
from Tank.Core import AbstractPlugin
from Tank.Plugins.ApacheBenchmark import ApacheBenchmarkPlugin
from Tank.Plugins.Monitoring import MonitoringPlugin
from Tank.Plugins.Phantom import PhantomPlugin
import StringIO
import itertools
import logging
import mimetools
import mimetypes
import os
import urllib2

class LoadosophiaPlugin(AbstractPlugin):
    '''
    Tank plugin with Loadosophia.org uploading 
    '''
    SECTION = 'loadosophia'
    
    @staticmethod
    def get_key():
        return __file__

    def __init__(self, core):
        '''
        Constructor
        '''
        AbstractPlugin.__init__(self, core)
        self.loadosophia = LoadosophiaClient()
        self.project_key = None
    
    def configure(self):
        self.loadosophia.set_address(self.get_option("address", "https://loadosophia.org/uploader/"))
        self.loadosophia.set_token(self.get_option("token", ""))
        self.project_key = self.get_option("project", '')
    
    def post_process(self, retcode):
        main_file = None
        # phantom
        try:
            phantom = self.core.get_plugin_of_type(PhantomPlugin)
            main_file = phantom.phout_file
        except KeyError:
            self.log.debug("Phantom not found")
            
        # ab
        try:
            ab = self.core.get_plugin_of_type(ApacheBenchmarkPlugin)
            main_file = ab.out_file
        except KeyError:
            self.log.debug("AB not found")
        
        # monitoring
        mon_file = None
        try:
            mon = self.core.get_plugin_of_type(MonitoringPlugin)
            mon_file = mon.data_file
        except KeyError:
            self.log.debug("Phantom not found")
            
        self.loadosophia.send_results(self.project_key, main_file, [mon_file])
        return retcode

class LoadosophiaClient:
    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.token = None
        self.address = None
    
    def set_token(self, token):
        self.log.info("Setting token")
        self.token = token

    def set_address(self, addr):
        self.address = addr

    def send_results(self, project, result_file, monitoring_files):
        if not self.token:
            self.log.warning("Loadosophia.org uploading disabled, please set loadosophia.token option to enable it, get token at https://loadosophia.org/service/upload/token/")
        else:
            if not self.address:
                self.log.warning("Loadosophia.org uploading disabled, please set loadosophia.address option to enable it")
            else:
                self.log.info("Uploading to Loadosophia.org: %s %s %s", project, result_file, monitoring_files)
                if not project:
                    self.log.info("Uploading to default project, please set loadosophia.project option to change this")
                if not result_file or not os.path.exists(result_file) or not os.path.getsize(result_file):
                    self.log.warning("Empty results file, skip Loadosophia.org uploading: %s", result_file)
                else:
                    self.__send_checked_results(project, result_file, monitoring_files)
    
    
    def __send_checked_results(self, project, result_file, monitoring_files):
        # Create the form with simple fields
        form = MultiPartForm()
        form.add_field('projectKey', project)
        form.add_field('uploadToken', self.token)
        
        # Add a fake file
        form.add_file('jtl_file', os.path.basename(result_file), open(result_file, 'r'))
    
        # TODO: add mon files
    
        # Build the request
        request = urllib2.Request(self.address)
        request.add_header('User-Agent', 'Yandex.Tank Loadosophia Uploader Module')
        body = str(form)
        request.add_header('Content-Type', form.get_content_type())
        request.add_header('Content-Length', len(body))
        request.add_data(body)

        response = urllib2.urlopen(request)
        if response.getcode() != 202:
            self.log.debug("Full loadosophia.org response: %s", response.read())
            raise RuntimeError("Loadosophia.org upload failed, response code %s instead of 202, see log for full response text" % response.getcode())
        self.log.info("Loadosophia.org upload succeeded, visit https://loadosophia.org/service/upload/ to see processing status")
        
                

class MultiPartForm(object):
    """Accumulate the data to be used when posting a form."""
    '''http://blog.doughellmann.com/2009/07/pymotw-urllib2-library-for-opening-urls.html'''

    def __init__(self):
        self.form_fields = []
        self.files = []
        self.boundary = mimetools.choose_boundary()
        return
    
    def get_content_type(self):
        return 'multipart/form-data; boundary=%s' % self.boundary

    def add_field(self, name, value):
        """Add a simple field to the form data."""
        self.form_fields.append((name, value))
        return

    def add_file_as_string(self, fieldname, filename, body, mimetype=None):
        if mimetype is None:
            mimetype = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        self.files.append((fieldname, filename, mimetype, body))
        return

    def add_file(self, fieldname, filename, fileHandle, mimetype=None):
        """Add a file to be uploaded."""
        body = fileHandle.read()
        self.add_file_as_string(fieldname, filename, body, mimetype)
        return
    
    def __str__(self):
        """Return a string representing the form data, including attached files."""
        # Build a list of lists, each containing "lines" of the
        # request.  Each part is separated by a boundary string.
        # Once the list is built, return a string where each
        # line is separated by '\r\n'.  
        parts = []
        part_boundary = '--' + self.boundary
        
        # Add the form fields
        parts.extend(
            [ part_boundary,
              'Content-Disposition: form-data; name="%s"' % name,
              '',
              value,
            ]
            for name, value in self.form_fields
            )
        
        # Add the files to upload
        parts.extend(
            [ part_boundary,
              'Content-Disposition: file; name="%s"; filename="%s"' % \
                 (field_name, filename),
              'Content-Type: %s' % content_type,
              '',
              body,
            ]
            for field_name, filename, content_type, body in self.files
            )
        
        # Flatten the list and add closing boundary marker,
        # then return CR+LF separated data
        flattened = list(itertools.chain(*parts))
        flattened.append('--' + self.boundary + '--')
        flattened.append('')
        return '\r\n'.join(flattened)
