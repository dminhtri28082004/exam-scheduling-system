#!/bin/bash

# Tạo cấu trúc thư mục mới
mkdir -p app/api/v1/endpoints
mkdir -p app/core
mkdir -p app/db/repositories
mkdir -p app/models/domain
mkdir -p app/models/schemas
mkdir -p app/services
mkdir -p app/static/{css,js,images}
mkdir -p app/templates/{admin,student,shared}
mkdir -p app/utils
mkdir -p app/web
mkdir -p scripts
mkdir -p tests/{test_api,test_services}

# Tạo các file __init__.py cần thiết
touch app/__init__.py
touch app/api/__init__.py
touch app/api/v1/__init__.py
touch app/api/v1/endpoints/__init__.py
touch app/db/__init__.py
touch app/db/repositories/__init__.py
touch app/models/__init__.py
touch app/models/domain/__init__.py
touch app/models/schemas/__init__.py
touch app/services/__init__.py
touch app/utils/__init__.py
touch app/web/__init__.py
touch tests/__init__.py
touch tests/test_api/__init__.py
touch tests/test_services/__init__.py

echo "Cấu trúc thư mục đã được tạo!"
