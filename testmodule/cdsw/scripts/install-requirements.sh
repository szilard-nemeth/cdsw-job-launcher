#!/bin/bash
set -x

echo "Uninstalling package: cdsw-example-module"
set +e
pip3 -V
pip3 show cdsw-example-module
pip3 uninstall -y cdsw-example-module

set -e
echo $@
if [ $# -ne 1 ]; then
    echo "Usage: $0 <execution mode>"
    echo "Example: $0 cloudera --> Uses execution mode: 'cloudera'"
    echo "Example: $0 upstream --> Uses execution mode: 'upstream'"
    exit 1
fi

EXEC_MODE="$1"
echo "Installing package: cdsw-example-module"
pip3 install cdsw-example-module --force-reinstall
pip3 show cdsw-example-module