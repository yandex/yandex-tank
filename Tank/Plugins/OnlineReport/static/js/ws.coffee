conn = new io.connect("http://#{window.location.host}")
conn.on 'connect', () => console.log("Connection opened...")
conn.on 'disconnect', () => console.log("Connection closed...")
conn.on 'message', (msg) =>
  console.log JSON.parse msg
  $("#msg").append("<p>#{msg}</p>")
