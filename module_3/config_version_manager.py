"""
Module: config_version_manager.py
Mục đích: Engine lõi quản lý phiên bản cấu hình, ghi nhận Audit Trail biến động thiết định,
tính toán so sánh Diff trực quan (Cũ vs Mới) và khôi phục (Rollback) an toàn bằng CSDL MySQL.

Phạm vi giám sát 8 nhóm bảng:
1. Model & Bảng Nhãn: PARAMETERSET, WEIGHTS
2. Toán tử hình học: task_calculator, task_calculator_rules
3. PLC Settings: PLC_DATA, signal_timing_config, signal_transmission_and_reception, counter_shot_setup
4. Chế độ Auto: MODE_AUTO_SIGNAL, SHOTXMODEL
5. Cấu hình quang học: MIRROR_CONFIG
6. Cấu hình log ảnh: auto_logging
"""

import json
import copy
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from app_logger.app_logger import get_logger

_log = get_logger('module_3.config_version_manager')

SQL_CREATE_CONFIG_HISTORY = """
CREATE TABLE IF NOT EXISTS ADMINISTRATOR.CONFIG_HISTORY (
    id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
    scope_category      VARCHAR(50) NOT NULL,
    camera_id           VARCHAR(50) DEFAULT '',
    model_id            INT DEFAULT NULL,
    mode_id             INT DEFAULT NULL,
    version_tag         VARCHAR(100) DEFAULT '',
    change_reason       VARCHAR(255) NOT NULL,
    changed_by          VARCHAR(100) NOT NULL,
    user_role           VARCHAR(50) DEFAULT 'modify',
    is_golden           TINYINT(1) DEFAULT 0,
    diff_summary_json   LONGTEXT,
    full_config_json    LONGTEXT NOT NULL,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_category (scope_category),
    INDEX idx_cam_model (camera_id, model_id),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

SQL_CREATE_CONFIG_HISTORY_FALLBACK = """
CREATE TABLE IF NOT EXISTS CONFIG_HISTORY (
    id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
    scope_category      VARCHAR(50) NOT NULL,
    camera_id           VARCHAR(50) DEFAULT '',
    model_id            INT DEFAULT NULL,
    mode_id             INT DEFAULT NULL,
    version_tag         VARCHAR(100) DEFAULT '',
    change_reason       VARCHAR(255) NOT NULL,
    changed_by          VARCHAR(100) NOT NULL,
    user_role           VARCHAR(50) DEFAULT 'modify',
    is_golden           TINYINT(1) DEFAULT 0,
    diff_summary_json   LONGTEXT,
    full_config_json    LONGTEXT NOT NULL,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_category (scope_category),
    INDEX idx_cam_model (camera_id, model_id),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


def ensure_config_history_table(cursor, connection) -> bool:
    """Đảm bảo bảng CONFIG_HISTORY tồn tại."""
    try:
        try:
            cursor.execute(SQL_CREATE_CONFIG_HISTORY)
            if hasattr(cursor, 'fetchall'):
                try: cursor.fetchall()
                except Exception: pass
        except Exception:
            cursor.execute(SQL_CREATE_CONFIG_HISTORY_FALLBACK)
            if hasattr(cursor, 'fetchall'):
                try: cursor.fetchall()
                except Exception: pass
        if connection:
            connection.commit()
        return True
    except Exception as e:
        _log.error("Lỗi khi tạo bảng CONFIG_HISTORY: %s", e)
        return False


def _get_history_table_name(cursor) -> str:
    """Xác định tên bảng lịch sử có prefix ADMINISTRATOR hay không."""
    candidates = [
        "`ADMINISTRATOR`.`CONFIG_HISTORY`",
        "`administrator`.`config_history`",
        "`ADMINISTRATOR`.`config_history`",
        "`CONFIG_HISTORY`",
        "`config_history`"
    ]
    for cand in candidates:
        try:
            cursor.execute(f"SELECT 1 FROM {cand} LIMIT 1")
            cursor.fetchall()
            return cand
        except Exception:
            continue
    return "CONFIG_HISTORY"


# ─────────────────────────────────────────────────────────────────────────────
# 1. CÁC HÀM TRÍCH XUẤT CẤU HÌNH HIỆN TẠI (CAPTURE ENGINE)
# ─────────────────────────────────────────────────────────────────────────────

def capture_model_config(cursor, camera_id: Any, model_id: int) -> Dict[str, Any]:
    """Trích xuất toàn bộ cấu hình Model AI và Bảng nhãn PARAMETERSET."""
    data = {
        'weights': {},
        'parameterset': []
    }
    try:
        # 1. WEIGHTS
        cursor.execute("SELECT * FROM WEIGHTS WHERE model_id = %s LIMIT 1", (model_id,))
        desc = [d[0] for d in cursor.description] if cursor.description else []
        row = cursor.fetchone()
        if row and desc:
            data['weights'] = dict(zip(desc, row))

        # 2. PARAMETERSET
        cursor.execute("SELECT * FROM PARAMETERSET WHERE model_id = %s ORDER BY id ASC", (model_id,))
        desc_p = [d[0] for d in cursor.description] if cursor.description else []
        rows_p = cursor.fetchall()
        if rows_p and desc_p:
            data['parameterset'] = [dict(zip(desc_p, r)) for r in rows_p]
    except Exception as e:
        _log.error("Lỗi capture_model_config: %s", e)
    return data


def capture_task_calculator_config(cursor, camera_id: Any, model_id: int) -> Dict[str, Any]:
    """Trích xuất danh sách Task và Rules hình học."""
    data = {'tasks': []}
    try:
        from module_3.task_calculator_db import get_tasks_by_camera
        tasks = get_tasks_by_camera(cursor, camera_id, model_id=model_id)
        data['tasks'] = tasks or []
    except Exception as e:
        _log.error("Lỗi capture_task_calculator_config: %s", e)
    return data


def capture_plc_settings_config(cursor, camera_id: Any) -> Dict[str, Any]:
    """Trích xuất toàn bộ cấu hình PLC settings."""
    data = {
        'plc_data': [],
        'signal_timing_config': [],
        'signal_transmission_and_reception': [],
        'counter_shot_setup': []
    }
    try:
        c_clean = int(str(camera_id).lower().replace('camera-', '').replace('built-in-', '').strip()) if str(camera_id).isdigit() or any(c.isdigit() for c in str(camera_id)) else 1
    except Exception:
        c_clean = 1

    try:
        # PLC_DATA
        cursor.execute("SELECT * FROM PLC_DATA")
        desc = [d[0] for d in cursor.description] if cursor.description else []
        data['plc_data'] = [dict(zip(desc, r)) for r in cursor.fetchall()]

        # signal_timing_config
        cursor.execute("SELECT * FROM signal_timing_config WHERE camera_id = %s", (c_clean,))
        desc = [d[0] for d in cursor.description] if cursor.description else []
        data['signal_timing_config'] = [dict(zip(desc, r)) for r in cursor.fetchall()]

        # signal_transmission_and_reception
        cursor.execute("SELECT * FROM signal_transmission_and_reception WHERE camera_id = %s", (c_clean,))
        desc = [d[0] for d in cursor.description] if cursor.description else []
        data['signal_transmission_and_reception'] = [dict(zip(desc, r)) for r in cursor.fetchall()]

        # counter_shot_setup
        cursor.execute("SELECT * FROM counter_shot_setup WHERE camera_id = %s", (c_clean,))
        desc = [d[0] for d in cursor.description] if cursor.description else []
        data['counter_shot_setup'] = [dict(zip(desc, r)) for r in cursor.fetchall()]
    except Exception as e:
        _log.error("Lỗi capture_plc_settings_config: %s", e)
    return data


def capture_mode_auto_config(cursor, mode_id: int) -> Dict[str, Any]:
    """Trích xuất cấu hình MODE_AUTO_SIGNAL và SHOTXMODEL theo mode_id."""
    data = {
        'mode_auto_signal': [],
        'shotxmodel': []
    }
    try:
        # MODE_AUTO_SIGNAL
        cursor.execute("SELECT * FROM MODE_AUTO_SIGNAL WHERE mode_id = %s ORDER BY id ASC", (mode_id,))
        desc = [d[0] for d in cursor.description] if cursor.description else []
        data['mode_auto_signal'] = [dict(zip(desc, r)) for r in cursor.fetchall()]

        # SHOTXMODEL
        cursor.execute("SELECT * FROM SHOTXMODEL WHERE mode_id = %s ORDER BY shot ASC", (mode_id,))
        desc = [d[0] for d in cursor.description] if cursor.description else []
        data['shotxmodel'] = [dict(zip(desc, r)) for r in cursor.fetchall()]
    except Exception as e:
        _log.error("Lỗi capture_mode_auto_config: %s", e)
    return data


def capture_mirror_config(cursor, camera_id: Any) -> Dict[str, Any]:
    """Trích xuất MIRROR_CONFIG theo camera_id."""
    data = {'mirror_config': []}
    try:
        c_clean = int(str(camera_id).lower().replace('camera-', '').replace('built-in-', '').strip()) if any(c.isdigit() for c in str(camera_id)) else 1
        cursor.execute("""
            SELECT * FROM MIRROR_CONFIG 
            WHERE camera_id = %s OR camera_id IN (SELECT id FROM NUMS_CAMERA WHERE nums_camera = %s)
            ORDER BY id ASC
        """, (c_clean, str(camera_id)))
        desc = [d[0] for d in cursor.description] if cursor.description else []
        data['mirror_config'] = [dict(zip(desc, r)) for r in cursor.fetchall()]
    except Exception as e:
        _log.error("Lỗi capture_mirror_config: %s", e)
    return data


def capture_auto_logging_config(cursor, camera_id: Any) -> Dict[str, Any]:
    """Trích xuất auto_logging theo camera_id."""
    data = {'auto_logging': []}
    try:
        c_clean = int(str(camera_id).lower().replace('camera-', '').replace('built-in-', '').strip()) if any(c.isdigit() for c in str(camera_id)) else 1
        cursor.execute("""
            SELECT * FROM auto_logging 
            WHERE camera_id = %s OR camera_id IN (SELECT id FROM NUMS_CAMERA WHERE nums_camera = %s)
            ORDER BY id ASC
        """, (c_clean, str(camera_id)))
        desc = [d[0] for d in cursor.description] if cursor.description else []
        data['auto_logging'] = [dict(zip(desc, r)) for r in cursor.fetchall()]
    except Exception as e:
        _log.error("Lỗi capture_auto_logging_config: %s", e)
    return data


def capture_full_config(cursor, camera_id: Any = None, model_id: Optional[int] = None, mode_id: Optional[int] = None) -> Dict[str, Any]:
    """Gom toàn bộ dữ liệu cấu hình của tất cả các nhóm."""
    full = {
        'model_config': capture_model_config(cursor, camera_id, model_id) if model_id else {},
        'task_calculator': capture_task_calculator_config(cursor, camera_id, model_id) if (camera_id and model_id) else {},
        'plc_settings': capture_plc_settings_config(cursor, camera_id) if camera_id else {},
        'mode_auto': capture_mode_auto_config(cursor, mode_id) if mode_id else {},
        'mirror_config': capture_mirror_config(cursor, camera_id) if camera_id else {},
        'auto_logging': capture_auto_logging_config(cursor, camera_id) if camera_id else {}
    }
    return full


# ─────────────────────────────────────────────────────────────────────────────
# 2. THUẬT TOÁN TÍNH TOÁN SO SÁNH DIFF (CŨ VS MỚI)
# ─────────────────────────────────────────────────────────────────────────────

def _clean_val(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (int, float, str, bool)):
        return str(v).strip()
    return json.dumps(v, ensure_ascii=False)


def compute_diff(old_data: Dict[str, Any], new_data: Dict[str, Any], scope_category: str) -> List[Dict[str, Any]]:
    """
    So sánh chi tiết 2 bản cấu hình và trả về danh sách các điểm thay đổi.
    Mỗi phần tử: {
        'category': str,
        'item': str,
        'old_val': str,
        'new_val': str,
        'action': 'MODIFIED' | 'ADDED' | 'DELETED'
    }
    """
    diffs = []

    def _diff_dict(d_old: dict, d_new: dict, cat: str, prefix: str = ""):
        all_keys = set(d_old.keys()).union(set(d_new.keys()))
        for k in sorted(all_keys):
            if k in ('id', 'created_at', 'updated_at', 'model_id', 'camera_id', 'mode_id'):
                continue
            v_old = _clean_val(d_old.get(k))
            v_new = _clean_val(d_new.get(k))
            item_name = f"{prefix}{k}" if prefix else str(k)
            if k not in d_old:
                diffs.append({'category': cat, 'item': item_name, 'old_val': '(Trống)', 'new_val': v_new, 'action': 'ADDED'})
            elif k not in d_new:
                diffs.append({'category': cat, 'item': item_name, 'old_val': v_old, 'new_val': '(Bị xóa)', 'action': 'DELETED'})
            elif v_old != v_new:
                diffs.append({'category': cat, 'item': item_name, 'old_val': v_old, 'new_val': v_new, 'action': 'MODIFIED'})

    # 1. So sánh Model & Weights
    if 'weights' in old_data or 'weights' in new_data:
        _diff_dict(old_data.get('weights', {}), new_data.get('weights', {}), 'AI Model (WEIGHTS)')

    # 2. So sánh PARAMETERSET
    if 'parameterset' in old_data or 'parameterset' in new_data:
        old_params = {str(p.get('Label_Name') or p.get('id')): p for p in old_data.get('parameterset', [])}
        new_params = {str(p.get('Label_Name') or p.get('id')): p for p in new_data.get('parameterset', [])}
        for lbl in sorted(set(old_params.keys()).union(set(new_params.keys()))):
            if lbl not in old_params:
                diffs.append({'category': 'Bảng Nhãn (PARAMETERSET)', 'item': f"Nhãn mới: '{lbl}'", 'old_val': '(Chưa có)', 'new_val': 'Thêm mới', 'action': 'ADDED'})
            elif lbl not in new_params:
                diffs.append({'category': 'Bảng Nhãn (PARAMETERSET)', 'item': f"Nhãn: '{lbl}'", 'old_val': 'Tồn tại', 'new_val': '(Đã xóa)', 'action': 'DELETED'})
            else:
                _diff_dict(old_params[lbl], new_params[lbl], 'Bảng Nhãn (PARAMETERSET)', prefix=f"Nhãn '{lbl}' -> ")

    # 3. So sánh Task Calculator & Rules
    if 'tasks' in old_data or 'tasks' in new_data:
        old_tasks = {t.get('task_name', f"Task-{t.get('id')}"): t for t in old_data.get('tasks', [])}
        new_tasks = {t.get('task_name', f"Task-{t.get('id')}"): t for t in new_data.get('tasks', [])}
        for t_name in sorted(set(old_tasks.keys()).union(set(new_tasks.keys()))):
            if t_name not in old_tasks:
                diffs.append({'category': 'Task Calculator', 'item': f"Task mới: '{t_name}'", 'old_val': '(Chưa có)', 'new_val': 'Thêm mới', 'action': 'ADDED'})
            elif t_name not in new_tasks:
                diffs.append({'category': 'Task Calculator', 'item': f"Task: '{t_name}'", 'old_val': 'Tồn tại', 'new_val': '(Đã xóa)', 'action': 'DELETED'})
            else:
                t_old = old_tasks[t_name]
                t_new = new_tasks[t_name]
                for fld in ['task_type', 'logic_mode', 'assign_register', 'value_state', 'value_ok', 'value_ng', 'enabled']:
                    vo = _clean_val(t_old.get(fld))
                    vn = _clean_val(t_new.get(fld))
                    if vo != vn:
                        diffs.append({'category': 'Task Calculator', 'item': f"Task '{t_name}' -> {fld}", 'old_val': vo, 'new_val': vn, 'action': 'MODIFIED'})

                # So sánh Rules con trong Task
                r_old_list = t_old.get('rules', [])
                r_new_list = t_new.get('rules', [])
                r_old_desc = {r.get('description') or f"Rule-{i}": r for i, r in enumerate(r_old_list)}
                r_new_desc = {r.get('description') or f"Rule-{i}": r for i, r in enumerate(r_new_list)}
                for r_desc in sorted(set(r_old_desc.keys()).union(set(r_new_desc.keys()))):
                    if r_desc not in r_old_desc:
                        diffs.append({'category': 'Task Rules', 'item': f"Task '{t_name}' -> Thêm Rule: {r_desc}", 'old_val': '(Chưa có)', 'new_val': 'Thêm mới', 'action': 'ADDED'})
                    elif r_desc not in r_new_desc:
                        diffs.append({'category': 'Task Rules', 'item': f"Task '{t_name}' -> Xóa Rule: {r_desc}", 'old_val': r_desc, 'new_val': '(Đã xóa)', 'action': 'DELETED'})

    # 4. So sánh PLC Settings
    for plc_tbl in ['plc_data', 'signal_timing_config', 'signal_transmission_and_reception', 'counter_shot_setup']:
        if plc_tbl in old_data or plc_tbl in new_data:
            list_o = old_data.get(plc_tbl, [])
            list_n = new_data.get(plc_tbl, [])
            if _clean_val(list_o) != _clean_val(list_n):
                diffs.append({'category': 'PLC Settings', 'item': f"Bảng {plc_tbl}", 'old_val': f"{len(list_o)} dòng cấu hình", 'new_val': f"{len(list_n)} dòng cấu hình", 'action': 'MODIFIED'})

    # 5. So sánh Mode Auto & Shotxmodel
    if 'mode_auto_signal' in old_data or 'mode_auto_signal' in new_data:
        m_old = {s.get('signal_name', f"Sig-{s.get('id')}"): s for s in old_data.get('mode_auto_signal', [])}
        m_new = {s.get('signal_name', f"Sig-{s.get('id')}"): s for s in new_data.get('mode_auto_signal', [])}
        for s_name in sorted(set(m_old.keys()).union(set(m_new.keys()))):
            if s_name not in m_old:
                diffs.append({'category': 'Mode Auto Signal', 'item': f"Signal mới: '{s_name}'", 'old_val': '(Chưa có)', 'new_val': 'Thêm mới', 'action': 'ADDED'})
            elif s_name not in m_new:
                diffs.append({'category': 'Mode Auto Signal', 'item': f"Signal: '{s_name}'", 'old_val': 'Tồn tại', 'new_val': '(Đã xóa)', 'action': 'DELETED'})
            else:
                _diff_dict(m_old[s_name], m_new[s_name], 'Mode Auto Signal', prefix=f"Signal '{s_name}' -> ")

    if 'shotxmodel' in old_data or 'shotxmodel' in new_data:
        sh_o = {str(s.get('shot')): s for s in old_data.get('shotxmodel', [])}
        sh_n = {str(s.get('shot')): s for s in new_data.get('shotxmodel', [])}
        for s_k in sorted(set(sh_o.keys()).union(set(sh_n.keys()))):
            if s_k not in sh_o:
                diffs.append({'category': 'Shot x Model', 'item': f"Shot {s_k}", 'old_val': '(Chưa có)', 'new_val': f"Model {sh_n[s_k].get('no_of_model')}", 'action': 'ADDED'})
            elif s_k not in sh_n:
                diffs.append({'category': 'Shot x Model', 'item': f"Shot {s_k}", 'old_val': f"Model {sh_o[s_k].get('no_of_model')}", 'new_val': '(Đã xóa)', 'action': 'DELETED'})
            else:
                _diff_dict(sh_o[s_k], sh_n[s_k], 'Shot x Model', prefix=f"Shot {s_k} -> ")

    # 6. So sánh MIRROR_CONFIG
    if 'mirror_config' in old_data or 'mirror_config' in new_data:
        mir_o = {str(m.get('parameter_name') or m.get('id')): m for m in old_data.get('mirror_config', [])}
        mir_n = {str(m.get('parameter_name') or m.get('id')): m for m in new_data.get('mirror_config', [])}
        for m_k in sorted(set(mir_o.keys()).union(set(mir_n.keys()))):
            if m_k not in mir_o:
                diffs.append({'category': 'Mirror Config', 'item': f"Thông số: '{m_k}'", 'old_val': '(Chưa có)', 'new_val': 'Thêm mới', 'action': 'ADDED'})
            elif m_k not in mir_n:
                diffs.append({'category': 'Mirror Config', 'item': f"Thông số: '{m_k}'", 'old_val': 'Tồn tại', 'new_val': '(Đã xóa)', 'action': 'DELETED'})
            else:
                _diff_dict(mir_o[m_k], mir_n[m_k], 'Mirror Config', prefix=f"Gương '{m_k}' -> ")

    # 7. So sánh auto_logging
    if 'auto_logging' in old_data or 'auto_logging' in new_data:
        log_o = old_data.get('auto_logging', [])
        log_n = new_data.get('auto_logging', [])
        if _clean_val(log_o) != _clean_val(log_n):
            diffs.append({'category': 'Auto Logging', 'item': 'Cấu hình auto_logging', 'old_val': f"{len(log_o)} dòng", 'new_val': f"{len(log_n)} dòng", 'action': 'MODIFIED'})

    return diffs


# ─────────────────────────────────────────────────────────────────────────────
# 3. LƯU SNAPSHOT & AUDIT TRAIL
# ─────────────────────────────────────────────────────────────────────────────

def get_latest_snapshot(cursor, scope_category: str, camera_id: Any, model_id: Optional[int] = None, mode_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Lấy bản snapshot gần nhất để tính diff."""
    table_name = _get_history_table_name(cursor)
    try:
        sql = f"SELECT * FROM {table_name} WHERE scope_category = %s"
        params = [scope_category]
        if camera_id is not None and str(camera_id).strip() != '':
            sql += " AND camera_id = %s"
            params.append(str(camera_id).strip())
        if model_id is not None:
            sql += " AND model_id = %s"
            params.append(int(model_id))
        if mode_id is not None:
            sql += " AND mode_id = %s"
            params.append(int(mode_id))
        sql += " ORDER BY id DESC LIMIT 1"

        cursor.execute(sql, tuple(params))
        desc = [d[0] for d in cursor.description] if cursor.description else []
        row = cursor.fetchone()
        if row and desc:
            record = dict(zip(desc, row))
            if record.get('full_config_json'):
                try:
                    record['full_config'] = json.loads(record['full_config_json'])
                except Exception:
                    record['full_config'] = {}
            return record
    except Exception as e:
        _log.error("Lỗi get_latest_snapshot: %s", e)
    return None


def save_snapshot(
    cursor,
    connection,
    scope_category: str,
    change_reason: str,
    changed_by: str,
    camera_id: Any = '',
    model_id: Optional[int] = None,
    mode_id: Optional[int] = None,
    user_role: str = 'modify',
    is_golden: bool = False,
    custom_data: Optional[Dict[str, Any]] = None
) -> int:
    """
    Chụp toàn bộ cấu hình hiện tại, so sánh diff với bản trước đó và lưu vào CONFIG_HISTORY.
    Trả về ID bản ghi lịch sử mới tạo.
    """
    ensure_config_history_table(cursor, connection)
    table_name = _get_history_table_name(cursor)

    # 1. Trích xuất dữ liệu cấu hình mới nhất
    if custom_data is not None:
        new_data = custom_data
    else:
        if scope_category == 'MODEL_PARAMS' and model_id is not None:
            new_data = capture_model_config(cursor, camera_id, model_id)
        elif scope_category == 'TASK_RULES' and camera_id and model_id is not None:
            new_data = capture_task_calculator_config(cursor, camera_id, model_id)
        elif scope_category == 'PLC_SETTINGS' and camera_id:
            new_data = capture_plc_settings_config(cursor, camera_id)
        elif scope_category == 'MODE_AUTO' and mode_id is not None:
            new_data = capture_mode_auto_config(cursor, mode_id)
        elif scope_category == 'MIRROR_CONFIG' and camera_id:
            new_data = capture_mirror_config(cursor, camera_id)
        elif scope_category == 'AUTO_LOGGING' and camera_id:
            new_data = capture_auto_logging_config(cursor, camera_id)
        else:
            new_data = capture_full_config(cursor, camera_id, model_id, mode_id)

    # 2. Lấy bản cũ để tính diff
    latest_rec = get_latest_snapshot(cursor, scope_category, camera_id, model_id, mode_id)
    old_data = latest_rec.get('full_config', {}) if latest_rec else {}

    diff_list = compute_diff(old_data, new_data, scope_category)

    # Đóng gói JSON
    diff_json = json.dumps(diff_list, ensure_ascii=False)
    full_json = json.dumps(new_data, ensure_ascii=False)

    version_tag = f"v_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    sql = f"""
    INSERT INTO {table_name} (
        scope_category, camera_id, model_id, mode_id,
        version_tag, change_reason, changed_by, user_role,
        is_golden, diff_summary_json, full_config_json, created_at
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
    """
    params = (
        scope_category,
        str(camera_id or ''),
        int(model_id) if model_id is not None else None,
        int(mode_id) if mode_id is not None else None,
        version_tag,
        str(change_reason or '').strip() or 'Không ghi chú',
        str(changed_by or 'Unknown').strip(),
        str(user_role or 'modify').strip(),
        1 if is_golden else 0,
        diff_json,
        full_json
    )

    try:
        cursor.execute(sql, params)
        if connection:
            connection.commit()
        last_id = cursor.lastrowid
        _log.info("Lưu Snapshot thành công #%s (Category: %s, User: %s, Diff count: %d)", last_id, scope_category, changed_by, len(diff_list))
        return last_id
    except Exception as e:
        _log.error("Lỗi khi lưu Snapshot: %s", e)
        if connection:
            connection.rollback()
        return 0


# ─────────────────────────────────────────────────────────────────────────────
# 4. ENGINE KHÔI PHỤC (ROLLBACK) AN TOÀN
# ─────────────────────────────────────────────────────────────────────────────

def verify_user_can_rollback(cursor, username: str, raw_password: str) -> Tuple[bool, str]:
    """
    Xác thực quyền hạn và mật khẩu người dùng trước khi cho phép Rollback.
    Chỉ tài khoản full_control hoặc __ADMIN__ mới được phép.
    """
    u_clean = str(username or '').strip()
    if not u_clean:
        return False, "Chưa xác định danh tính người dùng!"

    if not raw_password:
        return False, "Mật khẩu không được để trống!"

    # 1. Quản trị viên Master __ADMIN__
    if u_clean == "__ADMIN__":
        try:
            from Administrator.user_db import verify_admin_password
            if verify_admin_password(raw_password):
                return True, "Xác thực thành công!"
            return False, "Mật khẩu Admin Master không chính xác!"
        except Exception as e:
            return False, f"Lỗi xác thực: {e}"

    # 2. Người dùng trong ADMINISTRATOR.ADMIN_USERS
    try:
        cursor.execute("SELECT password_hash, role, is_active FROM ADMINISTRATOR.ADMIN_USERS WHERE username = %s", (u_clean,))
        row = cursor.fetchone()
        if not row:
            return False, f"Tài khoản '{u_clean}' không tồn tại!"
        
        saved_hash, role, is_active = row
        if not is_active:
            return False, "Tài khoản đã bị vô hiệu hóa!"
        
        role_clean = str(role or '').strip().lower()
        if role_clean not in ('full_control', '__admin__'):
            return False, f"Tài khoản '{u_clean}' có quyền [{role_clean}], không có quyền 'full_control' để thực hiện Rollback!"

        from Administrator.user_db import verify_password
        if verify_password(raw_password, saved_hash):
            return True, "Xác thực thành công!"
        return False, "Mật khẩu người dùng không chính xác!"
    except Exception as e:
        _log.error("Lỗi kiểm tra quyền rollback: %s", e)
        return False, f"Lỗi cơ sở dữ liệu: {e}"


def rollback_snapshot(cursor, connection, snapshot_id: int, performed_by: str) -> Tuple[bool, str]:
    """
    Khôi phục 100% dữ liệu từ snapshot_id vào các bảng CSDL tương ứng.
    Tự động ghi 1 bản log Rollback sau khi hoàn tất.
    """
    table_name = _get_history_table_name(cursor)
    try:
        cursor.execute(f"SELECT * FROM {table_name} WHERE id = %s", (snapshot_id,))
        desc = [d[0] for d in cursor.description] if cursor.description else []
        row = cursor.fetchone()
        if not row:
            return False, f"Không tìm thấy bản Snapshot #{snapshot_id}!"

        rec = dict(zip(desc, row))
        scope_cat = rec.get('scope_category')
        camera_id = rec.get('camera_id')
        model_id = rec.get('model_id')
        mode_id = rec.get('mode_id')
        tag = rec.get('version_tag') or f"#{snapshot_id}"
        full_json = rec.get('full_config_json')
        if not full_json:
            return False, "Snapshot không có dữ liệu JSON!"

        cfg_data = json.loads(full_json)

        # ── 1. Khôi phục Model & Bảng Nhãn ──
        if 'weights' in cfg_data and cfg_data['weights']:
            w = cfg_data['weights']
            w_id = w.get('id')
            w_mid = w.get('model_id') or model_id
            if w_mid:
                cols_to_update = [k for k in w.keys() if k not in ('id', 'model_id')]
                if cols_to_update:
                    set_str = ", ".join([f"`{c}` = %s" for c in cols_to_update])
                    vals = [w[c] for c in cols_to_update]
                    vals.append(w_mid)
                    cursor.execute(f"UPDATE WEIGHTS SET {set_str} WHERE model_id = %s", tuple(vals))

        if 'parameterset' in cfg_data and model_id:
            cursor.execute("DELETE FROM PARAMETERSET WHERE model_id = %s", (model_id,))
            p_rows = cfg_data['parameterset']
            for p in p_rows:
                cols = list(p.keys())
                if cols:
                    col_str = ", ".join([f"`{c}`" for c in cols])
                    val_placeholders = ", ".join(["%s"] * len(cols))
                    vals = [p[c] for c in cols]
                    cursor.execute(f"INSERT INTO PARAMETERSET ({col_str}) VALUES ({val_placeholders})", tuple(vals))

        # ── 2. Khôi phục Task Calculator & Rules ──
        if 'tasks' in cfg_data and camera_id and model_id:
            from module_3.task_calculator_db import save_task_and_rules
            c_int = int(str(camera_id).lower().replace('camera-', '').replace('built-in-', '').strip()) if any(c.isdigit() for c in str(camera_id)) else 1
            # Xóa các task hiện tại của camera + model
            cursor.execute("SELECT id FROM task_calculator WHERE camera_id = %s AND model_id = %s", (c_int, model_id))
            old_task_ids = [r[0] for r in cursor.fetchall()]
            for otid in old_task_ids:
                cursor.execute("DELETE FROM task_calculator_rules WHERE task_id = %s", (otid,))
                cursor.execute("DELETE FROM task_calculator WHERE id = %s", (otid,))

            for t_item in cfg_data['tasks']:
                t_item_copy = copy.deepcopy(t_item)
                rules_copy = t_item_copy.pop('rules', [])
                t_item_copy.pop('id', None)
                t_item_copy['camera_id'] = c_int
                t_item_copy['model_id'] = model_id
                save_task_and_rules(cursor, connection, t_item_copy, rules_copy)

        # ── 3. Khôi phục Mode Auto Signal & Shotxmodel ──
        if 'mode_auto_signal' in cfg_data and mode_id:
            cursor.execute("DELETE FROM MODE_AUTO_SIGNAL WHERE mode_id = %s", (mode_id,))
            for s in cfg_data['mode_auto_signal']:
                cols = list(s.keys())
                if cols:
                    col_str = ", ".join([f"`{c}`" for c in cols])
                    placeholders = ", ".join(["%s"] * len(cols))
                    vals = [s[c] for c in cols]
                    cursor.execute(f"INSERT INTO MODE_AUTO_SIGNAL ({col_str}) VALUES ({placeholders})", tuple(vals))

        if 'shotxmodel' in cfg_data and mode_id:
            cursor.execute("DELETE FROM SHOTXMODEL WHERE mode_id = %s", (mode_id,))
            for sh in cfg_data['shotxmodel']:
                cols = list(sh.keys())
                if cols:
                    col_str = ", ".join([f"`{c}`" for c in cols])
                    placeholders = ", ".join(["%s"] * len(cols))
                    vals = [sh[c] for c in cols]
                    cursor.execute(f"INSERT INTO SHOTXMODEL ({col_str}) VALUES ({placeholders})", tuple(vals))

        # ── 4. Khôi phục MIRROR_CONFIG ──
        if 'mirror_config' in cfg_data and camera_id:
            c_int = int(str(camera_id).lower().replace('camera-', '').replace('built-in-', '').strip()) if any(c.isdigit() for c in str(camera_id)) else 1
            cursor.execute("DELETE FROM MIRROR_CONFIG WHERE camera_id = %s OR camera_id IN (SELECT id FROM NUMS_CAMERA WHERE nums_camera = %s)", (c_int, str(camera_id)))
            for m in cfg_data['mirror_config']:
                cols = list(m.keys())
                if cols:
                    col_str = ", ".join([f"`{c}`" for c in cols])
                    placeholders = ", ".join(["%s"] * len(cols))
                    vals = [m[c] for c in cols]
                    cursor.execute(f"INSERT INTO MIRROR_CONFIG ({col_str}) VALUES ({placeholders})", tuple(vals))

        # ── 5. Khôi phục auto_logging ──
        if 'auto_logging' in cfg_data and camera_id:
            c_int = int(str(camera_id).lower().replace('camera-', '').replace('built-in-', '').strip()) if any(c.isdigit() for c in str(camera_id)) else 1
            cursor.execute("DELETE FROM auto_logging WHERE camera_id = %s OR camera_id IN (SELECT id FROM NUMS_CAMERA WHERE nums_camera = %s)", (c_int, str(camera_id)))
            for a in cfg_data['auto_logging']:
                cols = list(a.keys())
                if cols:
                    col_str = ", ".join([f"`{c}`" for c in cols])
                    placeholders = ", ".join(["%s"] * len(cols))
                    vals = [a[c] for c in cols]
                    cursor.execute(f"INSERT INTO auto_logging ({col_str}) VALUES ({placeholders})", tuple(vals))

        # ── 6. Khôi phục PLC Settings ──
        if ('signal_timing_config' in cfg_data or 'signal_transmission_and_reception' in cfg_data or 'counter_shot_setup' in cfg_data) and camera_id:
            c_int = int(str(camera_id).lower().replace('camera-', '').replace('built-in-', '').strip()) if any(c.isdigit() for c in str(camera_id)) else 1
            if 'signal_timing_config' in cfg_data and cfg_data['signal_timing_config']:
                cursor.execute("DELETE FROM signal_timing_config WHERE camera_id = %s", (c_int,))
                for row_data in cfg_data['signal_timing_config']:
                    cols = list(row_data.keys())
                    if cols:
                        col_str = ", ".join([f"`{c}`" for c in cols])
                        placeholders = ", ".join(["%s"] * len(cols))
                        vals = [row_data[c] for c in cols]
                        cursor.execute(f"INSERT INTO signal_timing_config ({col_str}) VALUES ({placeholders})", tuple(vals))

            if 'signal_transmission_and_reception' in cfg_data and cfg_data['signal_transmission_and_reception']:
                cursor.execute("DELETE FROM signal_transmission_and_reception WHERE camera_id = %s", (c_int,))
                for row_data in cfg_data['signal_transmission_and_reception']:
                    cols = list(row_data.keys())
                    if cols:
                        col_str = ", ".join([f"`{c}`" for c in cols])
                        placeholders = ", ".join(["%s"] * len(cols))
                        vals = [row_data[c] for c in cols]
                        cursor.execute(f"INSERT INTO signal_transmission_and_reception ({col_str}) VALUES ({placeholders})", tuple(vals))

            if 'counter_shot_setup' in cfg_data and cfg_data['counter_shot_setup']:
                cursor.execute("DELETE FROM counter_shot_setup WHERE camera_id = %s", (c_int,))
                for row_data in cfg_data['counter_shot_setup']:
                    cols = list(row_data.keys())
                    if cols:
                        col_str = ", ".join([f"`{c}`" for c in cols])
                        placeholders = ", ".join(["%s"] * len(cols))
                        vals = [row_data[c] for c in cols]
                        cursor.execute(f"INSERT INTO counter_shot_setup ({col_str}) VALUES ({placeholders})", tuple(vals))

        if connection:
            connection.commit()

        # Tự động ghi 1 log sự kiện Rollback
        rollback_reason = f"↺ Khôi phục về phiên bản #{snapshot_id} [{tag}]"
        save_snapshot(
            cursor, connection,
            scope_category=scope_cat,
            change_reason=rollback_reason,
            changed_by=performed_by,
            camera_id=camera_id,
            model_id=model_id,
            mode_id=mode_id,
            user_role='full_control',
            is_golden=False,
            custom_data=cfg_data
        )

        return True, f"Khôi phục thành công toàn bộ cấu hình về phiên bản #{snapshot_id}!"
    except Exception as e:
        _log.error("Lỗi khi thực hiện Rollback: %s", e)
        if connection:
            connection.rollback()
        return False, f"Lỗi khôi phục cơ sở dữ liệu: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# 5. CÁC HÀM TRUY VẤN LỊCH SỬ & QUẢN LÝ BẢN CHUẨN (GOLDEN)
# ─────────────────────────────────────────────────────────────────────────────

def get_snapshot_by_id(cursor, snapshot_id: int) -> Optional[Dict[str, Any]]:
    """Lấy chi tiết 1 bản snapshot theo ID (bao gồm diff_list và full_config đã parse)."""
    table_name = _get_history_table_name(cursor)
    try:
        cursor.execute(f"SELECT * FROM {table_name} WHERE id = %s", (snapshot_id,))
        desc = [d[0] for d in cursor.description] if cursor.description else []
        row = cursor.fetchone()
        if row:
            rec = dict(zip(desc, row))
            try:
                rec['diff_list'] = json.loads(rec.get('diff_summary_json') or '[]')
            except Exception:
                rec['diff_list'] = []
            try:
                rec['full_config'] = json.loads(rec.get('full_config_json') or '{}')
            except Exception:
                rec['full_config'] = {}
            return rec
    except Exception as e:
        _log.error("Lỗi get_snapshot_by_id: %s", e)
    return None


def get_history_records(
    cursor,
    scope_category: Optional[str] = None,
    camera_id: Optional[str] = None,
    model_id: Optional[int] = None,
    only_golden: bool = False,
    limit: int = 150
) -> List[Dict[str, Any]]:
    """Lấy danh sách các mốc thay đổi theo bộ lọc."""
    table_name = _get_history_table_name(cursor)
    try:
        clauses = []
        params = []
        if scope_category and scope_category != 'ALL':
            clauses.append("scope_category = %s")
            params.append(scope_category)
        if camera_id and str(camera_id).strip() not in ('', 'ALL'):
            c_str = str(camera_id).strip()
            c_digits = ''.join(ch for ch in c_str if ch.isdigit())
            if c_digits and c_digits != c_str:
                clauses.append("(camera_id = %s OR camera_id = %s OR camera_id = '')")
                params.extend([c_str, c_digits])
            else:
                clauses.append("(camera_id = %s OR camera_id = '')")
                params.append(c_str)
        if model_id is not None:
            clauses.append("model_id = %s")
            params.append(int(model_id))
        if only_golden:
            clauses.append("is_golden = 1")

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
        SELECT id, scope_category, camera_id, model_id, mode_id, version_tag,
               change_reason, changed_by, user_role, is_golden, diff_summary_json, created_at
        FROM {table_name}
        {where_sql}
        ORDER BY id DESC
        LIMIT {int(limit)}
        """
        cursor.execute(sql, tuple(params))
        desc = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        results = []
        for r in rows:
            rec = dict(zip(desc, r))
            # Parse diff summary count
            diff_count = 0
            if rec.get('diff_summary_json'):
                try:
                    diff_arr = json.loads(rec['diff_summary_json'])
                    diff_count = len(diff_arr)
                    rec['diff_list'] = diff_arr
                except Exception:
                    rec['diff_list'] = []
            else:
                rec['diff_list'] = []
            rec['diff_count'] = diff_count
            results.append(rec)
        return results
    except Exception as e:
        _log.error("Lỗi get_history_records: %s", e, exc_info=True)
        import traceback
        traceback.print_exc()
        return []


def toggle_golden_status(cursor, connection, snapshot_id: int) -> Tuple[bool, bool, str]:
    """Bật/tắt trạng thái Bản chuẩn (Golden) của 1 snapshot."""
    table_name = _get_history_table_name(cursor)
    try:
        cursor.execute(f"SELECT is_golden FROM {table_name} WHERE id = %s", (snapshot_id,))
        row = cursor.fetchone()
        if not row:
            return False, False, "Không tìm thấy snapshot!"
        new_state = 0 if row[0] else 1
        cursor.execute(f"UPDATE {table_name} SET is_golden = %s WHERE id = %s", (new_state, snapshot_id))
        if connection:
            connection.commit()
        msg = "Đã đánh dấu là Bản Chuẩn (Golden Config)!" if new_state else "Đã bỏ đánh dấu Bản Chuẩn!"
        return True, bool(new_state), msg
    except Exception as e:
        _log.error("Lỗi toggle_golden_status: %s", e)
        if connection:
            connection.rollback()
        return False, False, str(e)
