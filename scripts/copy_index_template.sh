#!/bin/bash

# Create directories if they don't exist
mkdir -p app/templates
mkdir -p app/templates/shared

# Check if shared index.html exists
if [ -f app/templates/shared/index.html ]; then
    # Copy shared index to root templates directory
    echo "Copying index.html from shared directory to templates root..."
    cp app/templates/shared/index.html app/templates/
else
    echo "Creating index.html in both locations..."
    # Create basic index template in both locations
    cat > app/templates/index.html << 'EOF'
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trang chủ - Hệ thống lập lịch thi</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="/static/css/styles.css">
</head>
<body>
    <div class="container mt-5">
        <div class="row justify-content-center">
            <div class="col-md-8 text-center">
                <h1>Hệ thống lập lịch thi</h1>
                <p class="lead">Quản lý và xem lịch thi của bạn dễ dàng</p>
                <div class="mt-4">
                    <a href="/ui/login" class="btn btn-primary btn-lg">Đăng nhập</a>
                </div>
            </div>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
EOF
    
    # Copy to shared directory too
    cp app/templates/index.html app/templates/shared/
fi

echo "Index template setup complete!"
