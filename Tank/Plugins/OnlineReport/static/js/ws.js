(function() {
  var app,
    __indexOf = [].indexOf || function(item) { for (var i = 0, l = this.length; i < l; i++) { if (i in this && this[i] === item) return i; } return -1; };

  app = angular.module("ng-tank-report", ["angular-rickshaw"]);

  app.controller("TankReport", function($scope) {
    var areaGraphs, conn, data, groupName, groups, hostname, monitoringData, name, overallData, quantiles, series;
    $scope.status = "Disconnected";
    overallData = document.cached_data.responses ? document.cached_data.responses.overall : {};
    monitoringData = document.cached_data.monitoring ? document.cached_data.monitoring : {};
    areaGraphs = ['CPU', 'Memory'];
    $scope.monitoringData = (function() {
      var _results;
      _results = [];
      for (hostname in monitoringData) {
        groups = monitoringData[hostname];
        _results.push({
          hostname: hostname,
          groups: (function() {
            var _results1;
            _results1 = [];
            for (groupName in groups) {
              series = groups[groupName];
              _results1.push({
                name: groupName,
                features: {
                  palette: 'spectrum14',
                  hover: {},
                  xAxis: {},
                  yAxis: {},
                  legend: {
                    toggle: true,
                    highlight: true
                  }
                },
                options: {
                  renderer: __indexOf.call(areaGraphs, groupName) >= 0 ? 'area' : 'line'
                },
                series: (function() {
                  var _results2;
                  _results2 = [];
                  for (name in series) {
                    data = series[name];
                    _results2.push({
                      name: name,
                      data: data
                    });
                  }
                  return _results2;
                })()
              });
            }
            return _results1;
          })()
        });
      }
      return _results;
    })();
    quantiles = $scope.quantiles = {
      name: "Response time quantiles",
      features: {
        palette: 'classic9',
        hover: {},
        xAxis: {},
        yAxis: {},
        legend: {
          toggle: true,
          highlight: true
        }
      },
      options: {
        renderer: 'area',
        stack: false
      },
      series: ((function() {
        var _ref, _results;
        _ref = overallData.quantiles;
        _results = [];
        for (name in _ref) {
          data = _ref[name];
          _results.push({
            name: name,
            data: data
          });
        }
        return _results;
      })()).sort(function(a, b) {
        if (parseFloat(a.name) <= parseFloat(b.name)) {
          return 1;
        } else {
          return -1;
        }
      })
    };
    $scope.rps = {
      name: "Responses per second",
      features: {
        palette: 'spectrum14',
        hover: {},
        xAxis: {},
        yAxis: {},
        legend: {
          toggle: true,
          highlight: true
        }
      },
      options: {
        renderer: 'line'
      },
      series: [
        {
          name: 'RPS',
          data: overallData.RPS
        }
      ]
    };
    conn = new io.connect("http://" + window.location.host);
    conn.on('connect', (function(_this) {
      return function() {
        console.log("Connection opened...");
        $scope.status = "Connected";
        return $scope.$apply();
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
      return function(msg) {};
    })(this));
  });

}).call(this);
