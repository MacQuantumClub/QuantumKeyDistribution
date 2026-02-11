#!/bin/bash

idf.py -p /dev/ttyUSB0 reconfigure build flash
rm sdkconfig
idf.py -B slave -DSDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.defaults.slave" -p /dev/ttyUSB1 reconfigure build flash monitor
rm sdkconfig
