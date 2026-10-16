"""
Module: task_calculator_db.py
Mục đích: Quản lý truy vấn và khởi tạo Database cho Task Calculator (Geometric Relational Inspection).
Bao gồm:
- Tự động đảm bảo 2 bảng task_calculator và task_calculator_rules tồn tại.
- Thao tác CRUD (Create, Read, Update, Delete) cho Task và Rules theo camera_id.
"""

from app_logger.app_logger import get_logger
from datetime import datetime
from typing import List, Dict, Any, Optional

_log = get_logger('module_3.task_calculator_db')

SQL_CREATE_TASK_CALCULATOR = """
CREATE TABLE IF NOT EXISTS task_calculator (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    camera_id       INT NOT NULL,
    task_name       VARCHAR(255) NOT NULL,
    task_type       VARCHAR(50) NOT NULL DEFAULT 'RELATION_COORDINATE',
    logic_mode      VARCHAR(20) NOT NULL DEFAULT 'ALL_PASS',
    action_on_fail  VARCHAR(20) NOT NULL DEFAULT 'NG',
    enabled         TINYINT(1) NOT NULL DEFAULT 1,
    assign_register VARCHAR(255) DEFAULT '',
    value_bit_on    INT DEFAULT 1,
    value_bit_off   INT DEFAULT 0,
    datetime        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (camera_id) REFERENCES NUMS_CAMERA(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

SQL_CREATE_TASK_CALCULATOR_RULES = """
CREATE TABLE IF NOT EXISTS task_calculator_rules (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    task_id                 INT NOT NULL,
    rule_name               VARCHAR(255),
    label_1                 VARCHAR(255) NOT NULL,
    param_1                 VARCHAR(50) NOT NULL,
    instance_select_1       VARCHAR(50) NOT NULL DEFAULT 'BEST_CONF',
    operator                VARCHAR(20) NOT NULL,
    target_type             VARCHAR(50) NOT NULL DEFAULT 'LABEL',
    label_2                 VARCHAR(255),
    param_2                 VARCHAR(50),
    instance_select_2       VARCHAR(50) NOT NULL DEFAULT 'BEST_CONF',
    math_op                 VARCHAR(10) DEFAULT 'NONE',
    math_operand_type       VARCHAR(50) DEFAULT 'CONSTANT',
    math_operand_val        VARCHAR(255) DEFAULT '0',
    min_value               DOUBLE DEFAULT 0,
    max_value               DOUBLE DEFAULT 0,
    condition_true_result   VARCHAR(10) NOT NULL DEFAULT 'NG',
    enabled                 TINYINT(1) NOT NULL DEFAULT 1,
    description             TEXT,
    FOREIGN KEY (task_id) REFERENCES task_calculator(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


def get_raw_mysql_connection(conn):
    """
    Trích xuất đối tượng MySQLConnection gốc từ bất kỳ đối tượng wrapper nào
    (Connect2Mysql, core, DatabaseManager, hoặc raw MySQLConnection).
    """
    curr = conn
    for _ in range(5):
        if curr is None:
            return None
        if hasattr(curr, 'connection') and curr.connection is not None:
            curr = curr.connection
        elif hasattr(curr, 'connect_db') and curr.connect_db is not None:
            curr = curr.connect_db
        else:
            break
    return curr


def safe_commit(conn):
    """Thực hiện commit an toàn trên kết nối gốc."""
    raw = get_raw_mysql_connection(conn)
    if raw and hasattr(raw, 'commit'):
        try:
            raw.commit()
        except Exception as e:
            _log.warning("safe_commit error: %s", e)


def safe_rollback(conn):
    """Thực hiện rollback an toàn trên kết nối gốc."""
    raw = get_raw_mysql_connection(conn)
    if raw and hasattr(raw, 'rollback'):
        try:
            raw.rollback()
        except Exception as e:
            _log.warning("safe_rollback error: %s", e)


def ensure_task_calculator_tables(cursor, connection) -> bool:
    """Tự động đảm bảo 2 bảng task_calculator và task_calculator_rules tồn tại."""
    if not cursor or not connection:
        return False
    try:
        cursor.execute(SQL_CREATE_TASK_CALCULATOR)
        cursor.execute(SQL_CREATE_TASK_CALCULATOR_RULES)

        # Kiểm tra và migrate tự động cột assign_register nếu bảng cũ chưa có
        cursor.execute("SHOW COLUMNS FROM task_calculator LIKE 'assign_register'")
        if not cursor.fetchone():
            _log.info("Migrating task_calculator: thêm cột assign_register, value_bit_on, value_bit_off")
            cursor.execute("ALTER TABLE task_calculator ADD COLUMN assign_register VARCHAR(255) DEFAULT ''")
            cursor.execute("ALTER TABLE task_calculator ADD COLUMN value_bit_on INT DEFAULT 1")
            cursor.execute("ALTER TABLE task_calculator ADD COLUMN value_bit_off INT DEFAULT 0")
            cursor.execute("ALTER TABLE task_calculator ADD COLUMN logic_mode VARCHAR(20) DEFAULT 'ALL_PASS'")
            cursor.execute("ALTER TABLE task_calculator ADD COLUMN action_on_fail VARCHAR(20) DEFAULT 'NG'")
            cursor.execute("ALTER TABLE task_calculator ADD COLUMN enabled TINYINT(1) DEFAULT 1")

        safe_commit(connection)
        return True
    except Exception as e:
        _log.error("Lỗi khi đảm bảo các bảng task_calculator: %s", e)
        safe_rollback(connection)
        return False


def get_tasks_by_camera(cursor, camera_id: int) -> List[Dict[str, Any]]:
    """Lấy danh sách tất cả các task thuộc camera_id kèm số lượng rule con."""
    if not cursor:
        return []
    try:
        query = """
            SELECT t.id, t.camera_id, t.task_name, t.task_type, t.logic_mode, 
                   t.action_on_fail, t.enabled, t.assign_register, t.value_bit_on, 
                   t.value_bit_off, t.datetime,
                   COUNT(r.id) AS rule_count
            FROM task_calculator t
            LEFT JOIN task_calculator_rules r ON t.id = r.task_id
            WHERE t.camera_id = %s
            GROUP BY t.id
            ORDER BY t.id ASC
        """
        cursor.execute(query, (camera_id,))
        rows = cursor.fetchall()
        tasks = []
        for r in rows:
            tasks.append({
                'id': r[0],
                'camera_id': r[1],
                'task_name': r[2],
                'task_type': r[3],
                'logic_mode': r[4],
                'action_on_fail': r[5],
                'enabled': bool(r[6]),
                'assign_register': r[7] or '',
                'value_bit_on': r[8] if r[8] is not None else 1,
                'value_bit_off': r[9] if r[9] is not None else 0,
                'datetime': r[10],
                'rule_count': r[11]
            })
        return tasks
    except Exception as e:
        _log.error("Lỗi get_tasks_by_camera (camera_id=%s): %s", camera_id, e)
        return []


def get_task_by_id(cursor, task_id: int) -> Optional[Dict[str, Any]]:
    """Lấy thông tin chi tiết đầy đủ của 1 task theo ID từ database."""
    if not cursor:
        return None
    try:
        query = """
            SELECT id, camera_id, task_name, task_type, logic_mode, 
                   action_on_fail, enabled, assign_register, value_bit_on, 
                   value_bit_off, datetime
            FROM task_calculator
            WHERE id = %s
        """
        cursor.execute(query, (task_id,))
        r = cursor.fetchone()
        if not r:
            return None
        return {
            'id': r[0],
            'camera_id': r[1],
            'task_name': r[2],
            'task_type': r[3],
            'logic_mode': r[4],
            'action_on_fail': r[5],
            'enabled': bool(r[6]),
            'assign_register': r[7] or '',
            'value_bit_on': r[8] if r[8] is not None else 1,
            'value_bit_off': r[9] if r[9] is not None else 0,
            'datetime': r[10]
        }
    except Exception as e:
        _log.error("Lỗi get_task_by_id (task_id=%s): %s", task_id, e)
        return None


def get_task_rules(cursor, task_id: int) -> List[Dict[str, Any]]:
    """Lấy danh sách các rule của 1 task."""
    if not cursor:
        return []
    try:
        query = """
            SELECT id, task_id, rule_name, label_1, param_1, instance_select_1,
                   operator, target_type, label_2, param_2, instance_select_2,
                   math_op, math_operand_type, math_operand_val, min_value, max_value,
                   condition_true_result, enabled, description
            FROM task_calculator_rules
            WHERE task_id = %s
            ORDER BY id ASC
        """
        cursor.execute(query, (task_id,))
        rows = cursor.fetchall()
        rules = []
        for r in rows:
            rules.append({
                'id': r[0],
                'task_id': r[1],
                'rule_name': r[2] or '',
                'label_1': r[3],
                'param_1': r[4],
                'instance_select_1': r[5] or 'BEST_CONF',
                'operator': r[6],
                'target_type': r[7] or 'LABEL',
                'label_2': r[8] or '',
                'param_2': r[9] or '',
                'instance_select_2': r[10] or 'BEST_CONF',
                'math_op': r[11] or 'NONE',
                'math_operand_type': r[12] or 'CONSTANT',
                'math_operand_val': str(r[13] if r[13] is not None else '0'),
                'min_value': float(r[14] or 0.0),
                'max_value': float(r[15] or 0.0),
                'condition_true_result': r[16] or 'NG',
                'enabled': bool(r[17]),
                'description': r[18] or ''
            })
        return rules
    except Exception as e:
        _log.error("Lỗi get_task_rules (task_id=%s): %s", task_id, e)
        return []


def save_task_and_rules(cursor, connection, task_data: Dict[str, Any], rules: List[Dict[str, Any]]) -> Optional[int]:
    """
    Tạo mới hoặc cập nhật 1 Task cùng toàn bộ Rules của nó trong transaction an toàn.
    Trả về task_id nếu thành công, None nếu thất bại.
    """
    if not cursor or not connection:
        return None
    try:
        task_id = task_data.get('id')
        camera_id = task_data['camera_id']
        task_name = task_data.get('task_name', 'Task Mới')
        task_type = task_data.get('task_type', 'RELATION_COORDINATE')
        logic_mode = task_data.get('logic_mode', 'ALL_PASS')
        action_on_fail = task_data.get('action_on_fail', 'NG')
        enabled = 1 if task_data.get('enabled', True) else 0
        assign_register = task_data.get('assign_register', '').strip()
        value_bit_on = int(task_data.get('value_bit_on', 1))
        value_bit_off = int(task_data.get('value_bit_off', 0))

        if task_id:
            # Update Task
            cursor.execute("""
                UPDATE task_calculator
                SET task_name = %s, task_type = %s, logic_mode = %s, action_on_fail = %s,
                    enabled = %s, assign_register = %s, value_bit_on = %s, value_bit_off = %s
                WHERE id = %s AND camera_id = %s
            """, (task_name, task_type, logic_mode, action_on_fail, enabled,
                  assign_register, value_bit_on, value_bit_off, task_id, camera_id))
            
            # Xóa các rules cũ để ghi lại danh sách mới
            cursor.execute("DELETE FROM task_calculator_rules WHERE task_id = %s", (task_id,))
        else:
            # Insert Task
            cursor.execute("""
                INSERT INTO task_calculator
                (camera_id, task_name, task_type, logic_mode, action_on_fail, enabled,
                 assign_register, value_bit_on, value_bit_off)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (camera_id, task_name, task_type, logic_mode, action_on_fail, enabled,
                  assign_register, value_bit_on, value_bit_off))
            task_id = cursor.lastrowid

        # Insert các Rules
        for r in rules:
            cursor.execute("""
                INSERT INTO task_calculator_rules
                (task_id, rule_name, label_1, param_1, instance_select_1,
                 operator, target_type, label_2, param_2, instance_select_2,
                 math_op, math_operand_type, math_operand_val, min_value, max_value,
                 condition_true_result, enabled, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                task_id,
                r.get('rule_name', ''),
                r['label_1'],
                r['param_1'],
                r.get('instance_select_1', 'BEST_CONF'),
                r['operator'],
                r.get('target_type', 'LABEL'),
                r.get('label_2', ''),
                r.get('param_2', ''),
                r.get('instance_select_2', 'BEST_CONF'),
                r.get('math_op', 'NONE'),
                r.get('math_operand_type', 'CONSTANT'),
                str(r.get('math_operand_val', '0')),
                float(r.get('min_value', 0.0)),
                float(r.get('max_value', 0.0)),
                r.get('condition_true_result', 'NG'),
                1 if r.get('enabled', True) else 0,
                r.get('description', '')
            ))

        safe_commit(connection)
        _log.info("Lưu thành công Task id=%s (gồm %s rules) cho camera_id=%s", task_id, len(rules), camera_id)
        return task_id
    except Exception as e:
        _log.error("Lỗi khi lưu Task và Rules: %s", e)
        safe_rollback(connection)
        return None


def delete_task(cursor, connection, task_id: int) -> bool:
    """Xóa task và các rule con liên kết."""
    if not cursor or not connection:
        return False
    try:
        cursor.execute("DELETE FROM task_calculator WHERE id = %s", (task_id,))
        safe_commit(connection)
        _log.info("Đã xóa Task id=%s", task_id)
        return True
    except Exception as e:
        _log.error("Lỗi khi xóa Task id=%s: %s", task_id, e)
        safe_rollback(connection)
        return False


def toggle_task_enabled(cursor, connection, task_id: int, enabled: bool) -> bool:
    """Bật/tắt nhanh 1 task."""
    if not cursor or not connection:
        return False
    try:
        cursor.execute("UPDATE task_calculator SET enabled = %s WHERE id = %s", (1 if enabled else 0, task_id))
        safe_commit(connection)
        return True
    except Exception as e:
        _log.error("Lỗi khi toggle task id=%s: %s", task_id, e)
        safe_rollback(connection)
        return False


def get_available_labels_for_camera(cursor, camera_id: int) -> List[str]:
    """
    Lấy danh sách các nhãn đã cấu hình trong bảng PARAMETERSET của camera này,
    phục vụ việc đổ dữ liệu vào combobox chọn nhãn.
    """
    if not cursor:
        return []
    try:
        query = """
            SELECT DISTINCT p.Label_Name
            FROM PARAMETERSET p
            JOIN NUMS_MODEL m ON p.model_id = m.id
            WHERE m.camera_id = %s
            ORDER BY p.Label_Name ASC
        """
        cursor.execute(query, (camera_id,))
        rows = cursor.fetchall()
        labels = [r[0] for r in rows if r[0] and str(r[0]).strip()]
        return labels
    except Exception as e:
        _log.error("Lỗi khi lấy danh sách nhãn của camera_id=%s: %s", camera_id, e)
        return []
