conn = new io.connect("http://#{window.location.host}")
conn.on 'connect', () =>
  console.log("Connection opened...")
  console.log document.cached_data

conn.on 'disconnect', () => console.log("Connection closed...")
conn.on 'message', (msg) =>
  console.log JSON.parse msg
