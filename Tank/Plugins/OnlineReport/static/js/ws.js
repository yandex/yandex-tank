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
        return scope.$watch('series', function() {
          if (scope.series != null) {
            return graph.render();
          }
        });
      }
    };
  });

}).call(this);
