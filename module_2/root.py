import sys,os
from pathlib import Path

# Đảm bảo đường dẫn đến project_root nằm đầu sys.path
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent  # → lên 1 cấp từ /base/
sys.path.insert(0, str(project_root))  # thêm project_root vào đầu sys.path

# # Kiểm tra thử
# import ultralytics
# print(f"[DEBUG] ultralytics imported from: {ultralytics.__file__}")