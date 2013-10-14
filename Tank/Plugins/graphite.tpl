<html>
<body>

<h2>Overall quantiles and average response time</h2>
<img src="http://{host}/render/?width={width}&height={height}&from={start_time}&until={end_time}&target=aliasByMetric({prefix}.overall.quantiles.{{25,50,75,80,90,95,99,100}}_0)&target=aliasByMetric({prefix}.overall.avg_response_time)" />

<h2>RPS by marker</h2>
<img src="http://{host}/render/?width={width}&height={height}&from={start_time}&until={end_time}&target={prefix}.markers.*.RPS&target={prefix}.overall.RPS" />

<h2>Average response time by marker</h2>
<img src="http://{host}/render/?width={width}&height={height}&from={start_time}&until={end_time}&target=aliasByNode({prefix}.overall.avg_response_time,2)&target=aliasByNode({prefix}.markers.*.avg_response_time,3)" />

<h2>HTTP codes</h2>
<img src="http://{host}/render/?width={width}&height={height}&from={start_time}&until={end_time}&target=aliasByMetric({prefix}.overall.http_codes.*)" />

<h2>NET codes</h2>
<img src="http://{host}/render/?width={width}&height={height}&from={start_time}&until={end_time}&target=aliasByMetric({prefix}.overall.net_codes.*)" />

<h2>Cumulative quantiles and average response time</h2>
<img src="http://{host}/render/?width={width}&height={height}&from={start_time}&until={end_time}&target=aliasByMetric({prefix}.cumulative.quantiles.{{25,50,75,80,90,95,99,100}}_0)&target=aliasByMetric({prefix}.cumulative.avg_response_time)" />

<body>
<html>