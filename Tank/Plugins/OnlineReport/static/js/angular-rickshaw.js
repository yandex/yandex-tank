
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
        var getSettings, graph, update;
        getSettings = function(el) {
          var settings;
          settings = angular.copy(scope.options);
          settings.element = el;
          settings.series = scope.series;
          return settings;
        };
        update = function() {
          var graph, graphEl, highlighter, hoverConfig, hoverDetail, i, legend, legendEl, mainEl, palette, settings, shelving, time, xAxis, xAxisConfig, yAxis, yAxisConfig;
          mainEl = angular.element(element);
          mainEl.append(graphEl);
          mainEl.empty();
          graphEl = $compile("<div></div>")(scope);
          mainEl.append(graphEl);
          settings = getSettings(graphEl[0]);
          graph = new Rickshaw.Graph(settings);
          if (scope.features && scope.features.hover) {
            hoverConfig = {
              graph: graph
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
          graph.render();
          if (scope.features && scope.features.xAxis) {
            xAxisConfig = {
              graph: graph
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
              graph: graph
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
              graph: graph,
              element: legendEl[0]
            });
            if (scope.features.legend.toggle) {
              shelving = new Rickshaw.Graph.Behavior.Series.Toggle({
                graph: graph,
                legend: legend
              });
            }
            if (scope.features.legend.highlight) {
              highlighter = new Rickshaw.Graph.Behavior.Series.Highlight({
                graph: graph,
                legend: legend
              });
            }
          }
        };
        graph = void 0;
        scope.$watch("options", function(newValue, oldValue) {
          if (!angular.equals(newValue, oldValue)) {
            update();
          }
        });
        scope.$watch("series", function(newValue, oldValue) {
          console.log(newValue);
          if (!angular.equals(newValue, oldValue)) {
            update();
          }
        });
        scope.$watch("features", function(newValue, oldValue) {
          if (!angular.equals(newValue, oldValue)) {
            update();
          }
        });
        update();
      },
      controller: function($scope, $element, $attrs) {}
    };
  });

}).call(this);
