from datetime import datetime, timedelta, time
from typing import List, Dict, Any
import logging
import random
import math
from bson.objectid import ObjectId

from app.models.domain.subject import Subject
from app.models.domain.room import Room
from app.models.domain.schedule import ScheduleConfig

class ExamScheduler:
    def __init__(self, config: ScheduleConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.teacher_assignments = {}  # Để theo dõi số lần phân công cho mỗi giáo viên
        self.teachers = []
        
    async def schedule_exams(self, db, subjects: List[Subject], rooms: List[Room]):
        """
        Lập lịch thi cho các môn học và phòng thi dựa trên cấu hình
        """
        self.logger.info(f"Starting exam scheduling for period: {self.config.start_date} to {self.config.end_date}")
        self.logger.info(f"Found {len(subjects)} subjects and {len(rooms)} rooms")
        
        # Kiểm tra dữ liệu đầu vào
        if not subjects:
            self.logger.warning("No subjects found. Cannot schedule exams.")
            return []
            
        if not rooms:
            self.logger.warning("No rooms found. Cannot schedule exams.")
            return []
        
        # Lọc môn học có sinh viên đăng ký
        valid_subjects = [s for s in subjects if s.registered_students]
        if not valid_subjects:
            self.logger.warning("No subjects with registered students found.")
            # Nếu không có môn học có sinh viên đăng ký, dùng tất cả môn học với giả định
            # mỗi môn có 20 sinh viên đăng ký để demo
            for subject in subjects:
                subject.registered_students = [f"DEMO_STUDENT_{i}" for i in range(1, 21)]
            valid_subjects = subjects
            
        # Lọc phòng có sức chứa
        valid_rooms = [r for r in rooms if r.capacity > 0]
        if not valid_rooms:
            self.logger.warning("No rooms with capacity > 0 found.")
            # Nếu không có phòng hợp lệ, dùng giá trị mặc định
            for room in rooms:
                room.capacity = 30
            valid_rooms = rooms
        
        # Sắp xếp môn học theo số sinh viên đăng ký (giảm dần)
        sorted_subjects = sorted(
            valid_subjects, 
            key=lambda s: len(s.registered_students), 
            reverse=True
        )
        
        # Log thông tin môn học
        for idx, subject in enumerate(sorted_subjects):
            self.logger.info(f"Subject {idx+1}: {subject.name} - {len(subject.registered_students)} students")
        
        # Sắp xếp phòng theo sức chứa (giảm dần)
        sorted_rooms = sorted(
            valid_rooms, 
            key=lambda r: r.capacity, 
            reverse=True
        )
        
        # Log thông tin phòng
        for idx, room in enumerate(sorted_rooms):
            self.logger.info(f"Room {idx+1}: {room.room_id} - Capacity: {room.capacity}")
        
        # Lấy danh sách giáo viên có thể giám sát từ database
        self.teachers = await self._get_teachers(db)
        self.logger.info(f"Found {len(self.teachers)} teachers for supervision")
        
        # Tính toán nhu cầu ca thi và phòng thi
        total_exam_sessions_needed = 0
        exam_requirements = []  # Lưu thông tin các phòng cần thiết cho từng môn học
        
        for subject in sorted_subjects:
            # Tính số phòng cần thiết cho môn học này
            num_students = len(subject.registered_students)
            
            if num_students == 0:
                continue
                
            # Tính toán số phòng thi cần thiết cho môn học này
            rooms_needed = []
            remaining_students = num_students
            
            for room in sorted_rooms:
                if remaining_students <= 0:
                    break
                rooms_needed.append(room)
                remaining_students -= room.capacity
            
            # Ghi nhận nhu cầu phòng thi cho môn học này
            exam_requirements.append({
                "subject": subject,
                "rooms_needed": rooms_needed,
                "num_students": num_students
            })
            
            # Tính tổng số phòng cần thiết cho tất cả các môn
            total_exam_sessions_needed += len(rooms_needed)
            
        self.logger.info(f"Total exam sessions needed: {total_exam_sessions_needed}")
        
        # Tính tổng số ngày có sẵn
        total_days = (self.config.end_date.date() - self.config.start_date.date()).days + 1
        self.logger.info(f"Total days available: {total_days}")
        
        # Tạo các khung thời gian đều đặn trên toàn bộ khoảng thời gian
        time_slots = self._generate_distributed_time_slots(sorted_subjects, total_exam_sessions_needed, total_days)
        self.logger.info(f"Generated {len(time_slots)} time slots distributed over {total_days} days")
        
        # Sắp xếp các time slot theo ngày và giờ
        sorted_time_slots = sorted(time_slots, key=lambda x: (x["start"].date(), x["start"].time()))
        
        # Danh sách để theo dõi các phòng đã được sử dụng trong từng time slot
        time_slot_room_usage = {}  # {time_slot_id: [room_ids]}
        for idx, slot in enumerate(sorted_time_slots):
            slot["id"] = idx  # Gán ID cho mỗi time slot để dễ tham chiếu
            time_slot_room_usage[idx] = []
            
        # Danh sách chứa tất cả các kỳ thi đã lập lịch
        scheduled_exams = []
        
        # Bước 1: Lập lịch cho môn học có nhiều phòng (nhiều sinh viên)
        multi_room_subjects = [req for req in exam_requirements if len(req["rooms_needed"]) > 1]
        multi_room_subjects.sort(key=lambda x: len(x["rooms_needed"]), reverse=True)
        
        for exam_req in multi_room_subjects:
            subject = exam_req["subject"]
            rooms_needed = exam_req["rooms_needed"]
            num_students = exam_req["num_students"]
            
            self.logger.info(f"Scheduling multi-room subject {subject.name} with {num_students} students, needs {len(rooms_needed)} rooms")
            
            # Tìm time slot phù hợp cho tất cả các phòng
            scheduled = False
            for time_slot in sorted_time_slots:
                slot_id = time_slot["id"]
                if time_slot.get("fully_assigned", False):
                    continue
                
                # Kiểm tra xem tất cả các phòng cần thiết có sẵn trong slot này không
                all_rooms_available = True
                for room in rooms_needed:
                    if room.id in time_slot_room_usage[slot_id]:
                        all_rooms_available = False
                        break
                
                if all_rooms_available:
                    self.logger.info(f"Found available slot: {time_slot['start']} for multi-room subject")
                    
                    # Lấy ID thực tế của sinh viên
                    student_ids = await self._get_student_ids(db, subject.registered_students)
                    
                    # Phân bổ sinh viên vào các phòng
                    student_distribution = self._distribute_students(student_ids, rooms_needed)
                    
                    # Lập lịch thi cho tất cả các phòng trong cùng time slot
                    for i, room in enumerate(rooms_needed):
                        if i < len(student_distribution) and student_distribution[i]:
                            end_time = time_slot["start"] + timedelta(minutes=subject.duration)
                            
                            exam = {
                                "subject_id": subject.id,
                                "room_id": room.id,
                                "start_time": time_slot["start"],
                                "end_time": end_time,
                                "supervisor_ids": [],  # Sẽ được phân bổ sau
                                "max_students": room.capacity,
                                "student_ids": student_distribution[i],
                            }
                            scheduled_exams.append(exam)
                            
                            # Đánh dấu phòng đã được sử dụng trong time slot này
                            time_slot_room_usage[slot_id].append(room.id)
                            
                    # Đánh dấu đã lên lịch cho môn học này
                    scheduled = True
                    break
            
            if not scheduled:
                self.logger.warning(f"Could not find available time slot for multi-room subject {subject.name}")
        
        # Bước 2: Lập lịch cho các môn học còn lại (một phòng)
        single_room_subjects = [req for req in exam_requirements if len(req["rooms_needed"]) == 1]
        
        for exam_req in single_room_subjects:
            subject = exam_req["subject"]
            rooms_needed = exam_req["rooms_needed"]
            num_students = exam_req["num_students"]
            
            if len(rooms_needed) == 0:
                continue
                
            room = rooms_needed[0]  # Chỉ cần một phòng
            
            self.logger.info(f"Scheduling single-room subject {subject.name} with {num_students} students")
            
            # Tìm time slot có phòng còn trống
            scheduled = False
            for time_slot in sorted_time_slots:
                slot_id = time_slot["id"]
                
                # Kiểm tra xem phòng có sẵn trong slot này không
                if room.id not in time_slot_room_usage[slot_id]:
                    self.logger.info(f"Found available slot: {time_slot['start']} for single-room subject")
                    
                    # Lấy ID thực tế của sinh viên
                    student_ids = await self._get_student_ids(db, subject.registered_students)
                    
                    # Lập lịch thi
                    end_time = time_slot["start"] + timedelta(minutes=subject.duration)
                    
                    exam = {
                        "subject_id": subject.id,
                        "room_id": room.id,
                        "start_time": time_slot["start"],
                        "end_time": end_time,
                        "supervisor_ids": [],  # Sẽ được phân bổ sau
                        "max_students": room.capacity,
                        "student_ids": student_ids[:room.capacity],
                    }
                    scheduled_exams.append(exam)
                    
                    # Đánh dấu phòng đã được sử dụng trong time slot này
                    time_slot_room_usage[slot_id].append(room.id)
                    
                    # Đánh dấu đã lên lịch cho môn học này
                    scheduled = True
                    break
            
            if not scheduled:
                self.logger.warning(f"Could not find available time slot for single-room subject {subject.name}")
        
        # Phân bổ giám thị
        scheduled_exams = await self._assign_supervisors(db, scheduled_exams)
        
        self.logger.info(f"Scheduled {len(scheduled_exams)} exams total")
        return scheduled_exams
    
    def _check_multiple_rooms_availability(self, time_slot, rooms_needed, scheduled_exams):
        """
        Kiểm tra xem tất cả các phòng cần thiết có sẵn trong khung thời gian không
        """
        for room in rooms_needed:
            for exam in scheduled_exams:
                if exam["room_id"] == room.id:
                    # Kiểm tra xung đột thời gian
                    if (time_slot["start"] < exam["end_time"] and 
                        time_slot["end"] > exam["start_time"]):
                        return False  # Chỉ cần một phòng không khả dụng là không thể sử dụng slot này
        
        return True  # Tất cả phòng đều khả dụng
                
    async def _get_student_ids(self, db, student_codes):
        """
        Chuyển đổi mã sinh viên sang ID thực tế trong database
        """
        student_ids = []
        for code in student_codes:
            student = await db.students.find_one({"student_id": code})
            if student:
                student_ids.append(student.get("student_id"))
            else:
                # Trường hợp không tìm thấy, giữ nguyên mã
                student_ids.append(code)
        return student_ids

    async def _get_teachers(self, db):
        """
        Lấy danh sách giáo viên từ database
        """
        teachers = []
        teachers_cursor = db.teachers.find()
        
        async for teacher in teachers_cursor:
            # Chuyển đổi ObjectId thành string
            if "teacher_id" in teacher:
                teachers.append({
                    "id": teacher.get("_id"),
                    "teacher_id": teacher.get("teacher_id"),
                    "full_name": teacher.get("full_name")
                })
                # Khởi tạo số lần phân công là 0
                self.teacher_assignments[teacher.get("_id")] = 0
                
        if not teachers:
            # Tạo giáo viên demo nếu không có giáo viên nào
            for i in range(1, 11):
                teacher_id = f"DEMO_TEACHER_{i}"
                teachers.append({
                    "id": teacher_id,
                    "teacher_id": teacher_id,
                    "full_name": f"Giáo viên Demo {i}"
                })
                self.teacher_assignments[teacher_id] = 0
                
        return teachers
    
    def _generate_time_slots(self, subjects):
        """
        Tạo các khung thời gian cho kỳ thi dựa trên cấu hình và thời lượng môn học
        """
        time_slots = []
        current_date = self.config.start_date
        
        # Đảm bảo first_exam_time và last_exam_time là đối tượng time
        first_exam_time = self.config.first_exam_time
        last_exam_time = self.config.last_exam_time
        
        # Kiểm tra nếu first_exam_time là chuỗi, chuyển đổi thành đối tượng time
        if isinstance(first_exam_time, str):
            h, m, s = map(int, first_exam_time.split(':'))
            first_exam_time = time(h, m, s)
            
        # Kiểm tra nếu last_exam_time là chuỗi, chuyển đổi thành đối tượng time
        if isinstance(last_exam_time, str):
            h, m, s = map(int, last_exam_time.split(':'))
            last_exam_time = time(h, m, s)
        
        # Đảm bảo start_date và end_date có cùng một ngày nếu chúng giống nhau
        if self.config.start_date.date() == self.config.end_date.date():
            self.logger.info("Start date and end date are the same")
            
        # Tính toán thời gian trung bình mỗi ca thi
        avg_duration = 120  # Mặc định là 120 phút (2 giờ)
        
        # Tính thời lượng trung bình nếu có môn học
        if subjects:
            duration_sum = sum(subject.duration for subject in subjects)
            avg_duration = max(duration_sum // len(subjects), 60)  # Tối thiểu 60 phút
            self.logger.info(f"Average exam duration: {avg_duration} minutes")
        
        # Thời gian nghỉ giữa các ca thi
        break_duration = 30  # 30 phút nghỉ giữa các ca
            
        while current_date.date() <= self.config.end_date.date():
            # Thời gian bắt đầu và kết thúc của ngày
            try:
                day_start = datetime.combine(current_date.date(), first_exam_time)
                day_end = datetime.combine(current_date.date(), last_exam_time)
                
                self.logger.debug(f"Day time range: {day_start} - {day_end}")
                
                # Tạo các khung thời gian trong ngày
                current_time = day_start
                while current_time < day_end:
                    # Tính toán thời gian kết thúc dựa trên thời lượng trung bình
                    slot_end = current_time + timedelta(minutes=avg_duration)
                    
                    # Đảm bảo không vượt quá thời gian kết thúc trong ngày
                    if slot_end <= day_end:
                        time_slots.append({
                            "start": current_time,
                            "end": slot_end,
                            "duration": avg_duration
                        })
                        self.logger.debug(f"Created time slot: {current_time} - {slot_end}")
                    
                    # Chuyển đến thời điểm bắt đầu ca tiếp theo (sau thời gian nghỉ)
                    current_time = slot_end + timedelta(minutes=break_duration)
                
                # Chuyển sang ngày tiếp theo
                current_date += timedelta(days=1)
            except Exception as e:
                self.logger.error(f"Error generating time slot: {str(e)}")
                # Chuyển sang ngày tiếp theo nếu có lỗi
                current_date += timedelta(days=1)
        
        self.logger.info(f"Generated {len(time_slots)} time slots")
        if not time_slots:
            self.logger.warning(f"No time slots were generated! Check your configuration: first_exam_time={self.config.first_exam_time}, last_exam_time={self.config.last_exam_time}")
            # Tạo ít nhất một khung thời gian mặc định nếu không có khung thời gian nào được tạo
            tomorrow = datetime.now() + timedelta(days=1)
            default_start = datetime.combine(tomorrow.date(), time(8, 0))
            default_end = default_start + timedelta(hours=2)
            time_slots.append({
                "start": default_start,
                "end": default_end,
            })
        
        return time_slots
    
    def _generate_distributed_time_slots(self, subjects, total_sessions_needed, total_days):
        """
        Tạo các khung thời gian phân bố đều trên toàn bộ khoảng thời gian
        """
        time_slots = []
        
        # Tính số lượng ca thi cần mỗi ngày (làm tròn lên)
        exams_per_day = math.ceil(total_sessions_needed / total_days)
        self.logger.info(f"Target exams per day: {exams_per_day}")
        
        # Tính thời lượng trung bình của một ca thi
        avg_duration = 120  # Mặc định là 120 phút
        if subjects:
            duration_sum = sum(subject.duration for subject in subjects)
            avg_duration = max(duration_sum // len(subjects), 60)  # Tối thiểu 60 phút
        
        # Thời gian nghỉ giữa các ca thi
        break_duration = 30  # 30 phút nghỉ
        
        # Đảm bảo first_exam_time và last_exam_time là đối tượng time
        first_exam_time = self.config.first_exam_time
        last_exam_time = self.config.last_exam_time
        
        if isinstance(first_exam_time, str):
            h, m, s = map(int, first_exam_time.split(':'))
            first_exam_time = time(h, m, s)
            
        if isinstance(last_exam_time, str):
            h, m, s = map(int, last_exam_time.split(':'))
            last_exam_time = time(h, m, s)
        
        # Tính toán số slot có thể có mỗi ngày
        day_start = datetime.combine(self.config.start_date.date(), first_exam_time)
        day_end = datetime.combine(self.config.start_date.date(), last_exam_time)
        day_minutes = (day_end - day_start).seconds // 60
        
        # Tính số lượng slot tối đa mỗi ngày
        max_slots_per_day = (day_minutes - (avg_duration - break_duration)) // (avg_duration + break_duration)
        max_slots_per_day = max(1, max_slots_per_day)  # Ít nhất 1 slot mỗi ngày
        
        self.logger.info(f"Max slots per day: {max_slots_per_day} (day minutes: {day_minutes}, avg duration: {avg_duration})")
        
        # Điều chỉnh số ca thi mỗi ngày để không vượt quá giới hạn
        exams_per_day = min(exams_per_day, max_slots_per_day)
        
        # Với mỗi ngày từ start_date đến end_date
        current_date = self.config.start_date
        days_with_slots = 0
        
        while current_date.date() <= self.config.end_date.date():
            # Số slot cần tạo cho ngày này
            if days_with_slots * exams_per_day >= total_sessions_needed:
                # Đã đủ số slot cần thiết
                break
                
            try:
                # Tính toán khoảng cách thời gian giữa các ca thi để phân bố đều trong ngày
                day_start = datetime.combine(current_date.date(), first_exam_time)
                day_end = datetime.combine(current_date.date(), last_exam_time)
                
                # Nếu số ca thi mỗi ngày > 1, phân bố đều trong ngày
                if exams_per_day > 1:
                    # Tính khoảng thời gian giữa các ca thi
                    total_minutes = (day_end - day_start).seconds // 60
                    # Trừ đi thời gian của ca thi đầu tiên
                    available_minutes = total_minutes - avg_duration
                    # Tính khoảng cách giữa các ca thi
                    slot_spacing = available_minutes // (exams_per_day - 1)
                else:
                    # Nếu chỉ có 1 ca thi mỗi ngày, đặt vào giữa ngày
                    slot_spacing = 0
                    day_start = day_start + timedelta(minutes=(day_end - day_start).seconds // 60 // 2 - avg_duration // 2)
                
                # Tạo các slot thời gian cho ngày này
                for i in range(exams_per_day):
                    if len(time_slots) >= total_sessions_needed:
                        break
                        
                    slot_start = day_start + timedelta(minutes=i * slot_spacing) if i > 0 else day_start
                    slot_end = slot_start + timedelta(minutes=avg_duration)
                    
                    # Đảm bảo slot không vượt quá thời gian kết thúc trong ngày
                    if slot_end <= day_end:
                        time_slots.append({
                            "start": slot_start,
                            "end": slot_end,
                            "duration": avg_duration,
                            "assigned": False
                        })
                
                days_with_slots += 1
                
            except Exception as e:
                self.logger.error(f"Error generating time slots for {current_date.date()}: {str(e)}")
            
            # Chuyển sang ngày tiếp theo
            current_date += timedelta(days=1)
        
        # Nếu vẫn chưa đủ slot, thêm slot vào những ngày đã có (trường hợp hiếm)
        if len(time_slots) < total_sessions_needed:
            self.logger.warning(f"Not enough slots generated ({len(time_slots)}/{total_sessions_needed}). Adding more slots.")
            
            # Quay lại từ đầu và thêm các slot vào buổi chiều
            current_date = self.config.start_date
            afternoon_start = time(13, 0)
            
            while len(time_slots) < total_sessions_needed and current_date.date() <= self.config.end_date.date():
                try:
                    slot_start = datetime.combine(current_date.date(), afternoon_start)
                    slot_end = slot_start + timedelta(minutes=avg_duration)
                    
                    # Đảm bảo slot không vượt quá thời gian kết thúc trong ngày
                    day_end = datetime.combine(current_date.date(), last_exam_time)
                    if slot_end <= day_end:
                        time_slots.append({
                            "start": slot_start,
                            "end": slot_end,
                            "duration": avg_duration,
                            "assigned": False
                        })
                except Exception as e:
                    self.logger.error(f"Error generating additional time slot for {current_date.date()}: {str(e)}")
                
                # Chuyển sang ngày tiếp theo
                current_date += timedelta(days=1)
        
        self.logger.info(f"Generated {len(time_slots)} time slots over {days_with_slots} days")
        return time_slots
    
    def _check_rooms_availability(self, time_slot, rooms, scheduled_exams):
        """
        Kiểm tra xem các phòng có sẵn trong khung thời gian không
        """
        for room in rooms:
            for exam in scheduled_exams:
                if exam["room_id"] == room.id:
                    # Kiểm tra xem có xung đột thời gian không
                    if (time_slot["start"] < exam["end_time"] and 
                        time_slot["end"] > exam["start_time"]):
                        return False
        
        return True
    
    def _distribute_students(self, student_ids, rooms):
        """
        Phân bổ sinh viên vào các phòng
        """
        distribution = []
        remaining_students = student_ids.copy()
        
        for room in rooms:
            room_capacity = room.capacity
            room_students = remaining_students[:room_capacity]
            distribution.append(room_students)
            remaining_students = remaining_students[room_capacity:]
            
            if not remaining_students:
                break
        
        return distribution
    
    async def _assign_supervisors(self, db, scheduled_exams):
        """
        Phân bổ giám thị cho các phòng thi đảm bảo cân bằng giữa các giáo viên
        """
        if not self.teachers:
            # Nếu không có giáo viên, sử dụng giám thị ảo
            for exam in scheduled_exams:
                exam["supervisor_ids"] = [f"DEMO_SUPERVISOR_{i}" for i in range(self.config.supervisors_per_room)]
            return scheduled_exams
            
        # Nhóm các kỳ thi theo thời gian (để cùng giáo viên không bị phân công vào 2 phòng cùng lúc)
        exams_by_time = {}
        for exam in scheduled_exams:
            time_key = f"{exam['start_time'].isoformat()}_{exam['end_time'].isoformat()}"
            if time_key not in exams_by_time:
                exams_by_time[time_key] = []
            exams_by_time[time_key].append(exam)
        
        # Đối với mỗi khung thời gian
        for time_key, exams in exams_by_time.items():
            # Tạo danh sách giáo viên có thể phân công cho khung thời gian này
            available_teachers = self.teachers.copy()
            
            # Phân bổ giáo viên cho từng phòng thi trong khung thời gian
            for exam in exams:
                supervisors_needed = self.config.supervisors_per_room
                
                # Nếu không đủ giáo viên, giảm số lượng giám thị/phòng xuống 1
                if len(available_teachers) < len(exams) * supervisors_needed:
                    supervisors_needed = 1
                
                exam_supervisors = []
                
                # Chọn giáo viên có số lần phân công ít nhất
                for _ in range(supervisors_needed):
                    if not available_teachers:
                        # Nếu hết giáo viên, sử dụng giám thị ảo
                        exam_supervisors.append(f"DEMO_SUPERVISOR_{_}")
                    else:
                        # Sắp xếp giáo viên theo số lần phân công (tăng dần)
                        available_teachers.sort(key=lambda t: self.teacher_assignments[t["id"]])
                        selected_teacher = available_teachers.pop(0)
                        
                        # Đảm bảo teacher ID luôn là string
                        teacher_id = selected_teacher["id"]
                        if isinstance(teacher_id, ObjectId):
                            teacher_id = str(teacher_id)
                        
                        exam_supervisors.append(teacher_id)
                        
                        # Tăng số lần phân công cho giáo viên được chọn
                        self.teacher_assignments[selected_teacher["id"]] += 1
                
                exam["supervisor_ids"] = exam_supervisors
        
        # Log số lần phân công của mỗi giáo viên
        self.logger.info("Teacher assignment distribution:")
        for teacher_id, count in self.teacher_assignments.items():
            if count > 0:  # Chỉ hiển thị giáo viên đã được phân công
                teacher_name = next((t["full_name"] for t in self.teachers if t["id"] == teacher_id), teacher_id)
                self.logger.info(f"  {teacher_name}: {count} assignments")
        
        # Đảm bảo tất cả exam đều có supervisor_ids
        for exam in scheduled_exams:
            if "supervisor_ids" not in exam or not exam["supervisor_ids"]:
                exam["supervisor_ids"] = [f"DEMO_SUPERVISOR_{i}" for i in range(self.config.supervisors_per_room)]
        
        return scheduled_exams
