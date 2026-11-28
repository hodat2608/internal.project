"""
Module: task_calculator_db.py
Mục đích: Quản lý truy vấn và khởi tạo Database cho Task Calculator (Geometric Relational Inspection).
Bao gồm:
- Tự động đảm bảo 2 bảng task_calculator và task_calculator_rules tồn tại (chỉ chạy 1 lần duy nhất).
- Cơ chế Thread-Safe (RLock) và Auto-Ping / Reconnect bảo vệ kết nối MySQL không bị Lost Connection khi nhiều Camera chạy song song.
- Thao tác CRUD (Create, Read, Update, Delete) cho Task và Rules theo camera_id.
"""

import threading
from app_logger.app_logger import get_logger
from datetime import datetime
from typing import List, Dict, Any, Optional

_log = get_logger('module_3.task_calculator_db')
_db_lock = threading.RLock()
_ensured_databases = set()

SQL_CREATE_TASK_CALCULATOR = """
CREATE TABLE IF NOT EXISTS task_calculator (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    camera_id       INT NOT NULL,
    model_id        INT NOT NULL DEFAULT 1,
    task_name       VARCHAR(255) NOT NULL,
    task_type       VARCHAR(50) NOT NULL DEFAULT 'RELATION_COORDINATE',
    logic_mode      VARCHAR(20) NOT NULL DEFAULT 'ALL_PASS',
    action_on_fail  VARCHAR(20) NOT NULL DEFAULT 'NG',
    enabled         TINYINT(1) NOT NULL DEFAULT 1,
    assign_register VARCHAR(255) DEFAULT '',
    value_state     INT DEFAULT 1,
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
    instance_scope          VARCHAR(50) NOT NULL DEFAULT '1_VS_1',
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
    box1_rect               VARCHAR(100) DEFAULT '',
    box2_rect               VARCHAR(100) DEFAULT '',
    FOREIGN KEY (task_id) REFERENCES task_calculator(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

SQL_CREATE_TASK_MULTISHOT_RULES = """
CREATE TABLE IF NOT EXISTS task_multishot_rules (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    task_id             INT NOT NULL,
    target_label        VARCHAR(255) NOT NULL,
    cycle_shots         INT NOT NULL DEFAULT 5,
    aggregation_mode    VARCHAR(50) NOT NULL DEFAULT 'THRESHOLD_COUNT',
    min_ng_shots        INT NOT NULL DEFAULT 2,
    specific_shots      VARCHAR(255) DEFAULT '',
    participating_shots VARCHAR(255) DEFAULT '',
    roi_enabled         TINYINT(1) NOT NULL DEFAULT 0,
    roi_mode            VARCHAR(50) NOT NULL DEFAULT 'IN_BOUNDS',
    roi_boxes           TEXT,
    timeout_reset_sec   DOUBLE NOT NULL DEFAULT 0.0,
    description         TEXT,
    FOREIGN KEY (task_id) REFERENCES task_calculator(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

SQL_CREATE_TASK_ROI_RULES = """
CREATE TABLE IF NOT EXISTS task_roi_rules (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    task_id             INT NOT NULL,
    zones_json          LONGTEXT NOT NULL,
    default_target      VARCHAR(255) DEFAULT '',
    action_mode         VARCHAR(50) DEFAULT 'DEFECT_FILTER',
    description         TEXT,
    FOREIGN KEY (task_id) REFERENCES task_calculator(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


def get_raw_mysql_connection(conn_or_cursor):
    """
    Trích xuất đối tượng MySQLConnection gốc từ bất kỳ đối tượng wrapper nào
    (Connect2Mysql, core, DatabaseManager, MySQLCursor, hoặc raw MySQLConnection).
    """
    curr = conn_or_cursor
    for _ in range(5):
        if curr is None:
            return None
        if hasattr(curr, '_connection') and curr._connection is not None:
            curr = curr._connection
        elif hasattr(curr, 'connection') and curr.connection is not None:
            curr = curr.connection
        elif hasattr(curr, 'connect_db') and curr.connect_db is not None:
            curr = curr.connect_db
        else:
            break
    return curr


def ensure_connection_alive(conn_or_cursor):
    """Đảm bảo kết nối MySQL còn sống, tự động ping và reconnect nếu bị đứt kết nối."""
    raw = get_raw_mysql_connection(conn_or_cursor)
    if raw:
        try:
            if hasattr(raw, 'is_connected') and not raw.is_connected():
                raw.ping(reconnect=True, attempts=3, delay=0.5)
            elif hasattr(raw, 'ping'):
                raw.ping(reconnect=True, attempts=1, delay=0)
        except Exception:
            try:
                if hasattr(raw, 'reconnect'):
                    raw.reconnect(attempts=3, delay=0.5)
            except Exception:
                pass
    return raw


def get_active_cursor(conn_or_cursor):
    """
    Đảm bảo kết nối MySQL còn sống và trả về một cursor hợp lệ sẵn sàng thực thi truy vấn.
    Nếu cursor cũ bị đóng hoặc mất kết nối, tự động tạo mới cursor từ connection.
    """
    raw = ensure_connection_alive(conn_or_cursor)
    if hasattr(conn_or_cursor, 'execute') and not hasattr(conn_or_cursor, 'commit'):
        if not getattr(conn_or_cursor, '_closed', False) and getattr(conn_or_cursor, '_connection', None) is not None:
            try:
                if hasattr(conn_or_cursor, 'fetchall'):
                    try:
                        conn_or_cursor.fetchall()
                    except Exception:
                        pass
                return conn_or_cursor
            except Exception:
                pass
    if raw and hasattr(raw, 'cursor'):
        try:
            return raw.cursor(buffered=True)
        except Exception:
            try:
                return raw.cursor()
            except Exception:
                pass
    return conn_or_cursor


def safe_commit(conn):
    """Thực hiện commit an toàn trên kết nối gốc có bảo vệ đa luồng."""
    with _db_lock:
        raw = get_raw_mysql_connection(conn)
        if raw and hasattr(raw, 'commit'):
            try:
                ensure_connection_alive(raw)
                raw.commit()
            except Exception as e:
                _log.warning("safe_commit error: %s", e)


def safe_rollback(conn):
    """Thực hiện rollback an toàn trên kết nối gốc có bảo vệ đa luồng."""
    with _db_lock:
        raw = get_raw_mysql_connection(conn)
        if raw and hasattr(raw, 'rollback'):
            try:
                ensure_connection_alive(raw)
                raw.rollback()
            except Exception as e:
                _log.warning("safe_rollback error: %s", e)


def ensure_task_calculator_tables(cursor, connection) -> bool:
    """
    Tự động đảm bảo 3 bảng task_calculator, task_calculator_rules và task_multishot_rules tồn tại
    cùng toàn bộ các cột cần thiết (Chạy an toàn đa luồng _db_lock, hỗ trợ migrate tự động).
    """
    if not cursor or not connection:
        return False
    with _db_lock:
        try:
            ensure_connection_alive(cursor)
            cur = get_active_cursor(cursor)

            # Lấy tên database hiện tại để quản lý trạng thái khởi tạo an toàn theo từng CSDL
            db_name = None
            try:
                cur.execute("SELECT DATABASE()")
                row = cur.fetchone()
                if row and row[0]:
                    db_name = str(row[0]).strip().lower()
            except Exception:
                db_name = None

            if db_name and db_name in _ensured_databases:
                return True

            cur.execute(SQL_CREATE_TASK_CALCULATOR)
            cur.execute(SQL_CREATE_TASK_CALCULATOR_RULES)
            cur.execute(SQL_CREATE_TASK_MULTISHOT_RULES)
            cur.execute(SQL_CREATE_TASK_ROI_RULES)

            # 1. Kiểm tra và migrate tự động cột task_type nếu bảng cũ chưa có
            try:
                cur.execute("SHOW COLUMNS FROM task_calculator LIKE 'task_type'")
                if not cur.fetchone():
                    _log.info("Migrating task_calculator: thêm cột task_type")
                    cur.execute("ALTER TABLE task_calculator ADD COLUMN task_type VARCHAR(50) NOT NULL DEFAULT 'RELATION_COORDINATE' AFTER task_name")
            except Exception:
                pass

            # 2. Kiểm tra và migrate tự động cột assign_register nếu bảng cũ chưa có
            try:
                cur.execute("SHOW COLUMNS FROM task_calculator LIKE 'assign_register'")
                if not cur.fetchone():
                    _log.info("Migrating task_calculator: thêm cột assign_register, value_bit_on, value_bit_off")
                    cur.execute("ALTER TABLE task_calculator ADD COLUMN assign_register VARCHAR(255) DEFAULT ''")
                    cur.execute("ALTER TABLE task_calculator ADD COLUMN value_bit_on INT DEFAULT 1")
                    cur.execute("ALTER TABLE task_calculator ADD COLUMN value_bit_off INT DEFAULT 0")
                    cur.execute("ALTER TABLE task_calculator ADD COLUMN logic_mode VARCHAR(20) DEFAULT 'ALL_PASS'")
                    cur.execute("ALTER TABLE task_calculator ADD COLUMN action_on_fail VARCHAR(20) DEFAULT 'NG'")
                    cur.execute("ALTER TABLE task_calculator ADD COLUMN enabled TINYINT(1) DEFAULT 1")
            except Exception:
                pass

            # 3. Kiểm tra và migrate tự động cột value_state nếu bảng cũ chưa có
            try:
                cur.execute("SHOW COLUMNS FROM task_calculator LIKE 'value_state'")
                if not cur.fetchone():
                    cur.execute("SHOW COLUMNS FROM task_calculator LIKE 'Value_State'")
                    if not cur.fetchone():
                        _log.info("Migrating task_calculator: thêm cột value_state (Value_State)")
                        cur.execute("ALTER TABLE task_calculator ADD COLUMN value_state INT DEFAULT 1 AFTER assign_register")
            except Exception:
                pass

            # 4. Kiểm tra và migrate tự động cột model_id nếu bảng cũ chưa có
            try:
                cur.execute("SHOW COLUMNS FROM task_calculator LIKE 'model_id'")
                if not cur.fetchone():
                    _log.info("Migrating task_calculator: thêm cột model_id")
                    cur.execute("ALTER TABLE task_calculator ADD COLUMN model_id INT NOT NULL DEFAULT 1 AFTER camera_id")
            except Exception:
                pass

            # 5. Kiểm tra và migrate tự động cột instance_scope nếu bảng cũ chưa có
            try:
                cur.execute("SHOW COLUMNS FROM task_calculator_rules LIKE 'instance_scope'")
                if not cur.fetchone():
                    _log.info("Migrating task_calculator_rules: thêm cột instance_scope")
                    cur.execute("ALTER TABLE task_calculator_rules ADD COLUMN instance_scope VARCHAR(50) NOT NULL DEFAULT '1_VS_1' AFTER instance_select_1")
            except Exception:
                pass

            # 6. Kiểm tra và migrate tự động cột box1_rect, box2_rect lưu tọa độ trực quan
            try:
                cur.execute("SHOW COLUMNS FROM task_calculator_rules LIKE 'box1_rect'")
                if not cur.fetchone():
                    _log.info("Migrating task_calculator_rules: thêm cột box1_rect")
                    cur.execute("ALTER TABLE task_calculator_rules ADD COLUMN box1_rect VARCHAR(100) DEFAULT ''")
            except Exception:
                pass

            try:
                cur.execute("SHOW COLUMNS FROM task_calculator_rules LIKE 'box2_rect'")
                if not cur.fetchone():
                    _log.info("Migrating task_calculator_rules: thêm cột box2_rect")
                    cur.execute("ALTER TABLE task_calculator_rules ADD COLUMN box2_rect VARCHAR(100) DEFAULT ''")
            except Exception:
                pass

            # 7. Kiểm tra và migrate tự động cột participating_shots trong task_multishot_rules
            try:
                cur.execute("SHOW COLUMNS FROM task_multishot_rules LIKE 'participating_shots'")
                if not cur.fetchone():
                    _log.info("Migrating task_multishot_rules: thêm cột participating_shots")
                    cur.execute("ALTER TABLE task_multishot_rules ADD COLUMN participating_shots VARCHAR(255) DEFAULT '' AFTER specific_shots")
            except Exception:
                pass

            # 8. Kiểm tra và migrate tự động cột timeout_reset_sec trong task_multishot_rules nếu thiếu
            try:
                cur.execute("SHOW COLUMNS FROM task_multishot_rules LIKE 'timeout_reset_sec'")
                if not cur.fetchone():
                    _log.info("Migrating task_multishot_rules: thêm cột timeout_reset_sec")
                    cur.execute("ALTER TABLE task_multishot_rules ADD COLUMN timeout_reset_sec DOUBLE NOT NULL DEFAULT 0.0 AFTER roi_boxes")
            except Exception:
                pass

            safe_commit(connection)
            if db_name:
                _ensured_databases.add(db_name)
            return True
        except Exception as e:
            _log.error("Lỗi khi đảm bảo các bảng task_calculator: %s", e)
            safe_rollback(connection)
            return False


def get_tasks_by_camera(cursor, camera_id: int, model_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Lấy danh sách tất cả các task thuộc camera_id (và model_id nếu có) kèm số lượng rule con."""
    if not cursor:
        return []
    with _db_lock:
        ensure_connection_alive(cursor)
        for attempt in range(2):
            try:
                # Chuẩn hóa camera_id và model_id
                c_id = None
                if camera_id is not None:
                    c_str = str(camera_id).lower().replace('camera-', '').replace('built-in-', '').strip()
                    c_id = int(c_str) if c_str.isdigit() else camera_id

                m_id = None
                if model_id is not None:
                    m_str = str(model_id).lower().replace('model-', '').replace('model', '').strip()
                    m_id = int(m_str) if m_str.isdigit() else model_id

                cur = get_active_cursor(cursor)
                has_val_state = True
                try:
                    if m_id is not None:
                        query = """
                            SELECT t.id, t.camera_id, t.model_id, t.task_name, t.task_type, t.logic_mode, 
                                   t.action_on_fail, t.enabled, t.assign_register, t.value_bit_on, 
                                   t.value_bit_off, t.datetime,
                                   COUNT(r.id) AS rule_count, t.value_state
                            FROM task_calculator t
                            LEFT JOIN task_calculator_rules r ON t.id = r.task_id
                            WHERE t.camera_id = %s AND (t.model_id = %s OR t.task_type = 'MULTI_SHOT_AGGREGATION' OR t.model_id = 0)
                            GROUP BY t.id
                            ORDER BY t.id ASC
                        """
                        cur.execute(query, (c_id, m_id))
                    else:
                        query = """
                            SELECT t.id, t.camera_id, t.model_id, t.task_name, t.task_type, t.logic_mode, 
                                   t.action_on_fail, t.enabled, t.assign_register, t.value_bit_on, 
                                   t.value_bit_off, t.datetime,
                                   COUNT(r.id) AS rule_count, t.value_state
                            FROM task_calculator t
                            LEFT JOIN task_calculator_rules r ON t.id = r.task_id
                            WHERE t.camera_id = %s
                            GROUP BY t.id
                            ORDER BY t.id ASC
                        """
                        cur.execute(query, (c_id,))
                except Exception:
                    has_val_state = False
                    if m_id is not None:
                        query = """
                            SELECT t.id, t.camera_id, t.model_id, t.task_name, t.task_type, t.logic_mode, 
                                   t.action_on_fail, t.enabled, t.assign_register, t.value_bit_on, 
                                   t.value_bit_off, t.datetime,
                                   COUNT(r.id) AS rule_count
                            FROM task_calculator t
                            LEFT JOIN task_calculator_rules r ON t.id = r.task_id
                            WHERE t.camera_id = %s AND (t.model_id = %s OR t.task_type = 'MULTI_SHOT_AGGREGATION' OR t.model_id = 0)
                            GROUP BY t.id
                            ORDER BY t.id ASC
                        """
                        cur.execute(query, (c_id, m_id))
                    else:
                        query = """
                            SELECT t.id, t.camera_id, t.model_id, t.task_name, t.task_type, t.logic_mode, 
                                   t.action_on_fail, t.enabled, t.assign_register, t.value_bit_on, 
                                   t.value_bit_off, t.datetime,
                                   COUNT(r.id) AS rule_count
                            FROM task_calculator t
                            LEFT JOIN task_calculator_rules r ON t.id = r.task_id
                            WHERE t.camera_id = %s
                            GROUP BY t.id
                            ORDER BY t.id ASC
                        """
                        cur.execute(query, (c_id,))
                rows = cur.fetchall()
                tasks = []
                for r in rows:
                    v_state = r[13] if (has_val_state and len(r) > 13 and r[13] is not None) else 1
                    v_on = r[9] if r[9] is not None else 1
                    v_off = r[10] if r[10] is not None else 0
                    t_item = {
                        'id': r[0],
                        'camera_id': r[1],
                        'model_id': r[2],
                        'task_name': r[3],
                        'task_type': r[4],
                        'logic_mode': r[5],
                        'action_on_fail': r[6],
                        'enabled': bool(r[7]),
                        'assign_register': r[8] or '',
                        'value_state': v_state,
                        'Value_State': v_state,
                        'value_bit_on': v_on,
                        'value_ok': v_on,
                        'Value_OK': v_on,
                        'value_bit_off': v_off,
                        'value_ng': v_off,
                        'Value_NG': v_off,
                        'datetime': r[11],
                        'rule_count': r[12]
                    }
                    if t_item.get('task_type') == 'MULTI_SHOT_AGGREGATION':
                        ms_rule = get_multishot_rule(cur, t_item['id'])
                        t_item['multishot_rule'] = ms_rule
                        t_item['rule_count'] = 1 if ms_rule else 0
                    elif t_item.get('task_type') == 'ROI_ZONE_INSPECTION':
                        roi_rule = get_roi_rule(cur, t_item['id'])
                        t_item['roi_rule'] = roi_rule
                        t_item['rule_count'] = len(roi_rule.get('zones', [])) if (roi_rule and isinstance(roi_rule.get('zones'), list)) else 0
                    tasks.append(t_item)
                return tasks
            except Exception as e:
                if attempt == 0:
                    raw_c = ensure_connection_alive(cursor)
                    if raw_c and hasattr(raw_c, 'cursor'):
                        try:
                            cursor = raw_c.cursor()
                        except Exception:
                            pass
                    continue
                _log.error("Lỗi get_tasks_by_camera (camera_id=%s, model_id=%s): %s", camera_id, model_id, e)
                return []
        return []


def get_task_by_id(cursor, task_id: int) -> Optional[Dict[str, Any]]:
    """Lấy thông tin chi tiết đầy đủ của 1 task theo ID từ database."""
    if not cursor:
        return None
    with _db_lock:
        cur = get_active_cursor(cursor)
        for attempt in range(2):
            try:
                has_val_state = True
                try:
                    query = """
                        SELECT id, camera_id, model_id, task_name, task_type, logic_mode, 
                               action_on_fail, enabled, assign_register, value_bit_on, 
                               value_bit_off, datetime, value_state
                        FROM task_calculator
                        WHERE id = %s
                    """
                    cur.execute(query, (task_id,))
                except Exception:
                    query = """
                        SELECT id, camera_id, model_id, task_name, task_type, logic_mode, 
                               action_on_fail, enabled, assign_register, value_bit_on, 
                               value_bit_off, datetime
                        FROM task_calculator
                        WHERE id = %s
                    """
                    cur.execute(query, (task_id,))
                    has_val_state = False

                r = cur.fetchone()
                if not r:
                    return None
                v_state = r[12] if (has_val_state and len(r) > 12 and r[12] is not None) else 1
                v_on = r[9] if r[9] is not None else 1
                v_off = r[10] if r[10] is not None else 0
                res_task = {
                    'id': r[0],
                    'camera_id': r[1],
                    'model_id': r[2],
                    'task_name': r[3],
                    'task_type': r[4],
                    'logic_mode': r[5],
                    'action_on_fail': r[6],
                    'enabled': bool(r[7]),
                    'assign_register': r[8] or '',
                    'value_state': v_state,
                    'Value_State': v_state,
                    'value_bit_on': v_on,
                    'value_ok': v_on,
                    'Value_OK': v_on,
                    'value_bit_off': v_off,
                    'value_ng': v_off,
                    'Value_NG': v_off,
                    'datetime': r[11]
                }
                if res_task.get('task_type') == 'MULTI_SHOT_AGGREGATION':
                    res_task['multishot_rule'] = get_multishot_rule(cur, task_id)
                elif res_task.get('task_type') == 'ROI_ZONE_INSPECTION':
                    res_task['roi_rule'] = get_roi_rule(cur, task_id)
                return res_task
            except Exception as e:
                if attempt == 0:
                    raw_c = ensure_connection_alive(cursor)
                    if raw_c and hasattr(raw_c, 'cursor'):
                        try:
                            cur = raw_c.cursor()
                        except Exception:
                            pass
                    continue
                _log.error("Lỗi get_task_by_id (task_id=%s): %s", task_id, e)
                return None
        return None


def get_task_rules(cursor, task_id: int) -> List[Dict[str, Any]]:
    """Lấy danh sách các rule của 1 task."""
    if not cursor:
        return []
    with _db_lock:
        cur = get_active_cursor(cursor)
        for attempt in range(2):
            try:
                try:
                    query = """
                        SELECT id, task_id, rule_name, label_1, param_1, instance_select_1,
                               operator, target_type, label_2, param_2, instance_select_2,
                               math_op, math_operand_type, math_operand_val, min_value, max_value,
                               condition_true_result, enabled, description, instance_scope, box1_rect, box2_rect
                        FROM task_calculator_rules
                        WHERE task_id = %s
                        ORDER BY id ASC
                    """
                    cur.execute(query, (task_id,))
                except Exception:
                    query = """
                        SELECT id, task_id, rule_name, label_1, param_1, instance_select_1,
                               operator, target_type, label_2, param_2, instance_select_2,
                               math_op, math_operand_type, math_operand_val, min_value, max_value,
                               condition_true_result, enabled, description
                        FROM task_calculator_rules
                        WHERE task_id = %s
                        ORDER BY id ASC
                    """
                    cur.execute(query, (task_id,))

                rows = cur.fetchall()
                desc = [d[0] for d in cur.description] if cur.description else []
                rules = []
                for r in rows:
                    row_dict = dict(zip(desc, r))
                    rules.append({
                        'id': row_dict.get('id'),
                        'task_id': row_dict.get('task_id'),
                        'rule_name': row_dict.get('rule_name') or '',
                        'label_1': row_dict.get('label_1'),
                        'param_1': row_dict.get('param_1'),
                        'instance_select_1': row_dict.get('instance_select_1') or 'BEST_CONF',
                        'operator': row_dict.get('operator'),
                        'target_type': row_dict.get('target_type') or 'LABEL',
                        'label_2': row_dict.get('label_2') or '',
                        'param_2': row_dict.get('param_2') or '',
                        'instance_select_2': row_dict.get('instance_select_2') or 'BEST_CONF',
                        'math_op': row_dict.get('math_op') or 'NONE',
                        'math_operand_type': row_dict.get('math_operand_type') or 'CONSTANT',
                        'math_operand_val': str(row_dict.get('math_operand_val') if row_dict.get('math_operand_val') is not None else '0'),
                        'min_value': float(row_dict.get('min_value') or 0.0),
                        'max_value': float(row_dict.get('max_value') or 0.0),
                        'condition_true_result': row_dict.get('condition_true_result') or 'NG',
                        'enabled': bool(row_dict.get('enabled', 1)),
                        'description': row_dict.get('description') or '',
                        'instance_scope': row_dict.get('instance_scope') or '1_VS_1',
                        'box1_rect': row_dict.get('box1_rect') or '',
                        'box2_rect': row_dict.get('box2_rect') or '',
                    })
                return rules
            except Exception as e:
                if attempt == 0:
                    raw_c = ensure_connection_alive(cursor)
                    if raw_c and hasattr(raw_c, 'cursor'):
                        try:
                            cur = raw_c.cursor()
                        except Exception:
                            pass
                    continue
                _log.error("Lỗi get_task_rules (task_id=%s): %s", task_id, e)
                return []
        return []


def save_task_and_rules(cursor, connection, task_data: Dict[str, Any], rules: List[Dict[str, Any]]) -> Optional[int]:
    """
    Tạo mới hoặc cập nhật 1 Task cùng toàn bộ Rules của nó trong transaction an toàn.
    Trả về task_id nếu thành công, None nếu thất bại.
    """
    if not cursor or not connection:
        return None
    with _db_lock:
        ensure_connection_alive(cursor)
        cur = get_active_cursor(cursor)
        try:
            task_id = task_data.get('id')
            c_raw = task_data.get('camera_id', 1)
            c_str = str(c_raw).lower().replace('camera-', '').replace('built-in-', '').strip()
            camera_id = int(c_str) if c_str.isdigit() else 1
            
            m_raw = task_data.get('model_id', 1)
            m_str = str(m_raw).lower().replace('model-', '').replace('model', '').strip()
            model_id = int(m_str) if m_str.isdigit() else 1
            task_name = task_data.get('task_name', 'Task Mới')
            task_type = task_data.get('task_type', 'RELATION_COORDINATE')
            logic_mode = task_data.get('logic_mode', 'ALL_PASS')
            action_on_fail = task_data.get('action_on_fail', 'NG')
            enabled = 1 if task_data.get('enabled', True) else 0
            assign_register = task_data.get('assign_register', '').strip()
            val_state = int(task_data.get('value_state', task_data.get('Value_State', 1)))
            value_bit_on = int(task_data.get('value_bit_on', task_data.get('value_ok', task_data.get('Value_OK', 1))))
            value_bit_off = int(task_data.get('value_bit_off', task_data.get('value_ng', task_data.get('Value_NG', 0))))

            # Đảm bảo cột value_state tồn tại
            cur.execute("SHOW COLUMNS FROM task_calculator LIKE 'value_state'")
            if not cur.fetchone():
                cur.execute("SHOW COLUMNS FROM task_calculator LIKE 'Value_State'")
                if not cur.fetchone():
                    cur.execute("ALTER TABLE task_calculator ADD COLUMN value_state INT DEFAULT 1 AFTER assign_register")

            if task_id:
                # Update Task
                cur.execute("""
                    UPDATE task_calculator
                    SET task_name = %s, task_type = %s, logic_mode = %s, action_on_fail = %s,
                        enabled = %s, assign_register = %s, value_state = %s, value_bit_on = %s, value_bit_off = %s,
                        model_id = %s
                    WHERE id = %s AND camera_id = %s
                """, (task_name, task_type, logic_mode, action_on_fail, enabled,
                      assign_register, val_state, value_bit_on, value_bit_off, model_id, task_id, camera_id))
                
                # Xóa các rules cũ để ghi lại danh sách mới
                cur.execute("DELETE FROM task_calculator_rules WHERE task_id = %s", (task_id,))
            else:
                # Insert Task
                cur.execute("""
                    INSERT INTO task_calculator
                    (camera_id, model_id, task_name, task_type, logic_mode, action_on_fail, enabled,
                     assign_register, value_state, value_bit_on, value_bit_off)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (camera_id, model_id, task_name, task_type, logic_mode, action_on_fail, enabled,
                      assign_register, val_state, value_bit_on, value_bit_off))
                task_id = cur.lastrowid

            # Đảm bảo cột instance_scope tồn tại
            cur.execute("SHOW COLUMNS FROM task_calculator_rules LIKE 'instance_scope'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE task_calculator_rules ADD COLUMN instance_scope VARCHAR(50) NOT NULL DEFAULT '1_VS_1' AFTER instance_select_1")

            # Đảm bảo cột box1_rect, box2_rect tồn tại
            cur.execute("SHOW COLUMNS FROM task_calculator_rules LIKE 'box1_rect'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE task_calculator_rules ADD COLUMN box1_rect VARCHAR(100) DEFAULT ''")

            cur.execute("SHOW COLUMNS FROM task_calculator_rules LIKE 'box2_rect'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE task_calculator_rules ADD COLUMN box2_rect VARCHAR(100) DEFAULT ''")

            # Insert các Rules
            for r in rules:
                cur.execute("""
                    INSERT INTO task_calculator_rules
                    (task_id, rule_name, label_1, param_1, instance_select_1, instance_scope,
                     operator, target_type, label_2, param_2, instance_select_2,
                     math_op, math_operand_type, math_operand_val, min_value, max_value,
                     condition_true_result, enabled, description, box1_rect, box2_rect)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    task_id,
                    r.get('rule_name', ''),
                    r['label_1'],
                    r['param_1'],
                    r.get('instance_select_1', 'BEST_CONF'),
                    r.get('instance_scope', '1_VS_1'),
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
                    r.get('description', ''),
                    str(r.get('box1_rect', '') or ''),
                    str(r.get('box2_rect', '') or '')
                ))

            safe_commit(connection)
            _log.info("Saved Task id=%s (%s rules) for camera_id=%s, model_id=%s", task_id, len(rules), camera_id, model_id)
            return task_id
        except Exception as e:
            _log.error("Error saving Task and Rules: %s", e)
            safe_rollback(connection)
            return None


def get_multishot_rule(cursor, task_id: int) -> Optional[Dict[str, Any]]:
    """Lấy cấu hình chi tiết của multi-shot rule theo task_id."""
    if not cursor:
        return None
    with _db_lock:
        cur = get_active_cursor(cursor)
        for attempt in range(2):
            try:
                try:
                    cur.execute("""
                        SELECT id, task_id, target_label, cycle_shots, aggregation_mode,
                               min_ng_shots, specific_shots, roi_enabled, roi_mode, roi_boxes,
                               timeout_reset_sec, description, participating_shots
                        FROM task_multishot_rules
                        WHERE task_id = %s
                        LIMIT 1
                    """, (task_id,))
                except Exception:
                    cur.execute("""
                        SELECT id, task_id, target_label, cycle_shots, aggregation_mode,
                               min_ng_shots, specific_shots, roi_enabled, roi_mode, roi_boxes,
                               timeout_reset_sec, description
                        FROM task_multishot_rules
                        WHERE task_id = %s
                        LIMIT 1
                    """, (task_id,))
                r = cur.fetchone()
                if not r:
                    return None
                desc = [d[0] for d in cur.description] if cur.description else []
                res = dict(zip(desc, r))
                return {
                    'id': res.get('id'),
                    'task_id': res.get('task_id'),
                    'target_label': res.get('target_label') or '',
                    'cycle_shots': int(res.get('cycle_shots') or 5),
                    'aggregation_mode': res.get('aggregation_mode') or 'THRESHOLD_COUNT',
                    'min_ng_shots': int(res.get('min_ng_shots') or 2),
                    'specific_shots': res.get('specific_shots') or '',
                    'participating_shots': res.get('participating_shots') or '',
                    'roi_enabled': bool(res.get('roi_enabled')),
                    'roi_mode': res.get('roi_mode') or 'IN_BOUNDS',
                    'roi_boxes': res.get('roi_boxes') or '',
                    'timeout_reset_sec': float(res.get('timeout_reset_sec') if res.get('timeout_reset_sec') is not None else 0.0),
                    'description': res.get('description') or ''
                }
            except Exception as e:
                if attempt == 0:
                    raw_c = ensure_connection_alive(cursor)
                    if raw_c and hasattr(raw_c, 'cursor'):
                        try:
                            cur = raw_c.cursor()
                        except Exception:
                            pass
                    continue
                _log.error("Lỗi get_multishot_rule (task_id=%s): %s", task_id, e)
                return None
        return None


def save_multishot_task_and_rule(cursor, connection, task_data: Dict[str, Any], rule_data: Dict[str, Any]) -> Optional[int]:
    """
    Tạo mới hoặc cập nhật 1 Task loại MULTI_SHOT_AGGREGATION cùng rule cấu hình liên ảnh của nó.
    Trả về task_id nếu thành công, None nếu thất bại.
    """
    if not cursor or not connection:
        return None
    with _db_lock:
        ensure_connection_alive(cursor)
        cur = get_active_cursor(cursor)
        try:
            task_id = task_data.get('id')
            c_raw = task_data.get('camera_id', 1)
            c_str = str(c_raw).lower().replace('camera-', '').replace('built-in-', '').strip()
            camera_id = int(c_str) if c_str.isdigit() else 1
            
            # Đối với MULTI_SHOT_AGGREGATION, task có phạm vi toàn Camera / toàn Chu kỳ (Liên Model).
            # Lưu model_id = 0 để biểu thị tác vụ áp dụng trên toàn bộ Model của Camera.
            model_id = 0
            task_name = task_data.get('task_name', 'Multi-Shot Task')
            task_type = 'MULTI_SHOT_AGGREGATION'
            logic_mode = task_data.get('logic_mode', 'ALL_PASS')
            action_on_fail = task_data.get('action_on_fail', 'NG')
            enabled = 1 if task_data.get('enabled', True) else 0
            assign_register = task_data.get('assign_register', '').strip()
            val_state = int(task_data.get('value_state', task_data.get('Value_State', 1)))
            value_bit_on = int(task_data.get('value_bit_on', task_data.get('value_ok', task_data.get('Value_OK', 1))))
            value_bit_off = int(task_data.get('value_bit_off', task_data.get('value_ng', task_data.get('Value_NG', 0))))

            ensure_task_calculator_tables(cursor, connection)

            if task_id:
                cur.execute("""
                    UPDATE task_calculator
                    SET task_name = %s, task_type = %s, logic_mode = %s, action_on_fail = %s,
                        enabled = %s, assign_register = %s, value_state = %s, value_bit_on = %s, value_bit_off = %s,
                        model_id = %s
                    WHERE id = %s AND camera_id = %s
                """, (task_name, task_type, logic_mode, action_on_fail, enabled,
                      assign_register, val_state, value_bit_on, value_bit_off, model_id, task_id, camera_id))
            else:
                cur.execute("""
                    INSERT INTO task_calculator
                    (camera_id, model_id, task_name, task_type, logic_mode, action_on_fail, enabled,
                     assign_register, value_state, value_bit_on, value_bit_off)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (camera_id, model_id, task_name, task_type, logic_mode, action_on_fail, enabled,
                      assign_register, val_state, value_bit_on, value_bit_off))
                task_id = cur.lastrowid

            cur.execute("SELECT id FROM task_multishot_rules WHERE task_id = %s", (task_id,))
            existing = cur.fetchone()

            target_label = rule_data.get('target_label', '').strip()
            cycle_shots = int(rule_data.get('cycle_shots', 5))
            agg_mode = rule_data.get('aggregation_mode', 'THRESHOLD_COUNT')
            min_ng_shots = int(rule_data.get('min_ng_shots', 2))
            specific_shots = str(rule_data.get('specific_shots', '') or '')
            participating_shots = str(rule_data.get('participating_shots', '') or '')
            roi_enabled = 1 if rule_data.get('roi_enabled') else 0
            roi_mode = rule_data.get('roi_mode', 'IN_BOUNDS')
            roi_boxes = str(rule_data.get('roi_boxes', '') or '')
            timeout_reset_sec = float(rule_data.get('timeout_reset_sec', 0.0) or 0.0)
            description = rule_data.get('description', '')

            # Đảm bảo cột participating_shots tồn tại
            try:
                cur.execute("SHOW COLUMNS FROM task_multishot_rules LIKE 'participating_shots'")
                if not cur.fetchone():
                    cur.execute("ALTER TABLE task_multishot_rules ADD COLUMN participating_shots VARCHAR(255) DEFAULT '' AFTER specific_shots")
            except Exception:
                pass

            if existing:
                try:
                    cur.execute("""
                        UPDATE task_multishot_rules
                        SET target_label = %s, cycle_shots = %s, aggregation_mode = %s,
                            min_ng_shots = %s, specific_shots = %s, participating_shots = %s,
                            roi_enabled = %s, roi_mode = %s, roi_boxes = %s, timeout_reset_sec = %s, description = %s
                        WHERE task_id = %s
                    """, (target_label, cycle_shots, agg_mode, min_ng_shots, specific_shots, participating_shots,
                          roi_enabled, roi_mode, roi_boxes, timeout_reset_sec, description, task_id))
                except Exception:
                    cur.execute("""
                        UPDATE task_multishot_rules
                        SET target_label = %s, cycle_shots = %s, aggregation_mode = %s,
                            min_ng_shots = %s, specific_shots = %s, roi_enabled = %s,
                            roi_mode = %s, roi_boxes = %s, timeout_reset_sec = %s, description = %s
                        WHERE task_id = %s
                    """, (target_label, cycle_shots, agg_mode, min_ng_shots, specific_shots,
                          roi_enabled, roi_mode, roi_boxes, timeout_reset_sec, description, task_id))
            else:
                try:
                    cur.execute("""
                        INSERT INTO task_multishot_rules
                        (task_id, target_label, cycle_shots, aggregation_mode, min_ng_shots,
                         specific_shots, participating_shots, roi_enabled, roi_mode, roi_boxes, timeout_reset_sec, description)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (task_id, target_label, cycle_shots, agg_mode, min_ng_shots,
                          specific_shots, participating_shots, roi_enabled, roi_mode, roi_boxes, timeout_reset_sec, description))
                except Exception:
                    cur.execute("""
                        INSERT INTO task_multishot_rules
                        (task_id, target_label, cycle_shots, aggregation_mode, min_ng_shots,
                         specific_shots, roi_enabled, roi_mode, roi_boxes, timeout_reset_sec, description)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (task_id, target_label, cycle_shots, agg_mode, min_ng_shots,
                          specific_shots, roi_enabled, roi_mode, roi_boxes, timeout_reset_sec, description))

            safe_commit(connection)
            _log.info("Saved MultiShot Task id=%s (label=%s, cycle=%s, min_ng=%s) for camera_id=%s (Camera-Wide Scope)",
                      task_id, target_label, cycle_shots, min_ng_shots, camera_id)
            return task_id
        except Exception as e:
            _log.error("Error saving MultiShot Task and Rule: %s", e)
            safe_rollback(connection)
            return None


def get_roi_rule(cursor, task_id: int) -> Optional[Dict[str, Any]]:
    """Lấy cấu hình chi tiết của ROI Zone rule theo task_id."""
    if not cursor:
        return None
    with _db_lock:
        cur = get_active_cursor(cursor)
        for attempt in range(2):
            try:
                cur.execute("""
                    SELECT id, task_id, zones_json, default_target, action_mode, description
                    FROM task_roi_rules
                    WHERE task_id = %s
                    LIMIT 1
                """, (task_id,))
                r = cur.fetchone()
                if not r:
                    return None
                desc = [d[0] for d in cur.description] if cur.description else []
                res = dict(zip(desc, r))
                import json
                zones_raw = res.get('zones_json') or '[]'
                try:
                    zones_list = json.loads(zones_raw) if isinstance(zones_raw, str) else (zones_raw or [])
                except Exception:
                    zones_list = []

                return {
                    'id': res.get('id'),
                    'task_id': res.get('task_id'),
                    'zones': zones_list,
                    'default_target': res.get('default_target') or '',
                    'action_mode': res.get('action_mode') or 'DEFECT_FILTER',
                    'description': res.get('description') or ''
                }
            except Exception as e:
                if attempt == 0:
                    raw_c = ensure_connection_alive(cursor)
                    if raw_c and hasattr(raw_c, 'cursor'):
                        try:
                            cur = raw_c.cursor()
                        except Exception:
                            pass
                    continue
                _log.error("Lỗi get_roi_rule (task_id=%s): %s", task_id, e)
                return None
        return None


def save_roi_task_and_rule(cursor, connection, task_data: Dict[str, Any], rule_data: Dict[str, Any]) -> Optional[int]:
    """
    Tạo mới hoặc cập nhật 1 Task loại ROI_ZONE_INSPECTION cùng danh sách các vùng ROI của nó.
    Phạm vi: ĐƠN MODEL (model_id cụ thể của tab Model hiện tại).
    """
    if not cursor or not connection:
        return None
    with _db_lock:
        ensure_connection_alive(cursor)
        cur = get_active_cursor(cursor)
        try:
            task_id = task_data.get('id')
            c_raw = task_data.get('camera_id', 1)
            c_str = str(c_raw).lower().replace('camera-', '').replace('built-in-', '').strip()
            camera_id = int(c_str) if c_str.isdigit() else 1

            m_raw = task_data.get('model_id', 1)
            m_str = str(m_raw).lower().replace('model-', '').replace('model', '').strip()
            model_id = int(m_str) if m_str.isdigit() else 1

            task_name = task_data.get('task_name', 'ROI Task')
            task_type = 'ROI_ZONE_INSPECTION'
            logic_mode = task_data.get('logic_mode', 'ALL_PASS')
            action_on_fail = task_data.get('action_on_fail', 'NG')
            enabled = 1 if task_data.get('enabled', True) else 0
            assign_register = task_data.get('assign_register', '').strip()
            val_state = int(task_data.get('value_state', task_data.get('Value_State', 1)))
            value_bit_on = int(task_data.get('value_bit_on', task_data.get('value_ok', task_data.get('Value_OK', 1))))
            value_bit_off = int(task_data.get('value_bit_off', task_data.get('value_ng', task_data.get('Value_NG', 0))))

            ensure_task_calculator_tables(cursor, connection)

            if task_id:
                cur.execute("""
                    UPDATE task_calculator
                    SET task_name = %s, task_type = %s, logic_mode = %s, action_on_fail = %s,
                        enabled = %s, assign_register = %s, value_state = %s, value_bit_on = %s, value_bit_off = %s,
                        model_id = %s
                    WHERE id = %s AND camera_id = %s
                """, (task_name, task_type, logic_mode, action_on_fail, enabled,
                      assign_register, val_state, value_bit_on, value_bit_off, model_id, task_id, camera_id))
            else:
                cur.execute("""
                    INSERT INTO task_calculator
                    (camera_id, model_id, task_name, task_type, logic_mode, action_on_fail, enabled,
                     assign_register, value_state, value_bit_on, value_bit_off)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (camera_id, model_id, task_name, task_type, logic_mode, action_on_fail, enabled,
                      assign_register, val_state, value_bit_on, value_bit_off))
                task_id = cur.lastrowid

            cur.execute("SELECT id FROM task_roi_rules WHERE task_id = %s", (task_id,))
            existing = cur.fetchone()

            import json
            zones_data = rule_data.get('zones', [])
            zones_json = json.dumps(zones_data, ensure_ascii=False) if not isinstance(zones_data, str) else zones_data
            default_target = str(rule_data.get('default_target') or '').strip()
            action_mode = str(rule_data.get('action_mode') or 'DEFECT_FILTER')
            description = str(rule_data.get('description') or '')

            if existing:
                cur.execute("""
                    UPDATE task_roi_rules
                    SET zones_json = %s, default_target = %s, action_mode = %s, description = %s
                    WHERE task_id = %s
                """, (zones_json, default_target, action_mode, description, task_id))
            else:
                cur.execute("""
                    INSERT INTO task_roi_rules
                    (task_id, zones_json, default_target, action_mode, description)
                    VALUES (%s, %s, %s, %s, %s)
                """, (task_id, zones_json, default_target, action_mode, description))

            safe_commit(connection)
            _log.info("Saved ROI Zone Task id=%s (%d zones) for camera_id=%s, model_id=%s (Model-Specific Scope)",
                      task_id, len(zones_data) if isinstance(zones_data, list) else 1, camera_id, model_id)
            return task_id
        except Exception as e:
            _log.error("Error saving ROI Task and Rule: %s", e)
            safe_rollback(connection)
            return None


def delete_task(cursor, connection, task_id: int) -> bool:
    """Xóa task và các rule con liên kết."""
    if not cursor or not connection:
        return False
    with _db_lock:
        ensure_connection_alive(cursor)
        cur = get_active_cursor(cursor)
        try:
            cur.execute("DELETE FROM task_roi_rules WHERE task_id = %s", (task_id,))
            cur.execute("DELETE FROM task_multishot_rules WHERE task_id = %s", (task_id,))
            cur.execute("DELETE FROM task_calculator_rules WHERE task_id = %s", (task_id,))
            cur.execute("DELETE FROM task_calculator WHERE id = %s", (task_id,))
            safe_commit(connection)
            _log.info("Deleted Task id=%s", task_id)
            return True
        except Exception as e:
            _log.error("Error deleting Task id=%s: %s", task_id, e)
            safe_rollback(connection)
            return False


def toggle_task_enabled(cursor, connection, task_id: int, enabled: bool) -> bool:
    """Bật/tắt nhanh 1 task."""
    if not cursor or not connection:
        return False
    with _db_lock:
        ensure_connection_alive(cursor)
        cur = get_active_cursor(cursor)
        try:
            cur.execute("UPDATE task_calculator SET enabled = %s WHERE id = %s", (1 if enabled else 0, task_id))
            safe_commit(connection)
            return True
        except Exception as e:
            _log.error("Lỗi khi toggle task id=%s: %s", task_id, e)
            safe_rollback(connection)
            return False


def get_available_labels_for_camera(cursor, camera_id: int, model_id: Optional[int] = None) -> List[str]:
    """
    Lấy danh sách các nhãn đã cấu hình trong bảng PARAMETERSET của model / camera này,
    phục vụ việc đổ dữ liệu vào combobox chọn nhãn.
    Nếu có model_id, chỉ lọc đúng các nhãn thuộc tab model đó.
    """
    if not cursor:
        return []
    with _db_lock:
        ensure_connection_alive(cursor)
        cur = get_active_cursor(cursor)
        try:
            # Chuẩn hóa camera_id sang int nếu có thể
            c_id = None
            if camera_id is not None:
                c_str = str(camera_id).lower().replace('camera-', '').replace('built-in-', '').strip()
                c_id = int(c_str) if c_str.isdigit() else camera_id

            # Chuẩn hóa model_id sang int nếu có thể
            m_id = None
            if model_id is not None:
                m_str = str(model_id).lower().replace('model-', '').replace('model', '').strip()
                m_id = int(m_str) if m_str.isdigit() else model_id

            if c_id is not None and m_id is not None:
                query = """
                    SELECT DISTINCT p.Label_Name
                    FROM PARAMETERSET p
                    JOIN NUMS_MODEL m ON p.model_id = m.id
                    WHERE (m.camera_id = %s OR m.camera_id = (SELECT id FROM NUMS_CAMERA WHERE nums_camera = %s LIMIT 1))
                      AND (m.nums_model = %s OR m.id = %s)
                    ORDER BY p.Label_Name ASC
                """
                cur.execute(query, (c_id, c_id, m_id, m_id))
            elif c_id is not None:
                query = """
                    SELECT DISTINCT p.Label_Name
                    FROM PARAMETERSET p
                    JOIN NUMS_MODEL m ON p.model_id = m.id
                    WHERE (m.camera_id = %s OR m.camera_id = (SELECT id FROM NUMS_CAMERA WHERE nums_camera = %s LIMIT 1))
                    ORDER BY p.Label_Name ASC
                """
                cur.execute(query, (c_id, c_id))
            else:
                return []
                
            rows = cur.fetchall()
            labels = [r[0] for r in rows if r[0] and str(r[0]).strip()]
            return labels
        except Exception as e:
            _log.error("Lỗi khi lấy danh sách nhãn của camera_id=%s, model_id=%s: %s", camera_id, model_id, e)
            return []


def get_cycle_shots_from_shotxmodel(cursor, camera_id: Any) -> int:
    """
    Lấy chính xác số lượng shot (ảnh) trong 1 chu kỳ từ bảng SHOTXMODEL (module_1/table_db.py).
    Tìm kiếm theo DEFAULT_MODE_AUTO và MODE_AUTO tương ứng với camera_id.
    """
    if not cursor:
        return 5
    with _db_lock:
        ensure_connection_alive(cursor)
        cur = get_active_cursor(cursor)
        try:
            c_str = str(camera_id).lower().replace('camera-', '').replace('built-in-', '').strip()
            c_id = int(c_str) if c_str.isdigit() else 1

            # 1. Tìm mode từ DEFAULT_MODE_AUTO và MODE_AUTO
            cur.execute("""
                SELECT COUNT(*), COALESCE(MAX(s.shot), 0)
                FROM SHOTXMODEL s
                JOIN MODE_AUTO m ON s.mode_id = m.id
                JOIN DEFAULT_MODE_AUTO d ON m.mode_name = d.mode_name AND m.camera_id = d.camera_id
                WHERE m.camera_id = %s
            """, (c_id,))
            row = cur.fetchone()
            if row and (row[0] > 0 or row[1] > 0):
                return max(int(row[0]), int(row[1]))

            # 2. Nếu không có DEFAULT_MODE_AUTO, lấy mode đầu tiên trong MODE_AUTO của camera
            cur.execute("""
                SELECT COUNT(*), COALESCE(MAX(s.shot), 0)
                FROM SHOTXMODEL s
                WHERE s.mode_id = (
                    SELECT id FROM MODE_AUTO WHERE camera_id = %s ORDER BY id ASC LIMIT 1
                )
            """, (c_id,))
            row = cur.fetchone()
            if row and (row[0] > 0 or row[1] > 0):
                return max(int(row[0]), int(row[1]))

            # 3. Quét toàn bộ SHOTXMODEL liên kết với camera_id qua MODE_AUTO
            cur.execute("""
                SELECT COUNT(*), COALESCE(MAX(s.shot), 0)
                FROM SHOTXMODEL s
                JOIN MODE_AUTO m ON s.mode_id = m.id
                WHERE m.camera_id = %s
            """, (c_id,))
            row = cur.fetchone()
            if row and (row[0] > 0 or row[1] > 0):
                return max(int(row[0]), int(row[1]))

            # 4. Fallback chung: Quét toàn bộ SHOTXMODEL hiện có
            cur.execute("SELECT COUNT(*), COALESCE(MAX(shot), 0) FROM SHOTXMODEL")
            row = cur.fetchone()
            if row and (row[0] > 0 or row[1] > 0):
                return max(int(row[0]), int(row[1]))

        except Exception as e:
            _log.warning("Không thể đọc số shot từ SHOTXMODEL (camera_id=%s): %s", camera_id, e)

        return 5
