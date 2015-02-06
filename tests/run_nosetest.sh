#!/bin/bash
nosetests --with-xunit --all-modules --traverse-namespace --with-coverage --cover-inclusive --cover-erase --cover-package=Tank $@

