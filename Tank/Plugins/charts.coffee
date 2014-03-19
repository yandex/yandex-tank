defaultColors = colors: [
   '#2f7ed8'
   '#0d233a'
   '#8bbc21'
   '#910000'
   '#1aadce'
   '#492970'
   '#f28f43'
   '#77a1e5'
   '#c42525'
   '#a6c96a'
]
stackedColors = [
  "#49006a"
  "#7a0177"
  "#ae017e"
  "#dd3497"
  "#f768a1"
  "#fa9fb5"
  "#fcc5c0"
  "#fde0dd"
  "#fff7f3"
  "#ffffff"
]
stackedGroups = ['quantiles', 'CPU', 'http_codes', 'net_codes', 'Memory', 'avg']
defaultPlotOptions = 
  spline:
    lineWidth: 2
    states:
      hover:
        lineWidth: 4
    marker:
      enabled: false
stackedPlotOptions = 
  area:
    lineWidth: 0
    stacking: 'normal'
    marker:
      enabled: false

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
  constructor: (parentContainer, @name, @data) ->
    btnHideLegend = $("
      <button class='btn'>
            <span class='glyphicon glyphicon-list' />
      </button>
    ")
    btnHideLegend.click =>
      if @chart
        @chart.legendToggle()
    @container = $('<div />',
      title: @name
    )
    chartGroup = $('<div />')
    btnHideLegend.appendTo chartGroup
    @container.appendTo chartGroup
    chartGroup.appendTo parentContainer
    @params = $(parentContainer).data()
  _update: ->
    @chart = new Highcharts.Chart
      title:
        text: @name
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
        type: if @name in stackedGroups then 'area' else 'spline'
        zoomType: 'xy'
        renderTo: $(@container)[0]

      plotOptions: if @name in stackedGroups then stackedPlotOptions else defaultPlotOptions
      colors: if @name in stackedGroups then stackedColors else defaultColors

      legend:
        layout: "horizontal"
        align: "center"
        verticalAlign: "bottom"
        borderWidth: 0

      series: @data

$(document).ready -> 
  $('.tank-charts').each ->
    chartGroup = $("""
      <div class="panel panel-default">
        <div class="panel-heading">
          <h3>Overall tank metrics</h3>
        </div>
        <div class="panel-body charts-container" />
      </div>
    """)
    chartGroup.appendTo this
    for name, group_data of document.tank_metrics.overall 
      data = ({
        name: key
        data: ([v[0] * 1000, v[1]] for v in value)
      } for key, value of group_data).sort (a, b) ->
        if name in ['quantiles']
          return if parseFloat(a.name) <= parseFloat(b.name) then 1 else -1
        else
          return if a.name >= b.name then 1 else -1

      new GraphiteChart(chartGroup.find('.charts-container'), name, data)._update()
    for caseName, caseData of document.tank_metrics.cases
      chartGroup = $("""
        <div class="panel panel-default">
          <div class="panel-heading">
            <h3>Metrics for '#{caseName}' case</h3>
          </div>
          <div class="panel-body charts-container" />
        </div>
      """)
      chartGroup.appendTo this
      for name, group_data of caseData
        data = ({
          name: key
          data: ([v[0] * 1000, v[1]] for v in value)
        } for key, value of group_data).sort (a, b) ->
          if name in ['quantiles']
            return if parseFloat(a.name) <= parseFloat(b.name) then 1 else -1
          else
            return if a.name >= b.name then 1 else -1

        new GraphiteChart(chartGroup.find('.charts-container'), name, data)._update()
  $('.monitoring-charts').each ->
    for host, host_data of document.tank_metrics.monitoring
      chartGroup = $("""
        <div class="panel panel-default">
          <div class="panel-heading">
            <h3>Metrics for #{host}</h3>
          </div>
          <div class="panel-body charts-container" />
        </div>
      """)
      chartGroup.appendTo this
      for name, group_data of host_data
        data = ({
          name: key
          data: ([v[0] * 1000, v[1]] for v in value)
        } for key, value of group_data).sort (a, b) ->
          if name in ['quantiles']
            if parseFloat(a.name) <= parseFloat(b.name) then 1 else -1
          else
            if a.name >= b.name then 1 else -1
        new GraphiteChart(chartGroup.find('.charts-container'), name, data)._update()
