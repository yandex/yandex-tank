#! /bin/sh
$(dirname $0)/tank.py -o "tank.plugin_phantom=" -o "tank.plugin_ab=Tank/Plugins/ApacheBenchmark.py" "$@"
