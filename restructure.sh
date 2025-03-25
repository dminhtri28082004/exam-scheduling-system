#!/bin/bash

echo "===== Bắt đầu cập nhật cấu trúc thư mục dự án ====="

# Bước 1: Chuẩn bị
./prepare.sh
if [ $? -ne 0 ]; then
    echo "Quá trình chuẩn bị không thành công. Vui lòng kiểm tra lỗi và thử lại."
    exit 1
fi

# Bước 2: Tạo cấu trúc thư mục mới
echo "Tạo cấu trúc thư mục mới..."
./setup.sh
if [ $? -ne 0 ]; then
    echo "Không thể tạo cấu trúc thư mục mới. Vui lòng kiểm tra lỗi và thử lại."
    exit 1
fi

# Bước 3: Di chuyển các file
echo "Di chuyển các file sang vị trí mới..."
./migrate.sh
if [ $? -ne 0 ]; then
    echo "Gặp lỗi khi di chuyển các file. Vui lòng kiểm tra lỗi và thử lại."
    exit 1
fi

# Bước 4: Cập nhật đường dẫn import
echo "Cập nhật đường dẫn import trong mã nguồn..."
./update_imports.sh
if [ $? -ne 0 ]; then
    echo "Gặp lỗi khi cập nhật đường dẫn import. Vui lòng kiểm tra lỗi và thử lại."
    exit 1
fi

# Kết thúc
echo "===== Đã hoàn tất cập nhật cấu trúc thư mục ====="
echo "Vui lòng kiểm tra lại ứng dụng để đảm bảo mọi thứ hoạt động bình thường."
echo "Nếu có vấn đề, bạn có thể phục hồi từ thư mục backup đã tạo ở bước 1."
