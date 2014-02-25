defaultColors = ["#E67117","#8F623F","#6D3103","#F9AA6D","#F9CFB0","#E69717","#8F713F","#6D4403","#F9C36D","#F9DDB0","#1A5197","#2E435E","#032148","#6FA3E5","#A8C2E5","#0E8D84","#275855","#02433E","#63E3D9","#A0E3DE"]
templates = [
    name: 'Quantiles'
    targets: [
      metric: "%p.overall.quantiles.100_0"
      function: "aliasByMetric(%m)"
    ,
      metric: "%p.overall.quantiles.99_0"
      function: "aliasByMetric(%m)"
    ,
      metric: "%p.overall.quantiles.95_0"
      function: "aliasByMetric(%m)"
    ,
      metric: "%p.overall.quantiles.90_0"
      function: "aliasByMetric(%m)"
    ,
      metric: "%p.overall.quantiles.75_0"
      function: "aliasByMetric(%m)"
    ,
      metric: "%p.overall.quantiles.50_0"
      function: "aliasByMetric(%m)"
    ]
    chartType: 'area'
    colors: ["green", "#38DD00", "#A6DD00", "#DDDC00", "#DD6e00", "#DD3800", "#DD0000"]
    plotOptions:
      area:
        lineWidth: 0
        stacking: 'normal'
        marker:
          enabled: false
  ,
    name: 'RPS by marker'
    targets: [
      metric: "%p.markers.*.RPS"
    ,
      metric: "%p.overall.RPS"
    ]
    plotOptions:
      spline:
        lineWidth: 2
        states:
          hover:
            lineWidth: 4
        marker:
          enabled: false
]

class GraphiteChart
  constructor: (parentContainer, @template) ->
    @container = $('<div />',
      title: @template.name
    )
    @container.appendTo parentContainer
    @params = $(parentContainer).data()
    @options = {
      format: 'json'
      tz: 'Europe/Moscow'
      maxDataPoints: 500
      from: @params.startTime
      until: @params.endTime
    }
  _makeOptions: ->
    ("#{key}=#{value}" for key, value of @options).join('&')
  _createTimeSeries: (chart_data) ->
    ({
      name: item.target
      data: ([point[1] * 1000, point[0]] for point in item.datapoints)
    } for item in chart_data)
  _makeTarget: (target) ->
    metric = target.metric.replace('%p', @params.prefix)
    if target.function?
      metric = target.function.replace('%m', metric)
    return metric
  _query: ->
    ("target=#{@_makeTarget(target)}" for target in @template.targets).join('&') + '&' + @_makeOptions()
  _update: ->
    link = "http://#{@params.host}:#{@params.webPort}/render?#{@_query()}"
    $(@container).attr('src', link)
    console.log @template.plotOptions
    $.ajax(link).done (data) =>
      @chart = new Highcharts.Chart
        title:
          text: @template.name
          x: -20
        xAxis:
          title:
            text: "Time"
          type: "datetime"
        yAxis:
          title:
            text: "Value"

          plotLines: [
            value: 0
            width: 1
            color: "#808080"
          ]

        tooltip:
          crosshairs: true

        chart:
          type: @template.chartType or 'spline'
          zoomType: 'xy'
          renderTo: $(@container)[0]

        plotOptions: @template.plotOptions
        colors: @template.colors or defaultColors

        legend:
          layout: "vertical"
          align: "center"
          verticalAlign: "bottom"
          borderWidth: 0

        series: @_createTimeSeries(data)

$(document).ready -> 
  $('.graphite-charts').each ->
    for template in templates
      template.chart = new GraphiteChart(this, template)
      template.chart._update()
