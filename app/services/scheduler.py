from datetime import datetime, timedelta, time
from typing import List, Dict, Any, Optional, Set, Tuple
import logging
import random
import math
from bson.objectid import ObjectId
from collections import defaultdict

from app.models.domain.subject import Subject
from app.models.domain.room import Room
from app.models.domain.schedule import ScheduleConfig

class ExamScheduler:
    def __init__(self, config: ScheduleConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.teacher_assignments = {}  # Để theo dõi số lần phân công cho mỗi giáo viên
        self.teachers = []
        # Thêm biến theo dõi các room_id đã được phân cùng một lúc
        self.parallel_rooms_weight = {}
        # Track student conflicts
        self.student_exam_dates = defaultdict(list)
        
    async def schedule_exams(self, db, subjects: List[Subject], rooms: List[Room]):
        """
        Lập lịch thi cho các môn học và phòng thi dựa trên cấu hình
        """
        self.logger.info(f"Starting exam scheduling for period: {self.config.start_date} to {self.config.end_date}")
        self.logger.info(f"Found {len(subjects)} subjects and {len(rooms)} rooms")
        
        # Kiểm tra dữ liệu đầu vào
        if not subjects:
            self.logger.warning("No subjects provided for scheduling")
            return []
            
        if not rooms:
            self.logger.warning("No rooms provided for scheduling")
            return []
        
        # Lọc môn học có sinh viên đăng ký
        valid_subjects = [s for s in subjects if s.registered_students]
        if not valid_subjects:
            self.logger.warning("No subjects with registered students")
            return []
            
        # Lọc phòng có sức chứa
        valid_rooms = [r for r in rooms if r.capacity > 0]
        if not valid_rooms:
            self.logger.warning("No rooms with capacity > 0")
            return []
        
        # Sắp xếp môn học theo số sinh viên đăng ký (giảm dần)
        # và nếu số sinh viên bằng nhau, sắp xếp theo thời lượng thi (giảm dần)
        sorted_subjects = sorted(
            valid_subjects, 
            key=lambda s: (len(s.registered_students), s.duration), 
            reverse=True
        )
        
        # Log thông tin môn học
        for idx, subject in enumerate(sorted_subjects):
            self.logger.info(f"Subject {idx+1}: {subject.name} - {len(subject.registered_students)} students, {subject.duration} minutes")
        
        # Sắp xếp phòng theo sức chứa (giảm dần)
        sorted_rooms = sorted(
            valid_rooms, 
            key=lambda r: r.capacity, 
            reverse=True
        )
        
        # Xây dựng hệ số tương thích giữa các phòng thi (gần nhau sẽ có hệ số cao hơn)
        self._build_room_compatibility_weights(sorted_rooms)
        
        # Lấy danh sách giáo viên có thể giám sát từ database
        self.teachers = await self._get_teachers(db)
        self.logger.info(f"Found {len(self.teachers)} teachers for supervision")
        
        # Tính toán nhu cầu ca thi và phòng thi
        exam_requirements = self._calculate_exam_requirements(sorted_subjects, sorted_rooms)
        total_exam_sessions_needed = sum(len(req["rooms_needed"]) for req in exam_requirements)
        self.logger.info(f"Total exam sessions needed: {total_exam_sessions_needed}")
        
        # Tính tổng số ngày có sẵn
        total_days = (self.config.end_date.date() - self.config.start_date.date()).days + 1
        self.logger.info(f"Total days available: {total_days}")
        
        # Tạo các khung thời gian đều đặn trên toàn bộ khoảng thời gian
        time_slots = self._generate_optimized_time_slots(sorted_subjects, total_exam_sessions_needed, total_days)
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
        
        # Lập lịch cho từng môn học theo thứ tự ưu tiên
        self._schedule_exams_with_priorities(exam_requirements, sorted_time_slots, time_slot_room_usage, scheduled_exams, db)
        
        # Phân bổ giám thị - cố gắng đảm bảo giám thị không phải di chuyển giữa các phòng xa nhau
        scheduled_exams = await self._assign_supervisors_optimized(db, scheduled_exams)
        
        self.logger.info(f"Scheduled {len(scheduled_exams)} exams total")
        return scheduled_exams
        
    def _calculate_exam_requirements(self, subjects: List[Subject], rooms: List[Room]) -> List[Dict]:
        """
        Tính toán các yêu cầu phòng thi cho từng môn học
        """
        exam_requirements = []
        
        for subject in subjects:
            num_students = len(subject.registered_students)
            
            # Tìm số lượng phòng cần thiết cho môn học này
            rooms_needed = []
            remaining_students = num_students
            
            for room in rooms:
                if remaining_students <= 0:
                    break
                    
                rooms_needed.append(room)
                remaining_students -= room.capacity
            
            # Thêm vào danh sách yêu cầu kỳ thi
            exam_requirements.append({
                "subject": subject,
                "num_students": num_students,
                "rooms_needed": rooms_needed,
                "priority_score": self._calculate_priority_score(subject, num_students)
            })
            
            self.logger.info(f"Subject {subject.name}: {num_students} students, needs {len(rooms_needed)} rooms")
            
        return exam_requirements
    
    def _calculate_priority_score(self, subject: Subject, num_students: int) -> float:
        """
        Tính điểm ưu tiên cho môn học dựa trên số lượng sinh viên và thời lượng thi
        """
        # Môn học có nhiều sinh viên và thời lượng dài sẽ được ưu tiên lập lịch trước
        return num_students * (1 + (subject.duration / 60))
    
    def _schedule_exams_with_priorities(self, exam_requirements, sorted_time_slots, time_slot_room_usage, scheduled_exams, db):
        """
        Lập lịch thi với chiến lược ưu tiên và lưu ý đến xung đột lịch thi của sinh viên
        """
        # Sắp xếp các yêu cầu theo điểm ưu tiên giảm dần
        sorted_requirements = sorted(
            exam_requirements,
            key=lambda req: (
                req["priority_score"],               # Ưu tiên môn có điểm ưu tiên cao
                len(req["rooms_needed"]),           # Ưu tiên môn cần nhiều phòng
                req["subject"].duration              # Ưu tiên môn có thời lượng dài
            ),
            reverse=True
        )
        
        # Xử lý từng yêu cầu thi theo thứ tự ưu tiên
        for exam_req in sorted_requirements:
            subject = exam_req["subject"]
            rooms_needed = exam_req["rooms_needed"]
            num_students = exam_req["num_students"]
            
            self.logger.info(f"Scheduling subject {subject.name} (priority: {exam_req['priority_score']:.2f}) with {num_students} students, needs {len(rooms_needed)} rooms")
            
            # Tìm time slot phù hợp
            best_slot = self._find_best_time_slot(subject, rooms_needed, sorted_time_slots, time_slot_room_usage)
            
            if best_slot:
                self._schedule_in_time_slot(subject, rooms_needed, best_slot, time_slot_room_usage, scheduled_exams, db)
            else:
                self.logger.warning(f"Could not find suitable time slot for subject {subject.name}")
    
    def _find_best_time_slot(self, subject, rooms_needed, time_slots, time_slot_room_usage):
        """
        Tìm time slot tốt nhất cho một môn học, với xem xét đến:
        - Khả năng có đủ phòng trống
        - Khoảng cách với các kỳ thi khác của cùng sinh viên
        - Sự tương thích về vị trí của các phòng
        """
        # Lấy danh sách sinh viên của môn học
        students = subject.registered_students
        
        # Đánh giá từng time slot
        slot_scores = []
        
        for time_slot in time_slots:
            slot_id = time_slot.get("id")
            if time_slot.get("fully_assigned", False):
                continue
            
            # Kiểm tra đủ phòng không
            all_rooms_available = True
            for room in rooms_needed:
                if room.id in time_slot_room_usage.get(slot_id, []):
                    all_rooms_available = False
                    break
            
            if not all_rooms_available:
                continue
            
            # Tính điểm xung đột sinh viên - càng ít sinh viên có lịch thi gần đây càng tốt
            student_conflict_score = self._calculate_student_conflict_score(students, time_slot["start"])
            
            # Tính điểm tương thích phòng
            room_compatibility_score = self._calculate_room_compatibility_score(rooms_needed)
            
            # Tính điểm phân bố thời gian - ưu tiên các slot ở giữa khoảng thời gian có sẵn
            time_distribution_score = self._calculate_time_distribution_score(time_slot["start"])
            
            # Tổng hợp điểm đánh giá
            total_score = (
                student_conflict_score * 0.5 +
                room_compatibility_score * 0.3 +
                time_distribution_score * 0.2
            )
            
            slot_scores.append({
                "slot": time_slot,
                "score": total_score
            })
        
        # Sắp xếp theo điểm giảm dần và lấy slot tốt nhất
        if slot_scores:
            slot_scores.sort(key=lambda x: x["score"], reverse=True)
            return slot_scores[0]["slot"]
        
        return None
    
    def _schedule_in_time_slot(self, subject, rooms_needed, time_slot, time_slot_room_usage, scheduled_exams, db):
        """
        Lập lịch thi cho một môn học trong một time slot đã chọn
        """
        slot_id = time_slot["id"]
        
        # Lấy ID thực tế của sinh viên - async function nên cần await
        student_ids = self._get_student_ids_sync(subject.registered_students)
        
        # Phân bổ sinh viên vào các phòng
        student_distribution = self._distribute_students_optimized(student_ids, rooms_needed)
        
        # Lập lịch thi cho tất cả các phòng trong cùng time slot
        parallel_group_id = f"{subject.id}_{slot_id}_{datetime.now().timestamp()}"
        
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
                    "parallel_exam_group": parallel_group_id  # Đánh dấu các phòng thi cùng môn song song
                }
                scheduled_exams.append(exam)
                
                # Đánh dấu phòng đã được sử dụng trong time slot này
                time_slot_room_usage[slot_id].append(room.id)
                
                # Cập nhật lịch thi của sinh viên - để tránh xung đột
                exam_date = time_slot["start"].date()
                for student_id in student_distribution[i]:
                    self.student_exam_dates[student_id].append({
                        "date": exam_date,
                        "start_time": time_slot["start"],
                        "end_time": end_time,
                        "subject": subject.name
                    })
                
        self.logger.info(f"Scheduled {subject.name} with {len(student_ids)} students in {len(rooms_needed)} rooms at {time_slot['start']}")
    
    def _calculate_student_conflict_score(self, students, exam_time):
        """
        Tính điểm xung đột lịch thi của sinh viên
        Điểm cao = ít xung đột
        """
        if not students:
            return 1.0  # Không có sinh viên = không xung đột
        
        conflicts = 0
        exam_date = exam_time.date()
        
        for student in students:
            # Kiểm tra sinh viên có lịch thi vào cùng ngày không
            student_exams = self.student_exam_dates.get(student, [])
            for student_exam in student_exams:
                if student_exam["date"] == exam_date:
                    conflicts += 1
                    break
                
                # Hoặc ngày liền kề (để tránh lịch thi dồn dập)
                elif abs((student_exam["date"] - exam_date).days) == 1:
                    conflicts += 0.5
                    break
        
        # Tính điểm từ 0-1, 1 = không xung đột
        if len(students) == 0:
            return 1.0
        
        conflict_ratio = conflicts / len(students)
        return 1.0 - conflict_ratio
    
    def _calculate_room_compatibility_score(self, rooms):
        """
        Tính điểm tương thích giữa các phòng thi
        """
        if len(rooms) <= 1:
            return 1.0  # Chỉ một phòng luôn có điểm cao nhất
        
        # Tính điểm tương thích trung bình giữa tất cả các cặp phòng
        compatibility_score = 0
        room_count = len(rooms)
        
        for i in range(room_count):
            for j in range(i+1, room_count):
                room1_id = rooms[i].id
                room2_id = rooms[j].id
                weight = self.parallel_rooms_weight.get((room1_id, room2_id), 0.5)
                compatibility_score += weight
        
        # Điểm trung bình (0-1)
        combinations = room_count * (room_count - 1) / 2
        if combinations > 0:
            return compatibility_score / combinations
        return 1.0
    
    def _calculate_time_distribution_score(self, exam_time):
        """
        Tính điểm phân bố thời gian - ưu tiên các slot ở giữa khoảng thời gian
        """
        # Tính tổng thời gian có sẵn
        total_period = (self.config.end_date - self.config.start_date).total_seconds()
        
        # Tính thời gian từ ngày bắt đầu đến exam_time
        time_from_start = (exam_time - self.config.start_date).total_seconds()
        
        # Tính tỉ lệ (0-1) - thời gian vị trí của slot trong tổng thời gian
        if total_period == 0:
            return 1.0
            
        ratio = time_from_start / total_period
        
        # Điểm cao nhất ở giữa khoảng thời gian (ratio = 0.5)
        # Sử dụng công thức hàm parabol ngược: 1 - 4 * (x - 0.5)²
        return 1.0 - 4.0 * (ratio - 0.5) * (ratio - 0.5)
    
    def _build_room_compatibility_weights(self, rooms: List[Room]):
        """
        Xây dựng ma trận trọng số tương thích giữa các phòng thi
        Phòng càng gần nhau (theo ID) thì trọng số càng cao
        """
        self.parallel_rooms_weight = {}
        
        # Giả định: Phòng có ID gần nhau thì vị trí vật lý cũng gần nhau
        for i, room1 in enumerate(rooms):
            for j, room2 in enumerate(rooms):
                if i == j:
                    # Phòng với chính nó có trọng số cao nhất
                    self.parallel_rooms_weight[(room1.id, room2.id)] = 1.0
                else:
                    # Tính toán trọng số dựa trên sự khác biệt trong ID phòng
                    # Giả sử phòng có định dạng ký tự + số (ví dụ: A101, B202)
                    room1_id = room1.room_id
                    room2_id = room2.room_id
                    
                    # Kiểm tra xem hai phòng có cùng tòa nhà không (phần ký tự đầu)
                    same_building = False
                    try:
                        r1_building = ''.join([c for c in room1_id if not c.isdigit()])
                        r2_building = ''.join([c for c in room2_id if not c.isdigit()])
                        same_building = r1_building == r2_building
                    except:
                        pass
                    
                    # Phòng cùng tòa nhà được ưu tiên cao hơn
                    if same_building:
                        # Tính khoảng cách phòng dựa trên số thứ tự
                        try:
                            r1_number = int(''.join([c for c in room1_id if c.isdigit()]) or '0')
                            r2_number = int(''.join([c for c in room2_id if c.isdigit()]) or '0')
                            # Phòng càng gần nhau thì trọng số càng cao (0.5-1.0)
                            diff = abs(r1_number - r2_number)
                            weight = max(0.5, 1.0 - (diff / 100))
                        except:
                            # Không thể phân tích số, mặc định trọng số trung bình
                            weight = 0.7
                    else:
                        # Phòng khác tòa có trọng số thấp hơn (0.1-0.4)
                        weight = 0.3
                    
                    self.parallel_rooms_weight[(room1.id, room2.id)] = weight
                    
        self.logger.info(f"Built room compatibility weights for {len(rooms)} rooms")
    
    def _distribute_students_optimized(self, student_ids, rooms):
        """
        Phân bổ sinh viên vào các phòng với chiến lược tối ưu
        """
        if not student_ids:
            return [[] for _ in rooms]
            
        distribution = []
        remaining_students = student_ids.copy()
        
        # Sắp xếp phòng theo sức chứa giảm dần - ưu tiên điền đầy phòng lớn trước
        sorted_rooms = sorted(rooms, key=lambda r: r.capacity, reverse=True)
        
        for room in sorted_rooms:
            room_capacity = room.capacity
            room_students = remaining_students[:room_capacity]
            distribution.append(room_students)
            remaining_students = remaining_students[room_capacity:]
            
            if not remaining_students:
                # Không còn sinh viên cần phân bổ
                # Điền danh sách rỗng cho các phòng còn lại
                while len(distribution) < len(rooms):
                    distribution.append([])
                break
        
        # Nếu số phòng trong distribution ít hơn số phòng cần, thêm các danh sách rỗng
        while len(distribution) < len(rooms):
            distribution.append([])
            
        # Remap lại thứ tự các phòng về thứ tự ban đầu
        result = [[] for _ in range(len(rooms))]
        room_ids_original = [r.id for r in rooms]
        room_ids_sorted = [r.id for r in sorted_rooms]
        
        for i, room_id in enumerate(room_ids_original):
            if room_id in room_ids_sorted:
                idx = room_ids_sorted.index(room_id)
                if idx < len(distribution):
                    result[i] = distribution[idx]
        
        return result

    def _generate_optimized_time_slots(self, subjects, total_sessions_needed, total_days):
        """
        Tạo các khung thời gian phân bố đều trên toàn bộ khoảng thời gian
        với tối ưu hóa dựa trên thời lượng trung bình của môn học
        """
        time_slots = []
        
        # Tính số lượng ca thi cần mỗi ngày (làm tròn lên)
        exams_per_day = math.ceil(total_sessions_needed / total_days)
        self.logger.info(f"Target exams per day: {exams_per_day}")
        
        # Tính thời lượng trung bình của một ca thi
        avg_duration = 120  # Mặc định là 120 phút
        if subjects:
            total_duration = sum(subject.duration for subject in subjects)
            avg_duration = total_duration // len(subjects)
        
        # Thời gian nghỉ giữa các ca thi (tối thiểu 30 phút)
        break_duration = max(30, avg_duration // 6)  # Nghỉ bằng khoảng 1/6 thời gian thi
        
        # Đảm bảo first_exam_time và last_exam_time là đối tượng time
        first_exam_time = self.config.first_exam_time
        last_exam_time = self.config.last_exam_time
        
        if isinstance(first_exam_time, str):
            parts = first_exam_time.split(':')
            first_exam_time = time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
            
        if isinstance(last_exam_time, str):
            parts = last_exam_time.split(':')
            last_exam_time = time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
        
        # Tính toán số slot tối đa mỗi ngày
        test_date = self.config.start_date.date()
        day_start = datetime.combine(test_date, first_exam_time)
        day_end = datetime.combine(test_date, last_exam_time)
        day_minutes = (day_end - day_start).total_seconds() // 60
        
        # Tối đa slots có thể có trong một ngày
        max_slots_per_day = max(1, int((day_minutes - avg_duration) / (avg_duration + break_duration)) + 1)
        slots_per_day = min(exams_per_day, max_slots_per_day)
        
        # Tạo phân bố đều các time slots
        current_date = self.config.start_date.date()
        end_date = self.config.end_date.date()
        
        while current_date <= end_date:
            # Tính toán các thời điểm bắt đầu phân bố đều trong ngày
            day_start = datetime.combine(current_date, first_exam_time)
            day_end = datetime.combine(current_date, last_exam_time)
            
            if slots_per_day == 1:
                # Nếu chỉ có 1 slot, đặt giữa ngày
                mid_point = day_start + (day_end - day_start) // 2
                time_slots.append({"start": mid_point})
            else:
                # Phân bố đều các slots
                available_minutes = (day_end - day_start).total_seconds() // 60
                segment_minutes = available_minutes / (slots_per_day - 0.999)  # Điều chỉnh để tránh slot cuối cùng quá sát với day_end
                
                for i in range(slots_per_day):
                    slot_start = day_start + timedelta(minutes=i * segment_minutes)
                    # Đảm bảo slot cuối không vượt quá thời gian cuối ngày
                    if slot_start + timedelta(minutes=avg_duration) <= day_end:
                        time_slots.append({"start": slot_start})
                    else:
                        break
                        
            current_date += timedelta(days=1)
        
        self.logger.info(f"Generated {len(time_slots)} optimized time slots with {slots_per_day} slots per day")
        return time_slots
    
    def _get_student_ids_sync(self, student_codes):
        """
        Chuyển đổi mã sinh viên sang ID cho phiên bản sync (non-async)
        """
        # Giả lập việc lấy student IDs
        return student_codes
        
    async def _get_teachers(self, db):
        """
        Lấy danh sách giáo viên từ database
        """
        teachers = []
        teachers_cursor = db.teachers.find()
        
        async for teacher in teachers_cursor:
            if isinstance(teacher.get("_id"), ObjectId):
                teacher["_id"] = str(teacher["_id"])
            
            if "id" not in teacher:
                teacher["id"] = teacher["_id"]
                
            teachers.append(teacher)
                
        if not teachers:
            self.logger.warning("No teachers found in database, using demo supervisors")
            # Tạo giáo viên demo nếu không có giáo viên thật
            for i in range(10):
                teachers.append({
                    "id": f"DEMO_SUPERVISOR_{i+1}",
                    "full_name": f"Giám thị Demo {i+1}"
                })
                
        return teachers
    
    async def _assign_supervisors_optimized(self, db, scheduled_exams):
        """
        Phân bổ giám thị cho các phòng thi với tối ưu hóa nhiều phòng song song
        """
        if not self.teachers:
            # Nếu không có giáo viên, sử dụng giám thị ảo
            for exam in scheduled_exams:
                exam["supervisor_ids"] = [f"DEMO_SUPERVISOR_{i+1}" for i in range(self.config.supervisors_per_room)]
            return scheduled_exams
            
        # Nhóm các kỳ thi theo thời gian và nhóm song song
        exams_by_time_and_group = {}
        for exam in scheduled_exams:
            time_key = f"{exam['start_time'].isoformat()}_{exam['end_time'].isoformat()}"
            group_key = exam.get('parallel_exam_group', 'default_group')
            combined_key = f"{time_key}_{group_key}"
            
            if combined_key not in exams_by_time_and_group:
                exams_by_time_and_group[combined_key] = []
            exams_by_time_and_group[combined_key].append(exam)
        
        # Mỗi giáo viên tại một thời điểm chỉ có thể coi thi tại một phòng
        teacher_assignments_by_time = {}  # {time_key: [teacher_ids]}
        
        # Phân công giám thị
        for combined_key, exams in exams_by_time_and_group.items():
            time_key = combined_key.rsplit('_', 1)[0]  # Lấy phần thời gian từ combined_key
            
            # Tạo danh sách giáo viên có thể phân công cho thời gian này
            available_teachers = [t for t in self.teachers if t["id"] not in teacher_assignments_by_time.get(time_key, [])]
            
            # Nhóm các phòng thi gần nhau
            room_groups = self._group_nearby_rooms(exams)
            
            # Phân bổ giáo viên cho từng nhóm phòng gần nhau
            for room_group in room_groups:
                # Số lượng giám thị cần cho nhóm phòng này
                supervisors_needed = len(room_group) * self.config.supervisors_per_room
                
                # Nếu không đủ giáo viên, giảm số lượng giám thị/phòng xuống
                if len(available_teachers) < supervisors_needed:
                    supervisors_per_room = max(1, len(available_teachers) // len(room_group))
                else:
                    supervisors_per_room = self.config.supervisors_per_room
                
                # Sắp xếp giáo viên theo số lần phân công (tăng dần)
                available_teachers.sort(key=lambda t: self.teacher_assignments.get(t["id"], 0))
                
                # Phân công giáo viên cho từng phòng trong nhóm
                for exam in room_group:
                    exam_supervisors = []
                    
                    for _ in range(supervisors_per_room):
                        if not available_teachers:
                            # Nếu hết giáo viên, sử dụng giám thị ảo
                            exam_supervisors.append(f"DEMO_SUPERVISOR_{_+1}")
                        else:
                            selected_teacher = available_teachers.pop(0)
                            
                            # Đảm bảo teacher ID luôn là string
                            teacher_id = selected_teacher["id"]
                            if isinstance(teacher_id, ObjectId):
                                teacher_id = str(teacher_id)
                            
                            exam_supervisors.append(teacher_id)
                            
                            # Tăng số lần phân công cho giáo viên được chọn
                            self.teacher_assignments[selected_teacher["id"]] = self.teacher_assignments.get(selected_teacher["id"], 0) + 1
                            
                            # Thêm giáo viên vào danh sách đã phân công cho thời gian này
                            if time_key not in teacher_assignments_by_time:
                                teacher_assignments_by_time[time_key] = []
                            teacher_assignments_by_time[time_key].append(selected_teacher["id"])
                    
                    exam["supervisor_ids"] = exam_supervisors
        
        # Đảm bảo tất cả exam đều có supervisor_ids
        for exam in scheduled_exams:
            if "supervisor_ids" not in exam or not exam["supervisor_ids"]:
                exam["supervisor_ids"] = [f"DEMO_SUPERVISOR_{i+1}" for i in range(self.config.supervisors_per_room)]
        
        return scheduled_exams
    
    def _group_nearby_rooms(self, exams):
        """
        Nhóm các phòng thi gần nhau để tối ưu hóa việc phân công giám thị
        """
        # Nếu số lượng exams ít, trả về một nhóm duy nhất
        if len(exams) <= 1:
            return [exams]
            
        # Nhóm exams theo phòng gần nhau
        groups = []
        remaining_exams = exams.copy()
        
        while remaining_exams:
            # Bắt đầu một nhóm mới với exam đầu tiên
            current_group = [remaining_exams.pop(0)]
            current_room_id = current_group[0]["room_id"]
            
            # Tìm các phòng gần với phòng hiện tại
            for _ in range(min(len(remaining_exams), 3)):  # Giới hạn mỗi nhóm tối đa 4 phòng
                # Tính điểm tương thích với phòng hiện tại
                best_exam = None
                best_score = -1
                
                for exam in remaining_exams:
                    room_id = exam["room_id"]
                    score = self.parallel_rooms_weight.get((current_room_id, room_id), 0)
                    
                    if score > best_score:
                        best_score = score
                        best_exam = exam
                
                # Nếu tìm thấy phòng với điểm tương thích đủ cao (> 0.5), thêm vào nhóm hiện tại
                if best_exam and best_score > 0.5:
                    current_group.append(best_exam)
                    remaining_exams.remove(best_exam)
                else:
                    break  # Không có phòng đủ gần, kết thúc nhóm hiện tại
            
            groups.append(current_group)
        
        return groups
        
    async def _get_student_ids(self, db, student_codes):
        """
        Chuyển đổi mã sinh viên sang ID thực tế trong database
        """
        student_ids = []
        for code in student_codes:
            # Tìm kiếm sinh viên theo mã
            student = await db.students.find_one({"student_id": code})
            if student:
                student_ids.append(code)
            else:
                # Nếu không tìm thấy, sử dụng mã như là ID
                student_ids.append(code)
                
        return student_ids
