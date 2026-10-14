# -*- coding: utf-8 -*-
"""
config_status_logger.py
Module quản lý trạng thái thiết lập cấu hình PLC theo thời gian thực (Realtime Status Log).
Hiển thị danh sách các cấu hình theo thứ tự các bước:
1. Thiết lập mode auto (save_mode_auto)
2. Gán register item_code (save_register_name_line_code)
3. Lưu bảng tín hiệu PLC (save_values_signal_to_db_from_gui)
4. Lưu bảng shot x model (save_shotxmodel_to_db)
5. Lưu truyền nhận tín hiệu & timing (save_all_data)
6. Thiết lập counter shot (setup_counter_shot)
7. Thiết lập mapping mode (save_mapping_mode)
8. Lưu userset camera cho mode (query_mode_id_to_user_index)
"""

import time
from app_logger.app_logger import get_logger as _get_logger

_log = _get_logger('module_3.config_status_logger')


class PLCConfigStatusLogger:
    STEPS = [
        {
            'id': 'mode_auto',
            'order': 1,
            'name': 'Thiết lập Mode Auto',
            'default_msg': 'Chưa nhấn lưu mode',
        },
        {
            'id': 'item_code',
            'order': 2,
            'name': 'Lưu Register Item Code',
            'default_msg': 'Chưa nhấn lưu mã hàng',
        },
        {
            'id': 'signal_table',
            'order': 3,
            'name': 'Lưu Bảng Tín Hiệu PLC',
            'default_msg': 'Chưa nhấn lưu bảng tín hiệu',
        },
        {
            'id': 'shot_model',
            'order': 4,
            'name': 'Lưu Bảng Shot x Model',
            'default_msg': 'Chưa nhấn lưu bảng Shot x Model',
        },
        {
            'id': 'transmission_timing',
            'order': 5,
            'name': 'Lưu Truyền Nhận & Timing',
            'default_msg': 'Chưa nhấn lưu cấu hình truyền nhận & timing',
        },
        {
            'id': 'counter_shot',
            'order': 6,
            'name': 'Thiết lập Counter Shot',
            'default_msg': 'Chưa nhấn lưu thiết lập Counter Shot',
        },
        {
            'id': 'mapping_mode',
            'order': 7,
            'name': 'Thiết lập Mapping Mode',
            'default_msg': 'Chưa nhấn lưu thiết lập Mapping Mode',
        },
        {
            'id': 'userset_camera',
            'order': 8,
            'name': 'Lưu UserSet Camera Cho Mode',
            'default_msg': 'Chưa nhấn lưu UserSet cho mode',
        },
    ]

    def __init__(self, text_widget=None):
        self.text_widget = text_widget
        self.status = {}
        self.reset_all_pending()

    def reset_all_pending(self):
        """Khởi tạo toàn bộ các bước ở trạng thái chưa lưu (pending)."""
        for step in self.STEPS:
            self.status[step['id']] = {
                'state': 'pending',
                'message': step['default_msg'],
                'updated_at': ''
            }
        self.render()

    def set_status(self, step_id: str, state: str, message: str = None):
        """
        Cập nhật trạng thái của một bước:
        state: 'pending' (chưa lưu) | 'success' (lưu thành công) | 'error' (lỗi khi lưu)
        """
        step_meta = next((s for s in self.STEPS if s['id'] == step_id), None)
        if not step_meta:
            _log.warning(f"[PLCConfigStatusLogger] Không tìm thấy step_id: {step_id}")
            return

        ts = time.strftime("%H:%M:%S")
        if message is None:
            if state == 'success':
                message = f"Đã lưu thành công"
            elif state == 'error':
                message = f"Lỗi trong quá trình lưu"
            else:
                message = step_meta['default_msg']

        self.status[step_id] = {
            'state': state,
            'message': message,
            'updated_at': ts
        }
        self.render()

    def check_initial_db(self, cursor, camera_id, item_code_id, mode_name, item_code):
        """
        Quét nhanh database để xác định trạng thái thực tế hiện có trong CSDL:
        Nếu đã có bản ghi -> đánh dấu 'success' (đã lưu).
        Nếu chưa có -> đánh dấu 'pending' (chưa nhấn lưu).
        """
        try:
            # 1. Mode Auto
            cursor.execute("""
                SELECT id FROM MODE_AUTO 
                WHERE camera_id = %s AND mode_name = %s
            """, (camera_id, mode_name))
            row = cursor.fetchone()
            mode_id = row[0] if row else None
            if mode_id:
                self.status['mode_auto'] = {
                    'state': 'success',
                    'message': f"Đã lưu thành công Mode '{mode_name}'",
                    'updated_at': 'CSDL'
                }
            else:
                self.status['mode_auto'] = {
                    'state': 'pending',
                    'message': f"Chưa nhấn lưu Mode '{mode_name}'",
                    'updated_at': ''
                }

            # 2. Item Code
            cursor.execute("""
                SELECT assign_register FROM ITEMS_CODE 
                WHERE name_line_code = %s
            """, (item_code,))
            row_ic = cursor.fetchone()
            if row_ic and row_ic[0]:
                self.status['item_code'] = {
                    'state': 'success',
                    'message': f"Đã lưu thành công mã hàng '{item_code}' (Reg: {row_ic[0]})",
                    'updated_at': 'CSDL'
                }
            else:
                self.status['item_code'] = {
                    'state': 'pending',
                    'message': f"Chưa nhấn lưu mã hàng '{item_code}'",
                    'updated_at': ''
                }

            # 3. Signal Table (liên kết với mode_id)
            if mode_id:
                cursor.execute("SELECT COUNT(*) FROM MODE_AUTO_SIGNAL WHERE mode_id = %s", (mode_id,))
                cnt_sig = cursor.fetchone()[0]
                if cnt_sig > 0:
                    self.status['signal_table'] = {
                        'state': 'success',
                        'message': f"Đã lưu thành công bảng tín hiệu ({cnt_sig} tín hiệu)",
                        'updated_at': 'CSDL'
                    }
                else:
                    self.status['signal_table'] = {
                        'state': 'pending',
                        'message': "Chưa nhấn lưu bảng tín hiệu",
                        'updated_at': ''
                    }
            else:
                self.status['signal_table'] = {
                    'state': 'pending',
                    'message': "Chưa nhấn lưu bảng tín hiệu (Cần lưu Mode trước)",
                    'updated_at': ''
                }

            # 4. Shot x Model (liên kết với mode_id)
            if mode_id:
                cursor.execute("SELECT COUNT(*) FROM SHOTXMODEL WHERE mode_id = %s", (mode_id,))
                cnt_sxm = cursor.fetchone()[0]
                if cnt_sxm > 0:
                    self.status['shot_model'] = {
                        'state': 'success',
                        'message': f"Đã lưu thành công bảng Shot x Model ({cnt_sxm} shot)",
                        'updated_at': 'CSDL'
                    }
                else:
                    self.status['shot_model'] = {
                        'state': 'pending',
                        'message': "Chưa nhấn lưu bảng Shot x Model",
                        'updated_at': ''
                    }
            else:
                self.status['shot_model'] = {
                    'state': 'pending',
                    'message': "Chưa nhấn lưu bảng Shot x Model (Cần lưu Mode trước)",
                    'updated_at': ''
                }

            # 5. Transmission & Timing
            cursor.execute("SELECT COUNT(*) FROM signal_transmission_and_reception WHERE camera_id = %s", (camera_id,))
            cnt_trans = cursor.fetchone()[0]
            if cnt_trans > 0:
                self.status['transmission_timing'] = {
                    'state': 'success',
                    'message': "Đã lưu thành công cấu hình truyền nhận & timing",
                    'updated_at': 'CSDL'
                }
            else:
                self.status['transmission_timing'] = {
                    'state': 'pending',
                    'message': "Chưa nhấn lưu cấu hình truyền nhận & timing",
                    'updated_at': ''
                }

            # 6. Counter Shot
            cursor.execute("SELECT COUNT(*) FROM counter_shot_setup WHERE camera_id = %s", (camera_id,))
            cnt_cntr = cursor.fetchone()[0]
            if cnt_cntr > 0:
                self.status['counter_shot'] = {
                    'state': 'success',
                    'message': "Đã lưu thành công thiết lập Counter Shot",
                    'updated_at': 'CSDL'
                }
            else:
                self.status['counter_shot'] = {
                    'state': 'pending',
                    'message': "Chưa nhấn lưu thiết lập Counter Shot",
                    'updated_at': ''
                }

            # 7. Mapping Mode
            cursor.execute("SELECT COUNT(*) FROM setup_mapping_mode WHERE camera_id = %s", (camera_id,))
            cnt_map = cursor.fetchone()[0]
            if cnt_map > 0:
                self.status['mapping_mode'] = {
                    'state': 'success',
                    'message': f"Đã lưu thành công thiết lập Mapping Mode ({cnt_map} modes)",
                    'updated_at': 'CSDL'
                }
            else:
                self.status['mapping_mode'] = {
                    'state': 'pending',
                    'message': "Chưa nhấn lưu thiết lập Mapping Mode",
                    'updated_at': ''
                }

            # 8. UserSet Camera (liên kết với mode_id)
            if mode_id:
                cursor.execute("SELECT user_set_selector FROM USER_SET_CAMERA WHERE mode_id = %s", (mode_id,))
                row_us = cursor.fetchone()
                if row_us:
                    self.status['userset_camera'] = {
                        'state': 'success',
                        'message': f"Đã lưu thành công UserSet camera ('{row_us[0]}') cho mode '{mode_name}'",
                        'updated_at': 'CSDL'
                    }
                else:
                    self.status['userset_camera'] = {
                        'state': 'pending',
                        'message': f"Chưa nhấn lưu UserSet camera cho mode '{mode_name}'",
                        'updated_at': ''
                    }
            else:
                self.status['userset_camera'] = {
                    'state': 'pending',
                    'message': f"Chưa nhấn lưu UserSet camera cho mode '{mode_name}'",
                    'updated_at': ''
                }

        except Exception as e:
            _log.error(f"[PLCConfigStatusLogger] Lỗi kiểm tra database ban đầu: {e}")

        self.render()

    def render(self):
        """Render giao diện HTML cho QTextBrowser."""
        if not self.text_widget:
            return

        html_lines = []
        html_lines.append(
            '<div style="font-family: \'Segoe UI\', Tahoma, Arial, sans-serif; font-size: 13px; line-height: 1.8;">'
        )

        success_count = 0
        total_count = len(self.STEPS)

        for step in self.STEPS:
            s_id = step['id']
            order = step['order']
            name = step['name']
            data = self.status.get(s_id, {'state': 'pending', 'message': step['default_msg'], 'updated_at': ''})
            state = data.get('state', 'pending')
            msg = data.get('message', step['default_msg'])
            ts = f" <span style='font-size: 11px; opacity: 0.8;'>[{data['updated_at']}]</span>" if data.get('updated_at') else ""

            if state == 'success':
                success_count += 1
                color = "#1E8E3E"  # Xanh lá cây
                html_lines.append(
                    f'<div style="color: {color}; margin: 4px 0; font-weight: 600;">'
                    f'- Bước {order} ({name}): {msg}{ts}'
                    f'</div>'
                )
            elif state == 'error':
                color = "#D93025"  # Đỏ
                html_lines.append(
                    f'<div style="color: {color}; margin: 4px 0; font-weight: 600;">'
                    f'- Bước {order} ({name}): [LỖI] {msg}{ts}'
                    f'</div>'
                )
            else:  # pending
                color = "#D93025"  # Đỏ (chưa lưu)
                html_lines.append(
                    f'<div style="color: {color}; margin: 4px 0; font-weight: 600;">'
                    f'- Bước {order} ({name}): {msg}'
                    f'</div>'
                )

        # Tổng kết tiến độ ở dưới
        html_lines.append("<hr style='border: 0; border-top: 1px solid #E0E0E0; margin: 10px 0;'>")
        if success_count == total_count:
            html_lines.append(
                f'<div style="color: #1E8E3E; font-weight: bold; font-size: 12px;">'
                f'✓ Đã hoàn tất toàn bộ cấu hình PLC ({success_count}/{total_count} bước thành công)!'
                f'</div>'
            )
        else:
            html_lines.append(
                f'<div style="color: #E37400; font-weight: bold; font-size: 12px;">'
                f'⚠ Tiến độ: {success_count}/{total_count} bước đã hoàn tất. Vui lòng thiết lập các mục chưa lưu (chữ màu đỏ).'
                f'</div>'
            )

        html_lines.append("</div>")

        self.text_widget.setHtml("".join(html_lines))
