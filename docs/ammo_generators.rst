================
Ammo generators
================

**sample req-style ammo generator (python):**

``usage: cat data | python make_ammo.py``
For each line of 'data' file this script will generate phantom ammo.
Line format: ``GET||/url||case_tag||body(optional)``

.. code-block:: python

    #!/usr/bin/python
    # -*- coding: utf-8 -*-
  
    import sys
    
	
    def make_ammo(method, url, headers, case, body):
        """ makes phantom ammo """
        # http request w/o entity body template
        req_template = (
              "%s %s HTTP/1.1\r\n"
              "%s\r\n"
              "\r\n"
        )
    
        # http request with entity body template
        req_template_w_entity_body = (
              "%s %s HTTP/1.1\r\n"
              "%s\r\n"
              "Content-Length: %d\r\n"
              "\r\n"
              "%s\r\n"
        )
    
        if not body:
            req = req_template % (method, url, headers)
        else:
            req = req_template_w_entity_body % (method, url, headers, len(body), body)
    
        # phantom ammo template
        ammo_template = (
            "%d %s\n"
            "%s"
        )
  
        return ammo_template % (len(req), case, req)
  
  
    def main():
        for stdin_line in sys.stdin:
            try:
                method, url, case, body = stdin_line.split("||")
                body = body.strip()
            except ValueError:
                method, url, case = stdin_line.split("||")
                body = None

            method, url, case = method.strip(), url.strip(), case.strip()
        
            headers = "Host: hostname.com\r\n" + \
                "User-Agent: tank\r\n" + \
                "Accept: */*\r\n" + \
                "Connection: Close"

            sys.stdout.write(make_ammo(method, url, headers, case, body))

			
    if __name__ == "__main__":
        main()

**sample POST multipart form-data generator (python)**

.. code-block:: python

  #!/usr/bin/python
  # -*- coding: utf-8 -*-
  import requests
  
  def print_request(request):
      req = "{method} {path_url} HTTP/1.1\r\n{headers}\r\n{body}".format(
          method = request.method,
          path_url = request.path_url,
          headers = ''.join('{0}: {1}\r\n'.format(k, v) for k, v in request.headers.items()),
          body = request.body or "",
      )
      return "{req_size}\n{req}\r\n".format(req_size = len(req), req = req)
    
  #POST multipart form data
  def post_multipart(host, port, namespace, files, headers, payload):
      req = requests.Request(
          'POST',
          'https://{host}:{port}{namespace}'.format(
              host = host,
              port = port,
              namespace = namespace,
          ),
          headers = headers,
          data = payload,
          files = files
      )
      prepared = req.prepare()
      return print_request(prepared)

  if __name__ == "__main__":
      #usage sample below
      #target's hostname and port
      #this will be resolved to IP for TCP connection      
      host = 'test.host.ya.ru'
      port = '8080'
      namespace = '/some/path'
      #below you should specify or able to operate with
      #virtual server name on your target
      headers = {
          'Host': 'ya.ru'
      }
      payload = {
          'langName': 'en',
          'apikey': '123'
      }
      files = {
          # name, path_to_file, content-type, additional headers
          'file': ('image.jpeg', open('./imagex.jpeg', 'rb'), 'image/jpeg ', {'Expires': '0'})
      }
  
      print post_multipart(host, port, namespace, files, headers, payload)

