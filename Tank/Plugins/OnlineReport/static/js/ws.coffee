conn = new io.connect("http://#{window.location.host}")
conn.on 'connect', () => alert("Connection opened...")
conn.on 'disconnect', () => alert("Connection closed...")
conn.on 'message', (msg) => $("#msg").append("<p>#{msg}</p>")
