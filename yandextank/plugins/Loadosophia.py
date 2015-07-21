""" Module to have Loadosophia.org integration """
from urllib2 import HTTPError
import StringIO
import cookielib
import gzip
import itertools
import json
import logging
import mimetools
import mimetypes
import os
import time
import urllib
import urllib2

from Aggregator import AggregateResultListener, AggregatorPlugin
from ApacheBenchmark import ApacheBenchmarkPlugin
from JMeter import JMeterPlugin
from Monitoring import MonitoringPlugin
from Phantom import PhantomPlugin
from yandextank.core import AbstractPlugin


class LoadosophiaPlugin(AbstractPlugin, AggregateResultListener):
    """ Tank plugin with Loadosophia.org uploading """

    SECTION = 'loadosophia'

    @staticmethod
    def get_key():
        return __file__

    def __init__(self, core):
        """ Constructor """
        AbstractPlugin.__init__(self, core)
        self.loadosophia = LoadosophiaClient()
        self.loadosophia.results_url = None
        self.project_key = None
        self.color = None
        self.title = None
        self.online_buffer = []
        self.online_initiated = False
        self.online_enabled = False

    def get_available_options(self):
        return ["token", "project", "test_title", "file_prefix", "color_flag", "online_enabled"]

    def configure(self):
        self.loadosophia.address = self.get_option("address", "https://loadosophia.org/")
        self.loadosophia.token = self.get_option("token", "")
        self.loadosophia.file_prefix = self.get_option("file_prefix", "")
        self.project_key = self.get_option("project", 'DEFAULT')
        self.title = self.get_option("test_title", "")
        self.color = self.get_option("color_flag", "")
        if self.loadosophia.token:
            self.online_enabled = int(self.get_option("online_enabled", "1"))

        try:
            aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
            aggregator.add_result_listener(self)
        except KeyError:
            self.log.debug("No aggregator for loadosophia")

    def start_test(self):
        if self.online_enabled:
            try:
                url = self.loadosophia.start_online(self.project_key, self.title)
                self.log.info("Started active test: %s", url)
            except Exception, exc:
                self.log.warning("Problems starting online: %s", exc)
                self.online_enabled = False

    def aggregate_second(self, second_aggregate_data):
        if self.online_enabled:
            self.log.debug("Online buffer: %s", self.online_buffer)
            self.online_buffer.append(second_aggregate_data)
            if len(self.online_buffer) >= 5 or not self.online_initiated:
                try:
                    self.loadosophia.send_online_data(self.online_buffer)
                    self.online_initiated = True
                except Exception, exc:
                    self.log.warning("Problems sending online data: %s", exc)
                self.online_buffer = []

    def post_process(self, retcode):
        if self.online_enabled:
            if self.online_buffer:
                try:
                    self.loadosophia.send_online_data(self.online_buffer)
                except Exception, exc:
                    self.log.warning("Problems sending online data rests: %s", exc)
                self.online_buffer = []
            # mark test closed
            try:
                self.loadosophia.end_online()
            except Exception, exc:
                self.log.warning("Problems ending online: %s", exc)

        main_file = None
        # phantom
        try:
            phantom = self.core.get_plugin_of_type(PhantomPlugin)
            if phantom.phantom:
                main_file = phantom.phantom.phout_file
        except KeyError:
            self.log.debug("Phantom not found")

        # ab
        try:
            apache_bench = self.core.get_plugin_of_type(ApacheBenchmarkPlugin)
            main_file = apache_bench.out_file
        except KeyError:
            self.log.debug("AB not found")

        # jmeter
        try:
            jmeter = self.core.get_plugin_of_type(JMeterPlugin)
            main_file = jmeter.jtl_file
        except KeyError:
            self.log.debug("AB not found")


        if not main_file:
            self.log.warn("No file to upload to Loadosophia")
        else:
            # monitoring
            mon_file = None
            try:
                mon = self.core.get_plugin_of_type(MonitoringPlugin)
                mon_file = mon.data_file
            except KeyError:
                self.log.debug("Monitoring not found")

            queue_id = self.loadosophia.send_results(self.project_key, main_file, [mon_file])
            if self.title or self.color:
                test_id = self.loadosophia.get_test_by_upload(queue_id)
                if self.color:
                    self.loadosophia.set_color_flag(test_id, self.color)
                if self.title:
                    self.loadosophia.set_test_title(test_id, self.title)

            if queue_id:
                self.log.info("Loadosophia.org upload succeeded, report link: %s", self.loadosophia.results_url)

        return retcode


class LoadosophiaClient:
    """ Loadosophia service client class """

    STATUS_DONE = 4

    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.token = None
        self.address = None
        self.file_prefix = ''
        self.results_url = None
        self.cookie_jar = cookielib.CookieJar()

    def send_results(self, project, result_file, monitoring_files):
        """ Send files to loadosophia """
        if not self.token:
            msg = "Loadosophia.org uploading disabled, please set loadosophia.token option to enable it, "
            msg += "get token at https://loadosophia.org/service/upload/token/"
            self.log.warning(msg)
        else:
            if not self.address:
                self.log.warning(
                    "Loadosophia.org uploading disabled, please set loadosophia.address option to enable it")
            else:
                self.log.info("Uploading to Loadosophia.org: %s %s %s", project, result_file, monitoring_files)
                if not project:
                    self.log.info("Uploading to default project, please set loadosophia.project option to change this")
                if not result_file or not os.path.exists(result_file) or not os.path.getsize(result_file):
                    self.log.warning("Empty results file, skip Loadosophia.org uploading: %s", result_file)
                else:
                    return self.__send_checked_results(project, result_file, monitoring_files)

    def __send_checked_results(self, project, result_file, monitoring_files):
        """ internal wrapper to send request """
        # Create the form with simple fields
        form = MultiPartForm()
        form.add_field('projectKey', project)
        form.add_field('token', self.token)

        # Add main file
        form.add_file_as_string('jtl_file', self.file_prefix + os.path.basename(result_file) + ".gz",
                                self.__get_gzipped_file(result_file))

        index = 0
        for mon_file in monitoring_files:
            if not mon_file or not os.path.exists(mon_file) or not os.path.getsize(mon_file):
                self.log.warning("Skipped mon file: %s", mon_file)
                continue
            form.add_file_as_string('perfmon_' + str(index), self.file_prefix + os.path.basename(mon_file) + ".gz",
                                    self.__get_gzipped_file(mon_file))
            index += 1

        # Build the request
        request = urllib2.Request(self.address + "api/file/upload/?format=json")
        request.add_header('User-Agent', 'Yandex.Tank Loadosophia Uploader Module')
        body = str(form)
        request.add_header('Content-Type', form.get_content_type())
        request.add_header('Content-Length', len(body))
        request.add_data(body)

        response = urllib2.urlopen(request)
        if response.getcode() != 200:
            self.log.debug("Full loadosophia.org response: %s", response.read())
            msg = "Loadosophia.org upload failed, response code %s instead of 200, see log for full response text"
            raise RuntimeError(msg % response.getcode())

        resp_str = response.read()
        try:
            res = json.loads(resp_str)
        except Exception, exc:
            self.log.debug("Failed to load json from str: %s", resp_str)
            raise exc
        self.results_url = self.address + 'api/file/status/' + res[0]['QueueID'] + '/?redirect=true'
        return res[0]['QueueID']

    @staticmethod
    def __get_gzipped_file(result_file):
        """ gzip file """
        out = StringIO.StringIO()
        fhandle = gzip.GzipFile(fileobj=out, mode='w')
        fhandle.write(open(result_file, 'r').read())
        fhandle.close()
        return out.getvalue()

    def get_test_by_upload(self, queue_id):
        self.log.info("Waiting for Loadosophia.org to process file...")

        while True:
            time.sleep(1)
            status = self.get_upload_status(queue_id)
            if status['UserError']:
                raise HTTPError("Loadosophia processing error: " + status['UserError'])

            if int(status['status']) == self.STATUS_DONE:
                self.results_url = self.address + 'gui/' + status['TestID'] + '/'
                return status['TestID']

    def get_upload_status(self, queue_id):
        self.log.debug("Requesting file status: %s", queue_id)
        form = MultiPartForm()
        form.add_field('token', self.token)

        request = urllib2.Request(self.address + "api/file/status/" + queue_id + "/?format=json")
        request.add_header('User-Agent', 'Yandex.Tank Loadosophia Uploader Module')
        body = str(form)
        request.add_header('Content-Type', form.get_content_type())
        request.add_header('Content-Length', len(body))
        request.add_data(body)

        response = urllib2.urlopen(request)
        if response.getcode() != 200:
            self.log.debug("Full loadosophia.org response: %s", response.read())
            msg = "Loadosophia.org request failed, response code %s instead of 200, see log for full response text"
            raise RuntimeError(msg % response.getcode())

        res = json.loads(response.read())
        self.log.debug("Status info: %s", res)
        return res[0]

    def set_color_flag(self, test_id, color):
        form = MultiPartForm()
        form.add_field('token', self.token)

        request = urllib2.Request(self.address + "api/test/edit/color/" + test_id + "/?format=json&color=" + color)
        request.add_header('User-Agent', 'Yandex.Tank Loadosophia Uploader Module')
        body = str(form)
        request.add_header('Content-Type', form.get_content_type())
        request.add_header('Content-Length', len(body))
        request.add_data(body)

        response = urllib2.urlopen(request)
        if response.getcode() != 204:
            self.log.debug("Full loadosophia.org response: %s", response.read())
            msg = "Loadosophia.org request failed, response code %s instead of 204, see log for full response text"
            raise RuntimeError(msg % response.getcode())

    def set_test_title(self, test_id, title):
        self.log.debug("Set test title: %s", title)
        form = MultiPartForm()
        form.add_field('token', self.token)

        request = urllib2.Request(
            self.address + "api/test/edit/title/" + test_id + "/?format=json&" + urllib.urlencode({"title": title}))
        request.add_header('User-Agent', 'Yandex.Tank Loadosophia Uploader Module')
        body = str(form)
        request.add_header('Content-Type', form.get_content_type())
        request.add_header('Content-Length', len(body))
        request.add_data(body)

        response = urllib2.urlopen(request)
        if response.getcode() != 204:
            self.log.debug("Full loadosophia.org response: %s", response.read())
            msg = "Loadosophia.org request failed, response code %s instead of 204, see log for full response text"
            raise RuntimeError(msg % response.getcode())

    def start_online(self, project, title):
        self.log.info("Initiating Loadosophia.org active test...")
        data = urllib.urlencode({'projectKey': project, 'token': self.token, 'title': title})

        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookie_jar))
        url = self.address + "api/active/receiver/start/"
        response = opener.open(url, data)
        if response.getcode() != 201:
            self.log.warn("Failed to start active test: %s", response.getcode())
            self.log.debug("Failed to start active test: %s", response.read())
            self.cookie_jar.clear_session_cookies()

        online_id = json.loads(response.read())
        return self.address + "gui/active/" + online_id['OnlineID'] + '/'

    def end_online(self):
        self.log.debug("Ending Loadosophia online test")
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookie_jar))
        url = self.address + "api/active/receiver/stop/"
        response = opener.open(url)
        if response.getcode() != 205:
            self.log.warn("Failed to end active test: %s", response.getcode())
            self.log.debug("Failed to end active test: %s", response.read())
        self.cookie_jar.clear_session_cookies()

    def send_online_data(self, data_buffer):
        data = []
        for sec in data_buffer:
            item = sec.overall
            json_item = {
                "ts": str(sec.time),
                "threads": item.active_threads,
                "rps": item.RPS,
                "planned_rps": item.planned_requests,
                "avg_rt": item.avg_response_time,
                "quantiles": item.quantiles,
                "rc": item.http_codes,
                "net": item.net_codes
            }
            data.append(json_item)

        self.log.debug("Sending online data: %s", json.dumps(data))
        data_str = urllib.urlencode({'data': json.dumps(data)})

        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookie_jar))
        url = self.address + "api/active/receiver/data/"
        response = opener.open(url, data_str)
        if response.getcode() != 202:
            self.log.warn("Failed to push data: %s", response.getcode())


# =================================================================


class MultiPartForm(object):
    """Accumulate the data to be used when posting a form.
    http://blog.doughellmann.com/2009/07/pymotw-urllib2-library-for-opening-urls.html """

    def __init__(self):
        self.form_fields = []
        self.files = []
        self.boundary = mimetools.choose_boundary()
        return

    def get_content_type(self):
        """ returns content type """
        return 'multipart/form-data; boundary=%s' % self.boundary

    def add_field(self, name, value):
        """Add a simple field to the form data."""
        self.form_fields.append((name, value))
        return

    def add_file_as_string(self, fieldname, filename, body, mimetype=None):
        """ add raw string file """
        if mimetype is None:
            mimetype = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        self.files.append((fieldname, filename, mimetype, body))
        return

    def add_file(self, fieldname, filename, file_handle, mimetype=None):
        """Add a file to be uploaded."""
        body = file_handle.read()
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
            [part_boundary,
             'Content-Disposition: form-data; name="%s"' % name,
             '',
             value, ]
            for name, value in self.form_fields
        )

        # Add the files to upload
        parts.extend(
            [part_boundary,
             'Content-Disposition: file; name="%s"; filename="%s"' % (field_name, filename),
             'Content-Type: %s' % content_type,
             '',
             body, ]
            for field_name, filename, content_type, body in self.files
        )

        # Flatten the list and add closing boundary marker,
        # then return CR+LF separated data
        flattened = list(itertools.chain(*parts))
        flattened.append('--' + self.boundary + '--')
        flattened.append('')
        return '\r\n'.join(flattened)
