#!/bin/bash

# Move index.html to the shared directory
mkdir -p app/templates/shared
mv app/templates/index.html app/templates/shared/

echo "Moved index.html to shared directory"
