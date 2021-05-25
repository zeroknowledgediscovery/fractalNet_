#!/bin/bash
pdoc --html ./cynet_utils -o ../docs -f -c latex_math=True

cd ../docs
mv cynet_utils/* .
