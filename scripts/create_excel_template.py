import pandas as pd
import os
from datetime import datetime

def create_excel_template(output_path=""):
    """
    Tạo file Excel mẫu cho việc import dữ liệu vào hệ thống.
    """
    # Tạo dữ liệu mẫu cho sheet sinh viên
    student_data = {
        'mã sinh viên': ['SV001', 'SV002', 'SV003'],
        'tên sinh viên': ['Nguyễn Văn A', 'Trần Thị B', 'Lê Văn C'],
        'giới tính': ['Nam', 'Nữ', 'Nam'],
        'lớp': ['CNTT1', 'CNTT2', 'HTTT1'],
        'gmail': ['nguyenvana@example.com', 'tranthib@example.com', 'levanc@example.com'],
        'danh sách môn đăng kí': ['MON001,MON002', 'MON001,MON003', 'MON002,MON003']
    }
    
    # Tạo dữ liệu mẫu cho sheet môn thi
    subject_data = {
        'mã môn': ['MON001', 'MON002', 'MON003'],
        'tên môn': ['Lập trình Python', 'Cơ sở dữ liệu', 'Mạng máy tính'],
        'thời lượng thi (phút)': [90, 120, 90],
        'danh sách sinh viên đăng kí môn': ['SV001,SV002', 'SV001,SV003', 'SV002,SV003']
    }
    
    # Tạo dữ liệu mẫu cho sheet giảng viên
    teacher_data = {
        'mã giảng viên': ['GV001', 'GV002', 'GV003'],
        'tên giảng viên': ['PGS.TS Phạm Văn D', 'TS. Trần Thị E', 'ThS. Nguyễn Văn F'],
        'gmail': ['phamvand@example.com', 'tranthie@example.com', 'nguyenvanf@example.com']
    }
    
    # Tạo dữ liệu mẫu cho sheet phòng thi
    room_data = {
        'mã phòng thi': ['P101', 'P102', 'P103', 'P201', 'P202'],
        'sức chứa': [40, 35, 45, 30, 50]
    }
    
    # Tạo dữ liệu mẫu cho sheet lớp học
    class_data = {
        'mã lớp': ['CNTT1', 'CNTT2', 'HTTT1'],
        'tên lớp': ['Công nghệ thông tin 1', 'Công nghệ thông tin 2', 'Hệ thống thông tin 1'],
        'khoa bộ môn': ['Khoa CNTT', 'Khoa CNTT', 'Khoa CNTT'],
        'khóa': [2021, 2022, 2023]
    }
    
    # Tạo dataframes
    student_df = pd.DataFrame(student_data)
    subject_df = pd.DataFrame(subject_data)
    teacher_df = pd.DataFrame(teacher_data)
    room_df = pd.DataFrame(room_data)
    class_df = pd.DataFrame(class_data)
    
    # Tạo tên file với timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not output_path:
        output_path = f"import_template_{timestamp}.xlsx"
    
    # Tạo file Excel với 5 sheet
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        student_df.to_excel(writer, sheet_name='sinh viên', index=False)
        subject_df.to_excel(writer, sheet_name='môn thi', index=False)
        teacher_df.to_excel(writer, sheet_name='giảng viên', index=False)
        room_df.to_excel(writer, sheet_name='phòng thi', index=False)
        class_df.to_excel(writer, sheet_name='lớp học', index=False)
    
    print(f"Đã tạo file Excel mẫu tại: {os.path.abspath(output_path)}")
    return os.path.abspath(output_path)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Tạo file Excel mẫu cho import dữ liệu")
    parser.add_argument("--output", "-o", help="Đường dẫn đến file Excel đầu ra")
    
    args = parser.parse_args()
    create_excel_template(args.output)
