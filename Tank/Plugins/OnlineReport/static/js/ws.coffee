app = angular.module("ng-tank-report", [])

app.controller "TankReport", ($scope) ->
  $scope.status = "Disconnected"
  $scope.overallData = if document.cached_data.responses then document.cached_data.responses.overall else {}
  $scope.monitoringData = document.cached_data.monitoring
  conn = new io.connect("http://#{window.location.host}")
  conn.on 'connect', () =>
    console.log("Connection opened...")
    $scope.status = "Connected"
    $scope.$apply()
    console.log document.cached_data

  conn.on 'disconnect', () =>
    console.log("Connection closed...")
    $scope.status = "Disonnected"
    $scope.$apply()
  conn.on 'message', (msg) =>
    $scope.tankData = JSON.parse msg
    $scope.$apply()
