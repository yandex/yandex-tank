#!/usr/bin/env bash
printf "================\nConfig reference\n================\n" > config_reference.rst
for p in `find ../yandextank/plugins/ \( -name "schema.py" -o -name "schema.yaml" \)`
do
tank-docs-gen -o config_reference.rst --title `echo $p | awk '{split($0,a,"\/"); print a[5]}'` -a $p
done
