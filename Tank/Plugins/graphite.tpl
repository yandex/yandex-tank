<html>
<body>

<h2>Overall quantiles and average response time</h2>
<img src="http://${host}:${web_port}/render/?width=${width}&height=${height}&from=${start_time}&until=${end_time}&target=aliasByMetric(color(${prefix}.overall.quantiles.25_0,%22%23DD0000%22))&target=aliasByMetric(color(${prefix}.overall.quantiles.50_0,%22%23DD3800%22))&target=aliasByMetric(color(${prefix}.overall.quantiles.75_0,%22%23DD6e00%22))&target=aliasByMetric(color(${prefix}.overall.quantiles.90_0,%22%23DDDC00%22))&target=aliasByMetric(color(${prefix}.overall.quantiles.95_0,%22%23A6DD00%22))&target=aliasByMetric(color(${prefix}.overall.quantiles.99_0,%22%2338DD00%22))&target=aliasByMetric(alpha(color(${prefix}.overall.quantiles.100_0,%22green%22),0.5))&target=aliasByMetric(${prefix}.overall.avg_response_time)&areaMode=all" />

<h2>RPS by marker</h2>
<img src="http://${host}:${web_port}/render/?width=${width}&height=${height}&from=${start_time}&until=${end_time}&target=${prefix}.markers.*.RPS&target=${prefix}.overall.RPS" />

<h2>Average response time by marker</h2>
<img src="http://${host}:${web_port}/render/?width=${width}&height=${height}&from=${start_time}&until=${end_time}&target=aliasByNode(${prefix}.overall.avg_response_time,2)&target=aliasByNode(${prefix}.markers.*.avg_response_time,3)" />

<h2>HTTP codes</h2>
<img src="http://${host}:${web_port}/render/?width=${width}&height=${height}&from=${start_time}&until=${end_time}&target=aliasByMetric(${prefix}.overall.http_codes.*)" />

<h2>NET codes</h2>
<img src="http://${host}:${web_port}/render/?width=${width}&height=${height}&from=${start_time}&until=${end_time}&target=aliasByMetric(${prefix}.overall.net_codes.*)" />

<h2>Cumulative quantiles and average response time</h2>
<img src="http://${host}:${web_port}/render/?width=${width}&height=${height}&from=${start_time}&until=${end_time}&target=aliasByMetric(color(${prefix}.cumulative.quantiles.25_0,%22%23DD0000%22))&target=aliasByMetric(color(${prefix}.cumulative.quantiles.50_0,%22%23DD3800%22))&target=aliasByMetric(color(${prefix}.cumulative.quantiles.75_0,%22%23DD6e00%22))&target=aliasByMetric(color(${prefix}.cumulative.quantiles.90_0,%22%23DDDC00%22))&target=aliasByMetric(color(${prefix}.cumulative.quantiles.95_0,%22%23A6DD00%22))&target=aliasByMetric(color(${prefix}.cumulative.quantiles.99_0,%22%2338DD00%22))&target=aliasByMetric(alpha(color(${prefix}.cumulative.quantiles.100_0,%22green%22),0.5))&&target=aliasByMetric(${prefix}.cumulative.avg_response_time)&areaMode=all" />

<body>
<html>
