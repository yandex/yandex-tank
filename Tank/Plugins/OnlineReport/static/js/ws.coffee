app = angular.module("ng-tank-report", ["angular-rickshaw"])

app.controller "TankReport", ($scope) ->
  $scope.status = "Disconnected"
  overallData = if document.cached_data.responses then document.cached_data.responses.overall else {}
  monitoringData = if document.cached_data.monitoring then document.cached_data.monitoring else {}
  areaGraphs = ['CPU', 'Memory']
  $scope.monitoringData = (
    ({
      hostname: hostname
      groups: ({
        name: groupName
        features:
          palette: 'spectrum14'
          hover: {}
          xAxis: {}
          yAxis: {}
          legend:
            toggle: true
            highlight: true
        options:
          renderer: if groupName in areaGraphs then 'area' else 'line'
        series: ({
          name: name
          data: data
        } for name, data of series)
      } for groupName, series of groups)
    } for hostname, groups of monitoringData)
  )
  quantiles =
  $scope.quantiles =
    name: "Response time quantiles"
    features:
      palette: 'classic9'
      hover: {}
      xAxis: {}
      yAxis: {}
      legend:
        toggle: true
        highlight: true
    options:
      renderer: 'area'
      stack: false
    series: ({
      name: name
      data: data
    } for name, data of overallData.quantiles).sort (a, b) ->
      return if parseFloat(a.name) <= parseFloat(b.name) then 1 else -1
  $scope.rps =
    name: "Responses per second"
    features:
      palette: 'spectrum14'
      hover: {}
      xAxis: {}
      yAxis: {}
      legend:
        toggle: true
        highlight: true
    options:
      renderer: 'line'
    series: [
      name: 'RPS'
      data: overallData.RPS
    ]


  conn = new io.connect("http://#{window.location.host}")
  conn.on 'connect', () =>
    console.log("Connection opened...")
    $scope.status = "Connected"
    $scope.$apply()
    #console.log document.cached_data

  conn.on 'disconnect', () =>
    console.log("Connection closed...")
    $scope.status = "Disonnected"
    $scope.$apply()
  conn.on 'message', (msg) =>
    #$scope.tankData = JSON.parse msg
    #$scope.$apply()
