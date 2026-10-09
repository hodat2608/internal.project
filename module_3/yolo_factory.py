# from pathlib import Path
# import os
# import sys

# # Thêm đường dẫn chứa ultralytics vào sys.path để các file bên trong ultralytics gọi được nhau
# _ultra_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '_source', 'v8', 'ultralytics'))
# if _ultra_path not in sys.path:
#     sys.path.insert(0, _ultra_path)

# from ultralytics import YOLO
# from _source.v5.v5 import v5s
# from module_1.root_path import resource_path
# from app_logger.app_logger import get_logger

# _log = get_logger('module_3.yolo_factory')

# class YoloFactory:
#     """
#     Factory class để xử lý khởi tạo (load) các phiên bản YOLO khác nhau (V5, V8, V11, V26...)
#     và các framework (PyTorch, TensorRT...) cũng như các task (Normal Box, Segmentation...).
#     Giúp module chính (ultils.py) gọn gàng và dễ dàng mở rộng, bảo trì trong tương lai.
#     """
    
#     @staticmethod
#     def load_model(source: str, task: str, model_runtime: str, weight_path: str, device: str) -> dict:
#         """
#         Load model dựa trên các tham số cấu hình.
#         Returns: 
#             dict chứa 'model_loader', 'result_model', 'path_object', và trạng thái 'success'.
#         """
#         result = {
#             "model_loader": None,
#             "result_model": None,
#             "path_object": None,
#             "success": False,
#             "error_msg": ""
#         }
        
#         try:
#             if source == 'Yolo V8':
#                 YoloFactory._load_v8(task, model_runtime, weight_path, device, result)
                
#             elif source == 'Yolo V5':
#                 YoloFactory._load_v5(task, model_runtime, weight_path, device, result)
                
#             elif source == 'Yolo V11':
#                 # Sẽ add mã xử lý sau
#                 pass
                
#             elif source == 'Yolo V26':
#                 # Sẽ add mã xử lý sau
#                 pass
            
#             else:
#                 result["error_msg"] = f"Nguồn model không được hỗ trợ: {source}"
                
#         except Exception as e:
#             result["error_msg"] = str(e)
#             _log.error(f"Lỗi khi load model {source} - {task}: {e}")
            
#         return result

#     @staticmethod
#     def _load_v8(task: str, model_runtime: str, weight_path: str, device: str, result: dict):
#         if task == 'Normal Box':
#             if model_runtime == 'PyTorch':
#                 result["path_object"] = Path(weight_path).parent
#                 result["model_loader"] = YOLO(model=weight_path, task='detect').to(device=device.split('-')[0])
#                 result["success"] = True
#                 _log.info("Load model Yolo V8 (Normal Box / PyTorch) successfully")
                
#             elif model_runtime == 'TensorRT':
#                 # Sẽ add mã xử lý sau
#                 pass
                
#         elif task == 'Segmentation':
#             # Sẽ add mã xử lý sau
#             pass
            
#         elif task == 'Rotation':
#             # Sẽ add mã xử lý sau
#             pass
            
#         elif task == 'Pose Estimation':
#             # Sẽ add mã xử lý sau
#             pass

#     @staticmethod
#     def _load_v5(task: str, model_runtime: str, weight_path: str, device: str, result: dict):
#         if task == 'Normal Box':
#             if model_runtime == 'PyTorch':
#                 try:
#                     result["path_object"] = Path(weight_path).parent
#                     result["result_model"] = v5s(weight_path, device)
#                     result["model_loader"] = result["result_model"].source_model
#                     result["success"] = True
#                     _log.info("Load model Yolo V5 (Normal Box / PyTorch) successfully from weight_path")
#                 except Exception as e:
#                     _log.warning(f"Lỗi load V5 từ weight_path ({weight_path}), fallback về best.pt: {e}")
#                     # Fallback
#                     fallback_path = resource_path('module_3/best.pt')
#                     result["path_object"] = Path(fallback_path).parent
#                     result["result_model"] = v5s(fallback_path, device)
#                     result["model_loader"] = result["result_model"].source_model
#                     result["success"] = True
#                     _log.info("Load model Yolo V5 (Normal Box / PyTorch) successfully from best.pt")
                    
#             elif model_runtime == 'TensorRT':
#                 # Sẽ add mã xử lý sau
#                 pass
                
#         elif task == 'Segmentation':
#             # Sẽ add mã xử lý sau
#             pass
            
#         elif task == 'Rotation':
#             # Sẽ add mã xử lý sau
#             pass
            
#         elif task == 'Pose Estimation':
#             # Sẽ add mã xử lý sau
#             pass


from pathlib import Path
import os
import sys

# Thêm đường dẫn chứa ultralytics vào sys.path để các file bên trong ultralytics gọi được nhau
_ultra_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '_source', 'v8', 'ultralytics'))
if _ultra_path not in sys.path:
    sys.path.insert(0, _ultra_path)

from ultralytics import YOLO
from _source.v5.v5 import v5s
from _source.v8.v8 import v8s
from module_1.root_path import resource_path
from app_logger.app_logger import get_logger

_log = get_logger('module_3.yolo_factory')

class YoloFactory:
    """
    Factory class để xử lý khởi tạo (load) các phiên bản YOLO khác nhau (V5, V8, V11, V26...)
    và các framework (PyTorch, TensorRT...) cũng như các task (Normal Box, Segmentation...).
    Giúp module chính (ultils.py) gọn gàng và dễ dàng mở rộng, bảo trì trong tương lai.
    """
    
    @staticmethod
    def load_model(source: str, task: str, model_runtime: str, weight_path: str, device: str) -> dict:
        """
        Load model dựa trên các tham số cấu hình.
        Returns: 
            dict chứa 'model_loader', 'result_model', 'path_object', và trạng thái 'success'.
        """
        result = {
            "model_loader": None,
            "result_model": None,
            "path_object": None,
            "success": False,
            "error_msg": ""
        }
        
        try:
            source = (source or '').strip()
            task = (task or '').strip()
            model_runtime = (model_runtime or '').strip()
            _alias = {'v5': 'Yolo V5', 'yolov5': 'Yolo V5', 'v8': 'Yolo V8', 'yolov8': 'Yolo V8'}
            source = _alias.get(source.lower(), source)
            _log.info(f"YoloFactory.load_model source={source!r} task={task!r} runtime={model_runtime!r} weight={weight_path!r} device={device!r}")

            if source == 'Yolo V8':
                YoloFactory._load_v8(task, model_runtime, weight_path, device, result)
                
            elif source == 'Yolo V5':
                YoloFactory._load_v5(task, model_runtime, weight_path, device, result)
                
            elif source == 'Yolo V11':
                # Sẽ add mã xử lý sau
                pass
                
            elif source == 'Yolo V26':
                # Sẽ add mã xử lý sau
                pass
            
            else:
                result["error_msg"] = f"Nguồn model không được hỗ trợ: {source}"
                
        except Exception as e:
            result["error_msg"] = str(e)
            _log.error(f"Lỗi khi load model {source} - {task}: {e}")

        if not result["success"] and not result["error_msg"]:
            result["error_msg"] = (f"Chưa hỗ trợ/không khớp cấu hình: source={source!r}, "
                                   f"task={task!r}, runtime={model_runtime!r}")
            
        return result

    @staticmethod
    def _load_v8(task: str, model_runtime: str, weight_path: str, device: str, result: dict):
        if task == 'Normal Box':
            if model_runtime == 'PyTorch':
                try:
                    result["path_object"] = Path(weight_path).parent
                    result["result_model"] = v8s(weight_path, device)
                    result["model_loader"] = result["result_model"].model
                    result["success"] = True
                    _log.info("Load model Yolo V8 (Normal Box / PyTorch) successfully from weight_path")
                except Exception as e:
                    _log.warning(f"Lỗi load V8 từ weight_path ({weight_path}), fallback về best.pt: {e}")
                    fallback_path = resource_path('module_3/best.pt')
                    result["path_object"] = Path(fallback_path).parent
                    result["result_model"] = v8s(fallback_path, device)
                    result["model_loader"] = result["result_model"].model
                    result["success"] = True
                    _log.info("Load model Yolo V8 (Normal Box / PyTorch) successfully from best.pt")
                
            elif model_runtime == 'TensorRT':
                # Sẽ add mã xử lý sau
                pass
                
        elif task == 'Segmentation':
            # Sẽ add mã xử lý sau
            pass
            
        elif task == 'Rotation':
            # Sẽ add mã xử lý sau
            pass
            
        elif task == 'Pose Estimation':
            # Sẽ add mã xử lý sau
            pass

    @staticmethod
    def _load_v5(task: str, model_runtime: str, weight_path: str, device: str, result: dict):
        if task == 'Normal Box':
            if model_runtime == 'PyTorch':
                try:
                    result["path_object"] = Path(weight_path).parent
                    result["result_model"] = v5s(weight_path, device)
                    result["model_loader"] = result["result_model"].source_model
                    result["success"] = True
                    _log.info("Load model Yolo V5 (Normal Box / PyTorch) successfully from weight_path")
                except Exception as e:
                    _log.warning(f"Lỗi load V5 từ weight_path ({weight_path}), fallback về best.pt: {e}")
                    # Fallback
                    fallback_path = resource_path('module_3/best.pt')
                    result["path_object"] = Path(fallback_path).parent
                    result["result_model"] = v5s(fallback_path, device)
                    result["model_loader"] = result["result_model"].source_model
                    result["success"] = True
                    _log.info("Load model Yolo V5 (Normal Box / PyTorch) successfully from best.pt")
                    
            elif model_runtime == 'TensorRT':
                # Sẽ add mã xử lý sau
                pass
                
        elif task == 'Segmentation':
            # Sẽ add mã xử lý sau
            pass
            
        elif task == 'Rotation':
            # Sẽ add mã xử lý sau
            pass
            
        elif task == 'Pose Estimation':
            # Sẽ add mã xử lý sau
            pass


