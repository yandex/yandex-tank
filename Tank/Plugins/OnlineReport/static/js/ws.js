(function() {
  var app, collect_subtree,
    __indexOf = [].indexOf || function(item) { for (var i = 0, l = this.length; i < l; i++) { if (i in this && this[i] === item) return i; } return -1; };

  app = angular.module("ng-tank-report", ["angular-rickshaw"]);

  collect_subtree = function(storage, subtree, ts) {
    var key, node, _results;
    _results = [];
    for (key in subtree) {
      node = subtree[key];
      if (typeof node === 'number' || typeof node === 'array') {
        _results.push(storage[key].push({
          x: ts,
          y: node
        }));
      } else {
        _results.push(collect_subtree(storage[key], node, ts));
      }
    }
    return _results;
  };

  app.controller("TankReport", function($scope) {
    var conn;
    $scope.status = "Disconnected";
    $scope.data = document.cached_data;
    $scope.updateData = function(tankData) {
      var data, storage, storages, ts;
      for (ts in tankData) {
        storages = tankData[ts];
        for (storage in storages) {
          data = storages[storage];
          collect_subtree($scope.data[storage], data, ts);
        }
      }
      return $scope.buildSeries();
    };
    $scope.buildSeries = function() {
      var areaGraphs, data, groupName, groups, hostname, monitoringData, name, overallData, quantiles, series;
      overallData = $scope.data.responses ? $scope.data.responses.overall : {};
      monitoringData = $scope.data.monitoring ? $scope.data.monitoring : {};
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
      return $scope.rps = {
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
    };
    $scope.buildSeries();
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
      return function(msg) {
        var tankData;
        tankData = JSON.parse(msg);
        return $scope.updateData(tankData);
      };
    })(this));
  });

}).call(this);
