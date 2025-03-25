#!/bin/bash
# Simple script to ensure static directories exist

mkdir -p app/static/css
mkdir -p app/static/js
mkdir -p app/static/images

# Copy CSS and JS if they exist in the root
if [ -f "css/styles.css" ]; then
    cp css/styles.css app/static/css/
fi

if [ -f "js/main.js" ]; then
    cp js/main.js app/static/js/
fi

echo "Static directories created!"
