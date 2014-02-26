defaultColors = ["#E67117","#8F623F","#6D3103","#F9AA6D","#F9CFB0","#E69717","#8F713F","#6D4403","#F9C36D","#F9DDB0","#1A5197","#2E435E","#032148","#6FA3E5","#A8C2E5","#0E8D84","#275855","#02433E","#63E3D9","#A0E3DE"]
defaultPlotOptions = 
  spline:
    lineWidth: 2
    states:
      hover:
        lineWidth: 4
    marker:
      enabled: false
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
  ,
    name: 'Average response time by marker'
    targets: [
      metric: "%p.overall.avg_response_time"
      function: "aliasByNode(%m, 2)"
    ,
      metric: "%p.markers.*.avg_response_time"
      function: "aliasByNode(%m, 3)"
    ]
  ,
    name: 'HTTP codes'
    targets: [
      metric: "%p.overall.http_codes.*"
      function: "aliasByMetric(%m)"
    ]
    chartType: 'area'
    plotOptions:
      area:
        lineWidth: 0
        stacking: 'normal'
        marker:
          enabled: false
  ,
    name: 'NET codes'
    targets: [
      metric: "%p.overall.net_codes.*"
      function: "aliasByMetric(%m)"
    ]
    chartType: 'area'
    plotOptions:
      area:
        lineWidth: 0
        stacking: 'normal'
        marker:
          enabled: false
  ,
    name: 'Cumulative quantiles'
    targets: [
      metric: "%p.cumulative.quantiles.100_0"
      function: "aliasByMetric(%m)"
    ,
      metric: "%p.cumulative.quantiles.99_0"
      function: "aliasByMetric(%m)"
    ,
      metric: "%p.cumulative.quantiles.95_0"
      function: "aliasByMetric(%m)"
    ,
      metric: "%p.cumulative.quantiles.90_0"
      function: "aliasByMetric(%m)"
    ,
      metric: "%p.cumulative.quantiles.75_0"
      function: "aliasByMetric(%m)"
    ,
      metric: "%p.cumulative.quantiles.50_0"
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
]

((Highcharts, UNDEFINED) ->
  return  unless Highcharts
  chartProto = Highcharts.Chart::
  legendProto = Highcharts.Legend::
  Highcharts.extend chartProto,
    legendSetVisibility: (display) ->
      chart = this
      legend = chart.legend
      legendAllItems = undefined
      legendAllItem = undefined
      legendAllItemLength = undefined
      legendOptions = chart.options.legend
      scroller = undefined
      extremes = undefined
      return  if legendOptions.enabled is display
      legendOptions.enabled = display
      unless display
        legendProto.destroy.call legend
        # fix for ex-rendered items - so they will be re-rendered if needed
        legendAllItems = legend.allItems
        if legendAllItems
          legendAllItem = 0
          legendAllItemLength = legendAllItems.length

          while legendAllItem < legendAllItemLength
            legendAllItems[legendAllItem].legendItem = UNDEFINED
            ++legendAllItem
        # fix for chart.endResize-eventListener and legend.positionCheckboxes()
        legend.group = {}
      chartProto.render.call chart
      unless legendOptions.floating
        scroller = chart.scroller
        if scroller and scroller.render
          # fix scrolller // @see renderScroller() in Highcharts
          extremes = chart.xAxis[0].getExtremes()
          scroller.render extremes.min, extremes.max
      return
    legendHide: ->
      @legendSetVisibility false
      return
    legendShow: ->
      @legendSetVisibility true
      return
    legendToggle: ->
      @legendSetVisibility @options.legend.enabled ^ true
      return

  return
) Highcharts

class GraphiteChart
  constructor: (parentContainer, @template) ->
    btnHideLegend = $("
      <button class='btn'>
            <span class='glyphicon glyphicon-list' />
      </button>
    ")
    btnHideLegend.click =>
      if @chart
        @chart.legendToggle()
    @container = $('<div />',
      title: @template.name
    )
    chartGroup = $('<div />')
    btnHideLegend.appendTo chartGroup
    @container.appendTo chartGroup
    chartGroup.appendTo parentContainer
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

        plotOptions: @template.plotOptions or defaultPlotOptions
        colors: @template.colors or defaultColors

        legend:
          layout: "vertical"
          align: "center"
          verticalAlign: "bottom"
          borderWidth: 0

        series: @_createTimeSeries(data)
      @chart.legendHide()

$(document).ready -> 
  $('.graphite-charts').each ->
    for template in templates
      template.chart = new GraphiteChart(this, template)
      template.chart._update()
