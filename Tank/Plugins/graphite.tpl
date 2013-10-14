<html>
<body>

<h2>Overall quantiles and average response time</h2>
<img src="http://{host}/render/?width={width}&height={height}&from={start_time}&until={end_time}&target=aliasByMetric(one_sec.yandex_tank.overall.quantiles.{{25,50,75,80,90,95,99}}_0)&target=aliasByMetric(one_sec.yandex_tank.overall.avg_response_time)" />

<h2>RPS by marker</h2>
<img src="http://{host}/render/?width={width}&height={height}&from={start_time}&until={end_time}&target=one_sec.yandex_tank.markers.*.RPS&target=one_sec.yandex_tank.overall.RPS" />

<h2>Average response time by marker</h2>
<img src="http://{host}/render/?width={width}&height={height}&from={start_time}&until={end_time}&target=aliasByNode(one_sec.yandex_tank.overall.avg_response_time,2)&target=aliasByNode(one_sec.yandex_tank.markers.*.avg_response_time,3)" />

<h2>HTTP codes</h2>
<img src="http://{host}/render/?width={width}&height={height}&from={start_time}&until={end_time}&target=aliasByMetric(one_sec.yandex_tank.overall.http_codes.*)" />

<h2>NET codes</h2>
<img src="http://{host}/render/?width={width}&height={height}&from={start_time}&until={end_time}&target=aliasByMetric(one_sec.yandex_tank.overall.net_codes.*)" />

<h2>Cumulative quantiles and average response time</h2>
<img src="http://{host}/render/?width={width}&height={height}&from={start_time}&until={end_time}&target=aliasByMetric(one_sec.yandex_tank.cumulative.quantiles.{{25,50,75,80,90,95,99}}_0)&target=aliasByMetric(one_sec.yandex_tank.cumulative.avg_response_time)" />

<body>
<html>