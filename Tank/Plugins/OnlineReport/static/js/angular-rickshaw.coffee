###*
Based on https://github.com/ngyewch/angular-rickshaw
###
"use strict"

angular.module("angular-rickshaw", []).directive "rickshaw", ($compile) ->
  restrict: "EA"
  scope:
    options: "=rickshawOptions"
    series: "=rickshawSeries"
    features: "=rickshawFeatures"


  # replace: true,
  link: (scope, element, attrs) ->
    getSettings = (el) ->
      settings = angular.copy(scope.options)
      settings.element = el
      settings.series = scope.series
      settings
    update = ->
      mainEl = angular.element(element)
      mainEl.append graphEl
      mainEl.empty()
      graphEl = $compile("<div></div>")(scope)
      mainEl.append graphEl
      settings = getSettings(graphEl[0])
      scope.graph = new Rickshaw.Graph(settings)
      if scope.features and scope.features.hover
        hoverConfig = graph: scope.graph
        hoverConfig.xFormatter = scope.features.hover.xFormatter
        hoverConfig.yFormatter = scope.features.hover.yFormatter
        hoverConfig.formatter = scope.features.hover.formatter
        hoverDetail = new Rickshaw.Graph.HoverDetail(hoverConfig)
      if scope.features and scope.features.palette
        palette = new Rickshaw.Color.Palette(scheme: scope.features.palette)
        i = 0

        while i < settings.series.length
          settings.series[i].color = palette.color()
          i++
      scope.graph.render()
      if scope.features and scope.features.xAxis
        xAxisConfig = graph: scope.graph
        if scope.features.xAxis.timeUnit
          time = new Rickshaw.Fixtures.Time()
          xAxisConfig.timeUnit = time.unit(scope.features.xAxis.timeUnit)
        xAxis = new Rickshaw.Graph.Axis.Time(xAxisConfig)
        xAxis.render()
      if scope.features and scope.features.yAxis
        yAxisConfig = graph: scope.graph
        yAxisConfig.tickFormat = Rickshaw.Fixtures.Number[scope.features.yAxis.tickFormat]  if scope.features.yAxis.tickFormat
        yAxis = new Rickshaw.Graph.Axis.Y(yAxisConfig)
        yAxis.render()
      if scope.features and scope.features.legend
        legendEl = $compile("<div></div>")(scope)
        mainEl.append legendEl
        legend = new Rickshaw.Graph.Legend(
          graph: scope.graph
          element: legendEl[0]
        )
        if scope.features.legend.toggle
          shelving = new Rickshaw.Graph.Behavior.Series.Toggle(
            graph: scope.graph
            legend: legend
          )
        if scope.features.legend.highlight
          highlighter = new Rickshaw.Graph.Behavior.Series.Highlight(
            graph: scope.graph
            legend: legend
          )
      return
    scope.graph = undefined
    scope.$watch "options", (newValue, oldValue) ->
      update()  unless angular.equals(newValue, oldValue)
      return

    scope.$watch "series", (newValue, oldValue) ->
      update()  unless angular.equals(newValue, oldValue)
      return

    scope.$watch "features", (newValue, oldValue) ->
      update()  unless angular.equals(newValue, oldValue)
      return

    scope.$on "DataUpdated", () ->
      scope.graph.update()

    update()

  controller: ($scope, $element, $attrs) ->
