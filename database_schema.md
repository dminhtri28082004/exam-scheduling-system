# Database Schema - Hệ thống Lập lịch thi

## Collections

### users
- **_id**: ObjectId/String - ID của người dùng
- **id**: String - ID của người dùng (đồng nhất với _id)
- **email**: String - Email của người dùng (dùng để đăng nhập)
- **full_name**: String - Họ tên đầy đủ
- **hashed_password**: String - Mật khẩu đã mã hóa
- **role**: String - Vai trò, có thể là "admin", "teacher", hoặc "student"
- **is_active**: Boolean - Trạng thái hoạt động của tài khoản
- **created_at**: DateTime - Thời gian tạo tài khoản
- **updated_at**: DateTime - Thời gian cập nhật gần nhất

### students
- **_id**: ObjectId/String - ID học sinh
- **id**: String - ID đồng nhất với _id
- **student_id**: String - Mã số sinh viên
- **full_name**: String - Họ tên đầy đủ
- **gender**: String - Giới tính
- **class_name**: String - Lớp học
- **email**: String - Email liên hệ
- **registered_subjects**: Array - Danh sách mã môn học đã đăng ký
- **created_at**: DateTime - Thời gian tạo
- **updated_at**: DateTime - Thời gian cập nhật

### teachers
- **_id**: ObjectId/String - ID giáo viên
- **id**: String - ID đồng nhất với _id
- **teacher_id**: String - Mã số giáo viên
- **full_name**: String - Họ tên đầy đủ
- **email**: String - Email liên hệ
- **created_at**: DateTime - Thời gian tạo
- **updated_at**: DateTime - Thời gian cập nhật
- **exam_count**: Number - Số lượng kỳ thi được phân công giám sát (không lưu trữ, tính toán động)

### subjects
- **_id**: ObjectId/String - ID môn học
- **id**: String - ID đồng nhất với _id
- **code**: String - Mã môn học
- **name**: String - Tên môn học
- **duration**: Number - Thời lượng thi (phút)
- **registered_students**: Array - Danh sách mã sinh viên đăng ký môn học
- **created_at**: DateTime - Thời gian tạo
- **updated_at**: DateTime - Thời gian cập nhật

### rooms
- **_id**: ObjectId/String - ID phòng thi
- **id**: String - ID đồng nhất với _id
- **room_id**: String - Mã phòng
- **name**: String - Tên phòng (tùy chọn)
- **building**: String - Tòa nhà (tùy chọn)
- **capacity**: Number - Sức chứa (số lượng sinh viên tối đa)
- **created_at**: DateTime - Thời gian tạo
- **updated_at**: DateTime - Thời gian cập nhật

### exams
- **_id**: ObjectId/String - ID kỳ thi
- **id**: String - ID đồng nhất với _id
- **subject_id**: String - ID môn học
- **room_id**: String - ID phòng thi
- **start_time**: DateTime - Thời gian bắt đầu
- **end_time**: DateTime - Thời gian kết thúc
- **supervisor_ids**: Array - Danh sách ID giáo viên giám sát
- **max_students**: Number - Số lượng sinh viên tối đa
- **student_ids**: Array - Danh sách ID sinh viên tham gia
- **created_at**: DateTime - Thời gian tạo
- **updated_at**: DateTime - Thời gian cập nhật

### classes
- **_id**: ObjectId/String - ID lớp học
- **class_id**: String - Mã lớp học
- **name**: String - Tên lớp
- **department**: String - Tên khoa/bộ môn
- **year**: Number - Niên khóa
- **student_count**: Number - Số lượng sinh viên (có thể tính toán động)
- **created_at**: DateTime - Thời gian tạo
- **updated_at**: DateTime - Thời gian cập nhật

### schedule_configs
- **_id**: ObjectId/String - ID cấu hình
- **exam_period_name**: String - Tên kỳ thi
- **start_date**: DateTime - Ngày bắt đầu kỳ thi
- **end_date**: DateTime - Ngày kết thúc kỳ thi
- **first_exam_time**: String - Thời gian bắt đầu ca thi đầu tiên trong ngày (HH:MM:SS)
- **last_exam_time**: String - Thời gian kết thúc ca thi cuối cùng trong ngày (HH:MM:SS)
- **supervisors_per_room**: Number - Số lượng giám thị cho mỗi phòng thi
- **created_by**: String - ID người tạo (thường là admin)
- **created_at**: DateTime - Thời gian tạo
- **updated_at**: DateTime - Thời gian cập nhật

## Mối quan hệ

1. **users - students/teachers**:
   - Sinh viên và giáo viên có thể đăng nhập thông qua bảng users
   - Liên kết qua trường email

2. **students - subjects**:
   - Môn học có nhiều sinh viên đăng ký (registered_students)
   - Sinh viên đăng ký nhiều môn học (registered_subjects)

3. **exams - subjects**:
   - Mỗi kỳ thi liên kết với một môn học (subject_id)

4. **exams - rooms**:
   - Mỗi kỳ thi diễn ra tại một phòng thi (room_id)

5. **exams - teachers**:
   - Mỗi kỳ thi có nhiều giám thị (supervisor_ids)

6. **exams - students**:
   - Mỗi kỳ thi có nhiều sinh viên tham gia (student_ids)

7. **students - classes**:
   - Sinh viên thuộc về một lớp học (class_name liên kết với class_id)
