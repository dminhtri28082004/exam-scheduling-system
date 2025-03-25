#!/bin/bash

# Tạo thư mục mới trước khi di chuyển file
echo "Đảm bảo các thư mục đích tồn tại..."
mkdir -p app/core
mkdir -p app/db/database
mkdir -p app/models/domain
mkdir -p app/models/schemas
mkdir -p app/templates/shared
mkdir -p app/templates/student
mkdir -p app/templates/admin
mkdir -p scripts

# Function an toàn để di chuyển file
safe_move() {
    local src=$1
    local dest=$2
    local dest_dir=$(dirname "$dest")
    
    # Tạo thư mục đích nếu chưa tồn tại
    if [ ! -d "$dest_dir" ]; then
        mkdir -p "$dest_dir"
        echo "Đã tạo thư mục: $dest_dir"
    fi
    
    # Kiểm tra file nguồn tồn tại
    if [ -f "$src" ]; then
        # Kiểm tra file đích đã tồn tại
        if [ -f "$dest" ]; then
            echo "Cảnh báo: File đích đã tồn tại: $dest"
            echo "  Đang tạo bản sao: ${dest}.bak"
            cp "$dest" "${dest}.bak"
        fi
        mv "$src" "$dest"
        echo "Đã di chuyển: $src -> $dest"
    else
        echo "Cảnh báo: File nguồn không tồn tại: $src"
    fi
}

echo "Bắt đầu di chuyển các file..."

# Di chuyển các file cấu hình
safe_move app/config.py app/core/config.py
safe_move app/database.py app/db/database.py

# Di chuyển models
safe_move app/models/exam.py app/models/domain/exam.py
safe_move app/models/subject.py app/models/domain/subject.py
safe_move app/models/user.py app/models/domain/user.py
safe_move app/models/room.py app/models/domain/room.py
safe_move app/models/student.py app/models/domain/student.py
safe_move app/models/teacher.py app/models/domain/teacher.py
safe_move app/models/class_group.py app/models/domain/class_group.py
safe_move app/models/schedule.py app/models/domain/schedule.py
safe_move app/models/dto.py app/models/schemas/dto.py

# Di chuyển templates
safe_move app/templates/login.html app/templates/shared/login.html
safe_move app/templates/error.html app/templates/shared/error.html
safe_move app/templates/base.html app/templates/shared/base.html
safe_move app/templates/dashboard.html app/templates/shared/dashboard.html
safe_move app/templates/profile.html app/templates/shared/profile.html

safe_move app/templates/exams.html app/templates/student/exams.html
safe_move app/templates/exams_calendar.html app/templates/student/calendar.html

safe_move app/templates/admin_subjects.html app/templates/admin/subjects.html
safe_move app/templates/admin_rooms.html app/templates/admin/rooms.html
safe_move app/templates/admin_classes.html app/templates/admin/classes.html
safe_move app/templates/admin_users.html app/templates/admin/users.html
safe_move app/templates/admin_exams.html app/templates/admin/exams.html
safe_move app/templates/admin_scheduler.html app/templates/admin/scheduler.html
safe_move app/templates/admin_supervisors.html app/templates/admin/supervisors.html

# Di chuyển scripts
safe_move create_admin.py scripts/create_admin.py
safe_move create_excel_template.py scripts/create_excel_template.py
safe_move create_student.py scripts/create_student.py
safe_move check_users.py scripts/check_users.py
safe_move create_static_dirs.sh scripts/create_static_dirs.sh

echo "Di chuyển các file hoàn tất!"
