#!/bin/bash

# Đảm bảo tất cả các script có quyền thực thi
chmod +x setup.sh migrate.sh

# Tạo backup của dự án
echo "Tạo backup dự án..."
backup_dir="../backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p $backup_dir
cp -r . $backup_dir
echo "Đã tạo backup tại: $backup_dir"

# Kiểm tra trạng thái git nếu đang dùng git
if [ -d ".git" ]; then
    echo "Dự án đang sử dụng git, kiểm tra trạng thái..."
    git status
    echo "Gợi ý: Bạn nên commit hoặc stash các thay đổi trước khi tiếp tục."
    read -p "Bạn có muốn tiếp tục? (y/n) " confirm
    if [ "$confirm" != "y" ]; then
        echo "Hủy quá trình cập nhật."
        exit 1
    fi
fi

echo "Đã chuẩn bị xong. Bạn có thể chạy ./setup.sh để tạo cấu trúc thư mục mới."
