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
        return console.log("Connection opened...");
      };
    })(this));
    conn.on('disconnect', (function(_this) {
      return function() {
        return console.log("Connection closed...");
      };
    })(this));
    return conn.on('message', (function(_this) {
      return function(msg) {};
    })(this));
  });

  app.filter("metricsToSeries", function() {
    return function(metrics) {
      var name, points, _results;
      _results = [];
      for (name in metrics) {
        points = metrics[name];
        _results.push({
          name: name,
          color: 'steelblue',
          data: points.map(function(p) {
            return {
              x: p[0],
              y: p[1]
            };
          })
        });
      }
      return _results;
    };
  });

  app.directive("rickshaw", function() {
    return {
      restrict: "E",
      replace: true,
      template: "<div></div>",
      scope: {
        series: '='
      },
      link: function(scope, element, attrs) {
        var graph;
        graph = new Rickshaw.Graph({
          element: element[0],
          renderer: attrs.renderer,
          series: scope.series,
          width: attrs.width,
          height: attrs.height
        });
        return graph.render();
      }
    };
  });

}).call(this);
