(function() {
  var app;

  app = angular.module("ng-tank-report", []);

  app.controller("TankReport", function($scope) {
    var conn;
    $scope.status = "Disconnected";
    $scope.overallData = document.cached_data.responses ? document.cached_data.responses.overall : {};
    $scope.monitoringData = document.cached_data.monitoring;
    conn = new io.connect("http://" + window.location.host);
    conn.on('connect', (function(_this) {
      return function() {
        console.log("Connection opened...");
        $scope.status = "Connected";
        $scope.$apply();
        return console.log(document.cached_data);
      };
    })(this));
    conn.on('disconnect', (function(_this) {
      return function() {
        console.log("Connection closed...");
        $scope.status = "Disonnected";
        return $scope.$apply();
      };
    })(this));
    return conn.on('message', (function(_this) {
      return function(msg) {
        $scope.tankData = JSON.parse(msg);
        return $scope.$apply();
      };
    })(this));
  });

}).call(this);
