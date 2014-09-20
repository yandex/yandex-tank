
/**
Based on https://github.com/ngyewch/angular-rickshaw
 */

(function() {
  "use strict";
  angular.module("angular-rickshaw", []).directive("rickshaw", function($compile) {
    return {
      restrict: "EA",
      scope: {
        options: "=rickshawOptions",
        series: "=rickshawSeries",
        features: "=rickshawFeatures"
      },
      link: function(scope, element, attrs) {
        var getSettings, update;
        getSettings = function(el) {
          var settings;
          settings = angular.copy(scope.options);
          settings.element = el;
          settings.series = scope.series;
          return settings;
        };
        update = function() {
          var graphEl, highlighter, hoverConfig, hoverDetail, i, legend, legendEl, mainEl, palette, settings, shelving, time, xAxis, xAxisConfig, yAxis, yAxisConfig;
          mainEl = angular.element(element);
          mainEl.append(graphEl);
          mainEl.empty();
          graphEl = $compile("<div></div>")(scope);
          mainEl.append(graphEl);
          settings = getSettings(graphEl[0]);
          scope.graph = new Rickshaw.Graph(settings);
          if (scope.features && scope.features.hover) {
            hoverConfig = {
              graph: scope.graph
            };
            hoverConfig.xFormatter = scope.features.hover.xFormatter;
            hoverConfig.yFormatter = scope.features.hover.yFormatter;
            hoverConfig.formatter = scope.features.hover.formatter;
            hoverDetail = new Rickshaw.Graph.HoverDetail(hoverConfig);
          }
          if (scope.features && scope.features.palette) {
            palette = new Rickshaw.Color.Palette({
              scheme: scope.features.palette
            });
            i = 0;
            while (i < settings.series.length) {
              settings.series[i].color = palette.color();
              i++;
            }
          }
          scope.graph.render();
          if (scope.features && scope.features.xAxis) {
            xAxisConfig = {
              graph: scope.graph
            };
            if (scope.features.xAxis.timeUnit) {
              time = new Rickshaw.Fixtures.Time();
              xAxisConfig.timeUnit = time.unit(scope.features.xAxis.timeUnit);
            }
            xAxis = new Rickshaw.Graph.Axis.Time(xAxisConfig);
            xAxis.render();
          }
          if (scope.features && scope.features.yAxis) {
            yAxisConfig = {
              graph: scope.graph
            };
            if (scope.features.yAxis.tickFormat) {
              yAxisConfig.tickFormat = Rickshaw.Fixtures.Number[scope.features.yAxis.tickFormat];
            }
            yAxis = new Rickshaw.Graph.Axis.Y(yAxisConfig);
            yAxis.render();
          }
          if (scope.features && scope.features.legend) {
            legendEl = $compile("<div></div>")(scope);
            mainEl.append(legendEl);
            legend = new Rickshaw.Graph.Legend({
              graph: scope.graph,
              element: legendEl[0]
            });
            if (scope.features.legend.toggle) {
              shelving = new Rickshaw.Graph.Behavior.Series.Toggle({
                graph: scope.graph,
                legend: legend
              });
            }
            if (scope.features.legend.highlight) {
              highlighter = new Rickshaw.Graph.Behavior.Series.Highlight({
                graph: scope.graph,
                legend: legend
              });
            }
          }
        };
        scope.graph = void 0;
        scope.$watch("options", function(newValue, oldValue) {
          if (!angular.equals(newValue, oldValue)) {
            update();
          }
        });
        scope.$watch("series", function(newValue, oldValue) {
          if (!angular.equals(newValue, oldValue)) {
            update();
          }
        });
        scope.$watch("features", function(newValue, oldValue) {
          if (!angular.equals(newValue, oldValue)) {
            update();
          }
        });
        scope.$on("DataUpdated", function() {
          return scope.graph.update();
        });
        return update();
      },
      controller: function($scope, $element, $attrs) {}
    };
  });

}).call(this);
