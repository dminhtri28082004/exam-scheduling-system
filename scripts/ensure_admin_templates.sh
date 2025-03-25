#!/bin/bash

# Create admin templates directory
mkdir -p app/templates/admin

# Create a basic admin/rooms.html template if it doesn't exist
if [ ! -f app/templates/admin/rooms.html ]; then
    echo "Creating basic admin rooms template..."
    cat > app/templates/admin/rooms.html << 'EOF'
{% extends "shared/base.html" %}

{% block title %}Quản lý phòng thi{% endblock %}

{% block content %}
<div class="container mt-4">
    <h1 class="mb-4">Quản lý phòng thi</h1>
    
    <div class="row mb-4">
        <div class="col-md-4">
            <div class="card">
                <div class="card-body">
                    <h5 class="card-title">Tổng số phòng</h5>
                    <p class="card-text display-4">{{ rooms_count }}</p>
                </div>
            </div>
        </div>
        <div class="col-md-4">
            <div class="card">
                <div class="card-body">
                    <h5 class="card-title">Tổng sức chứa</h5>
                    <p class="card-text display-4">{{ total_capacity }}</p>
                </div>
            </div>
        </div>
        <div class="col-md-4">
            <div class="card">
                <div class="card-body">
                    <h5 class="card-title">Hành động</h5>
                    <button type="button" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addRoomModal">
                        Thêm phòng mới
                    </button>
                </div>
            </div>
        </div>
    </div>
    
    <div class="card">
        <div class="card-header">
            <h5 class="mb-0">Danh sách phòng thi</h5>
        </div>
        <div class="card-body">
            <div class="table-responsive">
                <table class="table table-striped table-hover">
                    <thead>
                        <tr>
                            <th>Mã phòng</th>
                            <th>Tên phòng</th>
                            <th>Tòa nhà</th>
                            <th>Sức chứa</th>
                            <th>Hành động</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for room in rooms %}
                        <tr>
                            <td>{{ room.room_id }}</td>
                            <td>{{ room.name|default(room.room_id) }}</td>
                            <td>{{ room.building|default('Chưa xác định') }}</td>
                            <td>{{ room.capacity }}</td>
                            <td>
                                <button class="btn btn-sm btn-primary edit-room" 
                                    data-id="{{ room._id }}" 
                                    data-room-id="{{ room.room_id }}" 
                                    data-name="{{ room.name|default('') }}" 
                                    data-building="{{ room.building|default('') }}" 
                                    data-capacity="{{ room.capacity }}"
                                    data-bs-toggle="modal" 
                                    data-bs-target="#editRoomModal">
                                    Sửa
                                </button>
                                <button class="btn btn-sm btn-danger delete-room" 
                                    data-id="{{ room._id }}" 
                                    data-room-id="{{ room.room_id }}">
                                    Xóa
                                </button>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<!-- Modal thêm phòng -->
<div class="modal fade" id="addRoomModal" tabindex="-1" aria-labelledby="addRoomModalLabel" aria-hidden="true">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title" id="addRoomModalLabel">Thêm phòng mới</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
                <form id="addRoomForm">
                    <div class="mb-3">
                        <label for="room_id" class="form-label">Mã phòng</label>
                        <input type="text" class="form-control" id="room_id" name="room_id" required>
                    </div>
                    <div class="mb-3">
                        <label for="name" class="form-label">Tên phòng</label>
                        <input type="text" class="form-control" id="name" name="name">
                    </div>
                    <div class="mb-3">
                        <label for="building" class="form-label">Tòa nhà</label>
                        <input type="text" class="form-control" id="building" name="building">
                    </div>
                    <div class="mb-3">
                        <label for="capacity" class="form-label">Sức chứa</label>
                        <input type="number" class="form-control" id="capacity" name="capacity" min="1" required>
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Hủy</button>
                <button type="button" class="btn btn-primary" id="submitAddRoom">Thêm</button>
            </div>
        </div>
    </div>
</div>

<!-- Modal sửa phòng -->
<div class="modal fade" id="editRoomModal" tabindex="-1" aria-labelledby="editRoomModalLabel" aria-hidden="true">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title" id="editRoomModalLabel">Sửa thông tin phòng</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
                <form id="editRoomForm">
                    <input type="hidden" id="edit_id">
                    <div class="mb-3">
                        <label for="edit_room_id" class="form-label">Mã phòng</label>
                        <input type="text" class="form-control" id="edit_room_id" name="room_id" required>
                    </div>
                    <div class="mb-3">
                        <label for="edit_name" class="form-label">Tên phòng</label>
                        <input type="text" class="form-control" id="edit_name" name="name">
                    </div>
                    <div class="mb-3">
                        <label for="edit_building" class="form-label">Tòa nhà</label>
                        <input type="text" class="form-control" id="edit_building" name="building">
                    </div>
                    <div class="mb-3">
                        <label for="edit_capacity" class="form-label">Sức chứa</label>
                        <input type="number" class="form-control" id="edit_capacity" name="capacity" min="1" required>
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Hủy</button>
                <button type="button" class="btn btn-primary" id="submitEditRoom">Lưu</button>
            </div>
        </div>
    </div>
</div>

<!-- Modal xác nhận xóa phòng -->
<div class="modal fade" id="confirmDeleteModal" tabindex="-1" aria-labelledby="confirmDeleteModalLabel" aria-hidden="true">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title" id="confirmDeleteModalLabel">Xác nhận xóa</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
                <p>Bạn có chắc chắn muốn xóa phòng <strong id="roomToDelete"></strong>?</p>
                <input type="hidden" id="deleteRoomId">
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Hủy</button>
                <button type="button" class="btn btn-danger" id="confirmDelete">Xóa</button>
            </div>
        </div>
    </div>
</div>

<script>
document.addEventListener('DOMContentLoaded', function() {
    // Xử lý thêm phòng mới
    document.getElementById('submitAddRoom').addEventListener('click', function() {
        const formData = {
            room_id: document.getElementById('room_id').value,
            name: document.getElementById('name').value,
            building: document.getElementById('building').value,
            capacity: parseInt(document.getElementById('capacity').value)
        };
        
        fetch('/api/v1/rooms/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': getAuthToken()
            },
            body: JSON.stringify(formData)
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw err; });
            }
            return response.json();
        })
        .then(data => {
            alert('Thêm phòng thành công!');
            location.reload();
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Lỗi: ' + (error.detail || 'Không thể thêm phòng'));
        });
    });
    
    // Xử lý hiển thị modal sửa phòng
    document.querySelectorAll('.edit-room').forEach(button => {
        button.addEventListener('click', function() {
            document.getElementById('edit_id').value = this.getAttribute('data-id');
            document.getElementById('edit_room_id').value = this.getAttribute('data-room-id');
            document.getElementById('edit_name').value = this.getAttribute('data-name');
            document.getElementById('edit_building').value = this.getAttribute('data-building');
            document.getElementById('edit_capacity').value = this.getAttribute('data-capacity');
        });
    });
    
    // Xử lý sửa phòng
    document.getElementById('submitEditRoom').addEventListener('click', function() {
        const id = document.getElementById('edit_id').value;
        const formData = {
            room_id: document.getElementById('edit_room_id').value,
            name: document.getElementById('edit_name').value,
            building: document.getElementById('edit_building').value,
            capacity: parseInt(document.getElementById('edit_capacity').value)
        };
        
        fetch(`/api/v1/rooms/${id}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': getAuthToken()
            },
            body: JSON.stringify(formData)
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw err; });
            }
            return response.json();
        })
        .then(data => {
            alert('Cập nhật phòng thành công!');
            location.reload();
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Lỗi: ' + (error.detail || 'Không thể cập nhật phòng'));
        });
    });
    
    // Xử lý hiển thị modal xóa phòng
    document.querySelectorAll('.delete-room').forEach(button => {
        button.addEventListener('click', function() {
            const id = this.getAttribute('data-id');
            const roomId = this.getAttribute('data-room-id');
            document.getElementById('deleteRoomId').value = id;
            document.getElementById('roomToDelete').textContent = roomId;
            
            new bootstrap.Modal(document.getElementById('confirmDeleteModal')).show();
        });
    });
    
    // Xử lý xóa phòng
    document.getElementById('confirmDelete').addEventListener('click', function() {
        const id = document.getElementById('deleteRoomId').value;
        
        fetch(`/api/v1/rooms/${id}`, {
            method: 'DELETE',
            headers: {
                'Authorization': getAuthToken()
            }
        })
        .then(response => {
            if (!response.ok) {
                if (response.status === 400) {
                    return response.json().then(err => { throw err; });
                }
                throw new Error('Network response was not ok');
            }
            alert('Xóa phòng thành công!');
            location.reload();
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Lỗi: ' + (error.detail || 'Không thể xóa phòng'));
        });
    });
});
</script>
{% endblock %}
EOF
fi

# Create a basic shared/base.html template if it doesn't exist
if [ ! -f app/templates/shared/base.html ]; then
    echo "Creating basic base template..."
    cat > app/templates/shared/base.html << 'EOF'
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Hệ thống lập lịch thi{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="/static/css/styles.css">
    {% block additional_css %}{% endblock %}
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/ui/dashboard">Hệ thống lập lịch thi</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav" aria-controls="navbarNav" aria-expanded="false" aria-label="Toggle navigation">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav ms-auto">
                    <li class="nav-item">
                        <a class="nav-link" href="/ui/profile">Tài khoản</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/ui/logout">Đăng xuất</a>
                    </li>
                </ul>
            </div>
        </div>
    </nav>

    <main>
        {% block content %}{% endblock %}
    </main>

    <footer class="bg-light py-3 mt-5">
        <div class="container text-center">
            <p class="text-muted mb-0">© 2023 Hệ thống lập lịch thi. Đồ án cơ sở.</p>
        </div>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
    <script src="/static/js/main.js"></script>
    {% block additional_js %}{% endblock %}
</body>
</html>
EOF
fi

echo "Admin templates setup complete!"
chmod +x "$0"
