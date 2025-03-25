#!/bin/bash

# Copy the base.html template from shared to the root templates directory
mkdir -p app/templates
if [ -f app/templates/shared/base.html ]; then
    echo "Copying base.html from shared directory to templates root..."
    cp app/templates/shared/base.html app/templates/
    echo "Base template copied successfully."
else
    echo "Error: Could not find app/templates/shared/base.html"
fi
