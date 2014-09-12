(function() {
  var conn;

  conn = new io.connect("http://" + window.location.host);

  conn.on('connect', (function(_this) {
    return function() {
      console.log("Connection opened...");
      return console.log(document.cached_data);
    };
  })(this));

  conn.on('disconnect', (function(_this) {
    return function() {
      return console.log("Connection closed...");
    };
  })(this));

  conn.on('message', (function(_this) {
    return function(msg) {
      return console.log(JSON.parse(msg));
    };
  })(this));

}).call(this);
