
from PyQt5 import QtCore, QtGui, QtWidgets

class DataExport:
    def __init__(self,main_core_from_log, ui_data_export):
        self.connection = main_core_from_log
        self.ui_data_export = ui_data_export
        import os, datetime
        user_dumps = os.path.join(os.path.expanduser("~"), "Documents", "dumps")
        try: os.makedirs(user_dumps, exist_ok=True)
        except Exception: pass
        date_str = datetime.datetime.now().strftime("%Y%m%d")
        self.ui_data_export.editDumpProjectFolder.setText(os.path.join(user_dumps, f"Dump_{date_str}"))
        self.ui_data_export.editSelfContainedFile.setText(os.path.join(user_dumps, f"Dump_{date_str}.sql"))
        
        

    def on_schema_clicked(self, item, column):
        self.treeSchemaObjects = self.ui_data_export.treeSchemaObjects
        self.treeSchemaObjects.clear()
        
        db_name_str = item.data(0, QtCore.Qt.UserRole)
        if not db_name_str:
            return
            
        try:
            self.cursor = self.connection.cursor()
            self.cursor.execute(f"SELECT name_line_code FROM `{db_name_str}`.ITEMS_CODE")
            item_codes = self.cursor.fetchall()
            for code in item_codes:
                item_obj_table = QtWidgets.QTreeWidgetItem(self.treeSchemaObjects)
                item_obj_table.setText(0, f"📄 {code[0]}")
                item_obj_table.setCheckState(0, QtCore.Qt.Unchecked)
        except Exception as e:
            print(f"Error fetching item codes for {db_name_str}: {e}")


    def query_all_table(self):
        self.treeSchemas = self.ui_data_export.treeSchemas
        self.treeSchemas.clear()
        self.treeSchemaObjects = self.ui_data_export.treeSchemaObjects
        self.treeSchemaObjects.clear()
        
        self.cursor = self.connection.cursor()
        self.cursor.execute("SHOW DATABASES") 
        databases = self.cursor.fetchall()
        
        for db_name in databases:
            db_name_str = db_name[0]
            
            if db_name_str in ['information_schema', 'mysql', 'performance_schema', 'sys']:
                continue
                
            self.cursor.execute(f"SHOW TABLES IN `{db_name_str}`")
            tables = self.cursor.fetchall()
            
            has_items_code = False
            for table in tables:
                if 'items_code' == table[0].lower():
                    has_items_code = True
                    break
                    
            if has_items_code:
                db_item = QtWidgets.QTreeWidgetItem(self.treeSchemas)
                db_item.setText(0, f"💻 {db_name_str.upper()}")
                db_item.setCheckState(0, QtCore.Qt.Unchecked)
                db_item.setData(0, QtCore.Qt.UserRole, db_name_str)
                    
        self.treeSchemas.expandAll()

    def select_view(self, *args):
        selected_items = self.ui_data_export.treeSchemas.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            item.setCheckState(0, QtCore.Qt.Checked)

    def select_tables(self, *args):
        selected_items = self.ui_data_export.treeSchemaObjects.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            item.setCheckState(0, QtCore.Qt.Checked)

    def unselect_all(self, *args):
        selected_items = self.ui_data_export.treeSchemas.selectedItems()
        selected_tables = self.ui_data_export.treeSchemaObjects.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            item.setCheckState(0, QtCore.Qt.Unchecked)
        for item in selected_tables:
            item.setCheckState(0, QtCore.Qt.Unchecked)

    def browser_folder_export_data(self):
        folder_path = QtWidgets.QFileDialog.getExistingDirectory(None, "Chọn thư mục", "")
        if folder_path:
            self.ui_data_export.editDumpProjectFolder.setText(folder_path)
            self.ui_data_export.editDumpProjectFolder.setToolTip(folder_path)

    def export_data(self):
        import os
        from PyQt5 import QtWidgets, QtCore

        self.ui_data_export.tabWidget.setCurrentIndex(1)
        self.ui_data_export.txtProgressLog.clear()
        self.ui_data_export.progressBar.setValue(0)
        
        def log_msg(msg):
            self.ui_data_export.txtProgressLog.appendPlainText(msg)
            QtWidgets.QApplication.processEvents()

        log_msg("Bắt đầu chuẩn bị dữ liệu Export...")
        
        selected_dbs = []
        for i in range(self.ui_data_export.treeSchemas.topLevelItemCount()):
            item = self.ui_data_export.treeSchemas.topLevelItem(i)
            if item.checkState(0) == QtCore.Qt.Checked:
                db_name = item.data(0, QtCore.Qt.UserRole)
                if db_name: selected_dbs.append(db_name)
                    
        selected_item_codes = []
        for i in range(self.ui_data_export.treeSchemaObjects.topLevelItemCount()):
            item = self.ui_data_export.treeSchemaObjects.topLevelItem(i)
            if item.checkState(0) == QtCore.Qt.Checked:
                code = item.text(0).replace("📄 ", "")
                selected_item_codes.append(code)

        default_dbs = {
            'DATA_AUTO_LOGIN': ['INFOR'],
            'DATA_IP_ADDRESS': ['INFOR_ADDRESS'],
            'ITEM_CODE_SAVE': ['DATA_SAVE_DEFAULT'],
            'ADMINISTRATOR': ['ADMIN_USERS', 'HARDWARE_KEY_CONFIG']
        }
        
        dump_type = self.ui_data_export.cmbDumpType.currentIndex()
        inc_schema = self.ui_data_export.chkIncludeCreateSchema.isChecked()
        dump_procs = self.ui_data_export.chkDumpStoredProcedures.isChecked()
        dump_events = self.ui_data_export.chkDumpEvents.isChecked()
        dump_triggers = self.ui_data_export.chkDumpTriggers.isChecked()
        is_folder = self.ui_data_export.radioDumpProjectFolder.isChecked()
        
        target_path = self.ui_data_export.editDumpProjectFolder.text() if is_folder else self.ui_data_export.editSelfContainedFile.text()
        if not target_path:
            log_msg("Lỗi: Chưa chỉ định đường dẫn lưu!")
            return
            
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base_export_dir = ""
        
        if is_folder:
            base_export_dir = target_path
            target_path = os.path.join(base_export_dir, f"temp_sql_{timestamp}")
            os.makedirs(target_path, exist_ok=True)
        else:
            # Tạo thư mục chứa file đích nếu chưa có
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
        log_msg(f"Thư mục tạm thời xử lý SQL: {target_path}")
        
        all_export_tasks = []
        cursor = self.connection.cursor(dictionary=False)
        
        for db_name in selected_dbs:
            try:
                cursor.execute(f"SHOW TABLES IN `{db_name}`")
                tables = [t[0] for t in cursor.fetchall()]
                all_export_tasks.append((db_name, tables, False))
            except Exception as e:
                log_msg(f"Lỗi khi đọc DB {db_name}: {e}")
                
        for def_db, def_tables in default_dbs.items():
            all_export_tasks.append((def_db, def_tables, True))
            
        total_tasks = sum(len(tables) for _, tables, _ in all_export_tasks)
        if total_tasks == 0:
            log_msg("Không có table nào để export.")
            return

        def get_headers(db_name):
            # MySQL Workbench BẮT BUỘC phải có đoạn comment "Host: ... Database: ..." này để nhận diện file
            return f"""-- MySQL dump 10.13  Distrib 8.0.30, for Win64 (x86_64)
--
-- Host: 127.0.0.1    Database: {db_name}
-- ------------------------------------------------------
-- Server version	8.0.30

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
"""
        footers = """
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;
/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;
"""

        current_progress = 0
        single_f = None
        
        try:
            if not is_folder:
                single_f = open(target_path, 'w', encoding='utf-8')
                
            for db_name, tables, is_default in all_export_tasks:
                headers = get_headers(db_name)
                
                if not is_folder and single_f:
                    single_f.write(headers + "\n")
                    
                log_msg(f"--- Đang xử lý Database: {db_name} ---")
                    
                for tbl in tables:
                    log_msg(f" -> Đang export table: {tbl}")
                    tbl_buffer = []
                    if is_folder:
                        tbl_buffer.append(headers)
                        if inc_schema:
                            tbl_buffer.append(f"CREATE DATABASE IF NOT EXISTS `{db_name}`;\nUSE `{db_name}`;\n")
                    else:
                        if inc_schema:
                            tbl_buffer.append(f"CREATE DATABASE IF NOT EXISTS `{db_name}`;\nUSE `{db_name}`;\n")

                    try:
                        if dump_type in (0, 1): # Structure
                            tbl_buffer.append(f"--\n-- Table structure for table `{tbl}`\n--\n")
                            tbl_buffer.append(f"DROP TABLE IF EXISTS `{tbl}`;")
                            tbl_buffer.append("/*!40101 SET @saved_cs_client     = @@character_set_client */;")
                            tbl_buffer.append("/*!50503 SET character_set_client = utf8mb4 */;")
                            cursor.execute(f"SHOW CREATE TABLE `{db_name}`.`{tbl}`")
                            create_stmt = cursor.fetchone()[1]
                            tbl_buffer.append(f"{create_stmt};")
                            tbl_buffer.append("/*!40101 SET character_set_client = @saved_cs_client */;\n")
                            
                        if dump_type in (0, 2): # Data
                            tbl_buffer.append(f"--\n-- Dumping data for table `{tbl}`\n--\n")
                            tbl_buffer.append(f"LOCK TABLES `{tbl}` WRITE;")
                            tbl_buffer.append(f"/*!40000 ALTER TABLE `{tbl}` DISABLE KEYS */;")
                            
                            if tbl.lower() == 'items_code' and not is_default:
                                if selected_item_codes:
                                    placeholders = ','.join(['%s'] * len(selected_item_codes))
                                    query = f"SELECT * FROM `{db_name}`.`{tbl}` WHERE name_line_code IN ({placeholders})"
                                    cursor.execute(query, tuple(selected_item_codes))
                                else:
                                    cursor.execute(f"SELECT * FROM `{db_name}`.`{tbl}` WHERE 1=0")
                            else:
                                cursor.execute(f"SELECT * FROM `{db_name}`.`{tbl}`")
                                
                            rows = cursor.fetchall()
                            if rows:
                                for row in rows:
                                    val_strs = []
                                    for val in row:
                                        if val is None:
                                            val_strs.append("NULL")
                                        elif isinstance(val, (int, float)):
                                            val_strs.append(str(val))
                                        elif isinstance(val, (bytes, bytearray)):
                                            val_strs.append(f"X'{val.hex()}'")
                                        else:
                                            escaped = str(val).replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "\\r")
                                            val_strs.append(f"'{escaped}'")
                                            
                                    row_str = ", ".join(val_strs)
                                    tbl_buffer.append(f"INSERT INTO `{tbl}` VALUES ({row_str});")
                                    
                            tbl_buffer.append(f"/*!40000 ALTER TABLE `{tbl}` ENABLE KEYS */;")
                            tbl_buffer.append("UNLOCK TABLES;\n")
                            
                    except Exception as e:
                        log_msg(f"    Lỗi ở table {tbl}: {e}")
                        
                    if is_folder:
                        tbl_buffer.append(footers)
                        file_name = f"{db_name.lower()}_{tbl.lower()}.sql"
                        with open(os.path.join(target_path, file_name), 'w', encoding='utf-8') as f:
                            f.write("\n".join(tbl_buffer))
                    else:
                        single_f.write("\n".join(tbl_buffer) + "\n\n")
                        
                    current_progress += 1
                    self.ui_data_export.progressBar.setValue(int((current_progress / total_tasks) * 90))
                    QtWidgets.QApplication.processEvents()
                
                # Triggers & Procs -> routines file (Luôn xuất ra file này dù trống để Workbench nhận dạng file)
                routine_buf = []
                if is_folder:
                    routine_buf.append(headers)
                    routine_buf.append(f"--\n-- Dumping routines for database '{db_name}'\n--\n")
                    if inc_schema:
                        routine_buf.append(f"CREATE DATABASE IF NOT EXISTS `{db_name}`;\nUSE `{db_name}`;\n")

                if dump_triggers:
                    try:
                        cursor.execute("SHOW TRIGGERS")
                        for trig in cursor.fetchall():
                            cursor.execute(f"SHOW CREATE TRIGGER `{trig[0]}`")
                            res = cursor.fetchone()
                            if res: 
                                routine_buf.append(f"DELIMITER ;;\n{res[2]};;\nDELIMITER ;\n")
                    except Exception: pass
                    
                if dump_procs:
                    try:
                        cursor.execute(f"SHOW PROCEDURE STATUS WHERE Db = '{db_name}'")
                        for proc in cursor.fetchall():
                            cursor.execute(f"SHOW CREATE PROCEDURE `{proc[1]}`")
                            res = cursor.fetchone()
                            if res: 
                                routine_buf.append(f"DELIMITER ;;\n{res[2]};;\nDELIMITER ;\n")
                    except Exception: pass
                    
                if is_folder:
                    routine_buf.append(footers)
                    file_name = f"{db_name.lower()}_routines.sql"
                    with open(os.path.join(target_path, file_name), 'w', encoding='utf-8') as f:
                        f.write("\n".join(routine_buf))
                else:
                    single_f.write("\n".join(routine_buf) + "\n\n")
                    
            if single_f:
                if not is_folder:
                    single_f.write(footers + "\n")
                single_f.close()
                
            # === AUTO-ZIP FEATURE (BACKUP & RESTORE CAO CẤP) ===
            log_msg("\nĐang đóng gói CSDL và Model Weights thành file ZIP...")
            import zipfile, shutil, sys
            if getattr(sys, 'frozen', False):
                app_data = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or os.path.expanduser('~')
                BASE_DIR = os.path.join(app_data, 'MBC_Vision_Inspector')
            else:
                BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            weights_dir = os.path.join(BASE_DIR, 'workspace_weights')
            
            zip_path = ""
            if is_folder:
                zip_path = os.path.join(base_export_dir, f"VisionBackup_{timestamp}.zip")
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    # Gói SQL
                    for root, dirs, files in os.walk(target_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            zipf.write(file_path, arcname=f"database/{file}")
                    # Gói Weights
                    if os.path.exists(weights_dir):
                        for root, dirs, files in os.walk(weights_dir):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, start=weights_dir)
                                zipf.write(file_path, arcname=f"workspace_weights/{arcname}")
                # Dọn dẹp thư mục SQL tạm
                try: shutil.rmtree(target_path)
                except Exception: pass
            else:
                zip_path = target_path
                if zip_path.endswith('.sql'): zip_path = zip_path[:-4] + '.zip'
                else: zip_path += '.zip'
                
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    zipf.write(target_path, arcname=f"database/{os.path.basename(target_path)}")
                    if os.path.exists(weights_dir):
                        for root, dirs, files in os.walk(weights_dir):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, start=weights_dir)
                                zipf.write(file_path, arcname=f"workspace_weights/{arcname}")
                # Dọn file sql tạm
                if target_path != zip_path and os.path.exists(target_path):
                    try: os.remove(target_path)
                    except Exception: pass

            self.ui_data_export.progressBar.setValue(100)
            log_msg("\n==== HOÀN TẤT XUẤT DỮ LIỆU THÀNH CÔNG ====")
            QtWidgets.QMessageBox.information(None, "Thành công", f"Đã hoàn tất đóng gói dữ liệu tại:\n{zip_path}")
            
        except Exception as e:
            log_msg(f"\n[!] LỖI NGHIÊM TRỌNG: {e}")
            if single_f: single_f.close()

    def close_window(self):
        if hasattr(self.ui_data_export, 'tabWidget'):
            self.ui_data_export.tabWidget.window().close()


class DataImport():
    def __init__(self,main_core_from_log, ui_data_import):
        self.connection = main_core_from_log
        self.ui_data_import = ui_data_import
        self.import_db_map = {}
        import os
        user_dumps = os.path.join(os.path.expanduser("~"), "Documents", "dumps")
        try: os.makedirs(user_dumps, exist_ok=True)
        except Exception: pass
        self.ui_data_import.editDumpProjectFolder.setText(user_dumps)
        self.ui_data_import.editSelfContainedFile.setText(os.path.join(user_dumps, "export.sql"))
       
    def query_all_table(self):
        self.ui_data_import.treeSchemas.clear()
        self.ui_data_import.treeSchemaObjects.clear()

    def browser_folder_import_data(self):
        from PyQt5 import QtWidgets
        options = QtWidgets.QFileDialog.Options()
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            None,
            "Chọn file Backup (.zip)",
            "",
            "Backup ZIP (*.zip);;Thư mục / File cũ (*)",
            options=options
        )
        if file_path:
            self.ui_data_import.editDumpProjectFolder.setText(file_path)
            self.ui_data_import.editDumpProjectFolder.setToolTip(file_path)

    def load_folder_contents(self):
        import os
        import re
        from PyQt5 import QtWidgets, QtCore

        file_path = self.ui_data_import.editDumpProjectFolder.text()
        if not file_path or not os.path.exists(file_path):
            QtWidgets.QMessageBox.warning(None, "Cảnh báo", "Vui lòng chọn file Backup hợp lệ!")
            return

        import zipfile
        import tempfile
        import shutil
        
        self.extracted_backup_dir = None
        if os.path.isfile(file_path) and file_path.endswith(".zip"):
            self.ui_data_import.lblStatus.setText(f"Đang giải nén backup từ {os.path.basename(file_path)}...")
            QtWidgets.QApplication.processEvents()
            
            temp_dir = os.path.join(tempfile.gettempdir(), "vision_pro_backup_extracted")
            if os.path.exists(temp_dir):
                try: shutil.rmtree(temp_dir)
                except Exception: pass
            os.makedirs(temp_dir, exist_ok=True)
            
            try:
                with zipfile.ZipFile(file_path, 'r') as zipf:
                    zipf.extractall(temp_dir)
            except zipfile.BadZipFile:
                QtWidgets.QMessageBox.warning(None, "Lỗi", "File ZIP bị hỏng, không thể giải nén!")
                return
                
            self.extracted_backup_dir = temp_dir
            db_folder = os.path.join(temp_dir, 'database')
            if os.path.exists(db_folder):
                folder_path = db_folder
            else:
                folder_path = temp_dir
        elif os.path.isdir(file_path):
            folder_path = file_path # Tương thích ngược nếu người dùng dán đường dẫn Folder
        else:
            QtWidgets.QMessageBox.warning(None, "Cảnh báo", "Vui lòng chọn file Backup (.zip) hợp lệ!")
            return

        sql_files = [f for f in os.listdir(folder_path) if f.endswith(".sql")]
        self.ui_data_import.treeSchemas.clear()
        self.ui_data_import.treeSchemaObjects.clear()
        self.import_db_map = {}

        self.ui_data_import.lblStatus.setText(f"Đang phân tích {len(sql_files)} files...")
        QtWidgets.QApplication.processEvents()

        for sql_file in sql_files:
            full_path = os.path.join(folder_path, sql_file)
            try:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # 1. Tìm Database Name từ file (dựa vào header Workbench chuẩn)
                db_match = re.search(r"-- Host: .* Database: (\S+)", content)
                if not db_match:
                    continue # Bỏ qua nếu không phải file dump đúng chuẩn
                    
                db_name = db_match.group(1)
                
                if db_name not in self.import_db_map:
                    self.import_db_map[db_name] = {'tables': [], 'item_codes': set(), 'files': []}
                    
                self.import_db_map[db_name]['files'].append(sql_file)

                # 2. Tìm Table Names
                tbl_matches = re.findall(r"DROP TABLE IF EXISTS `([^`]+)`", content)
                for tbl in tbl_matches:
                    if tbl not in self.import_db_map[db_name]['tables']:
                        self.import_db_map[db_name]['tables'].append(tbl)
                        
                # 3. Quét ITEMS_CODE để lấy mã Models
                if "items_code" in [t.lower() for t in tbl_matches] or "items_code" in sql_file.lower():
                    # Cấu trúc bảng ITEMS_CODE là (id INT, name_line_code VARCHAR, ...)
                    # Nên data sẽ có dạng VALUES (1, 'model_1', ...) hoặc (2,'model_2', ...)
                    # Dùng regex \(\d+,\s*'([^']+)' để lấy chuỗi string ngay sau số ID
                    item_matches = re.findall(r"\(\d+,\s*'([^']+)'", content)
                    for code in item_matches:
                        self.import_db_map[db_name]['item_codes'].add(code)

            except Exception as e:
                print(f"Error parsing {sql_file}: {e}")

        
        for db_name, data in self.import_db_map.items():
            if 'item_codes' in data and data['item_codes']:
                item = QtWidgets.QTreeWidgetItem(self.ui_data_import.treeSchemas)
                item.setText(0, db_name)
                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(0, QtCore.Qt.Checked)
                item.setData(0, QtCore.Qt.UserRole, db_name)

        self.ui_data_import.lblStatus.setText(f"Đã load thành công {len(self.import_db_map)} Databases.")

    def on_schema_clicked(self, item, column):
        from PyQt5 import QtWidgets, QtCore
        self.ui_data_import.treeSchemaObjects.clear()
        
        db_name = item.data(0, QtCore.Qt.UserRole)

        if not db_name or db_name not in self.import_db_map:
            return
        item_codes = sorted(list(self.import_db_map[db_name]['item_codes']))
        for code in item_codes:

            child = QtWidgets.QTreeWidgetItem(self.ui_data_import.treeSchemaObjects)
            child.setText(0, f"📄 {code}")
            child.setFlags(child.flags() | QtCore.Qt.ItemIsUserCheckable)
            child.setCheckState(0, QtCore.Qt.Checked)

    def select_view(self, *args):
        selected_items = self.ui_data_import.treeSchemas.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            item.setCheckState(0, QtCore.Qt.Checked)

    def select_tables(self, *args):
        selected_items = self.ui_data_import.treeSchemaObjects.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            item.setCheckState(0, QtCore.Qt.Checked)

    def unselect_all(self, *args):
        selected_items = self.ui_data_import.treeSchemas.selectedItems()
        selected_tables = self.ui_data_import.treeSchemaObjects.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            item.setCheckState(0, QtCore.Qt.Unchecked)
        for item in selected_tables:
            item.setCheckState(0, QtCore.Qt.Unchecked)


    def import_data(self):
        import os
        from PyQt5 import QtWidgets, QtCore

        self.ui_data_import.tabWidget.setCurrentIndex(1)
        self.ui_data_import.txtProgressLog.clear()
        self.ui_data_import.progressBar.setValue(0)
        
        def log_msg(msg):
            self.ui_data_import.txtProgressLog.appendPlainText(msg)
            QtWidgets.QApplication.processEvents()

        log_msg("Bắt đầu quá trình Import Dữ Liệu...")

        # 1. Thu thập danh sách Database được tích
        selected_dbs = []
        for i in range(self.ui_data_import.treeSchemas.topLevelItemCount()):
            item = self.ui_data_import.treeSchemas.topLevelItem(i)
            if item.checkState(0) == QtCore.Qt.Checked:
                db_name = item.data(0, QtCore.Qt.UserRole)
                if db_name: selected_dbs.append(db_name)

        # Bắt buộc import 4 Database hệ thống mặc định (nếu chúng tồn tại trong thư mục SQL)
        default_dbs = ['DATA_AUTO_LOGIN', 'DATA_IP_ADDRESS', 'ITEM_CODE_SAVE', 'ADMINISTRATOR']
        for def_db in default_dbs:
            for map_db in self.import_db_map.keys():
                if map_db.upper() == def_db.upper() and map_db not in selected_dbs:
                    selected_dbs.append(map_db)

        if not selected_dbs:
            log_msg("Lỗi: Không có Database nào để import (cả DB tùy chọn lẫn hệ thống)!")
            return

        # 2. Thu thập danh sách Item Codes bị UNTICK (để xóa sau khi import)
        unchecked_item_codes = []
        for i in range(self.ui_data_import.treeSchemaObjects.topLevelItemCount()):
            item = self.ui_data_import.treeSchemaObjects.topLevelItem(i)
            if item.checkState(0) == QtCore.Qt.Unchecked:
                code = item.text(0).replace("📄 ", "")
                unchecked_item_codes.append(code)

        folder_path = self.ui_data_import.editDumpProjectFolder.text()
        
        # Chuyển hướng path nếu đang đọc từ file ZIP đã giải nén
        if hasattr(self, 'extracted_backup_dir') and self.extracted_backup_dir:
            db_folder = os.path.join(self.extracted_backup_dir, 'database')
            if os.path.exists(db_folder):
                folder_path = db_folder
            else:
                folder_path = self.extracted_backup_dir
                
        if not os.path.exists(folder_path):
            log_msg("Lỗi: Thư mục import không tồn tại.")
            return

        cursor = self.connection.cursor(dictionary=False)
        
        total_files = sum(len(self.import_db_map[db]['files']) for db in selected_dbs if db in self.import_db_map)
        current_progress = 0

        # Hàm trợ giúp để xử lý file SQL có chứa DELIMITER (như routines của Workbench)
        def run_sql_script(script_content):
            import re
            parts = script_content.split("DELIMITER ;;")
            for idx, part in enumerate(parts):
                if idx == 0:
                    if part.strip():
                        # C-extension của mysql.connector không hỗ trợ multi=True
                        # Ta chia nhỏ các câu lệnh bằng ; nằm ở cuối dòng
                        stmts = re.split(r';\s*(?:\n|$)', part)
                        for stmt in stmts:
                            stmt = stmt.strip()
                            if stmt:
                                cursor.execute(stmt)
                else:
                    sub_parts = part.split("DELIMITER ;")
                    routine_code = sub_parts[0].strip()
                    if routine_code.endswith(";;"):
                        routine_code = routine_code[:-2].strip()
                    if routine_code:
                        cursor.execute(routine_code)
                    
                    if len(sub_parts) > 1:
                        after_code = sub_parts[1].strip()
                        if after_code:
                            stmts = re.split(r';\s*(?:\n|$)', after_code)
                            for stmt in stmts:
                                stmt = stmt.strip()
                                if stmt:
                                    cursor.execute(stmt)

        try:
            for db_name in selected_dbs:
                if db_name not in self.import_db_map:
                    continue
                
                log_msg(f"--- Đang Import Database: {db_name} ---")
                
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`;")
                cursor.execute(f"USE `{db_name}`;")
                
                files = self.import_db_map[db_name]['files']
                for f_name in files:
                    log_msg(f" -> Thực thi file: {f_name}")
                    full_path = os.path.join(folder_path, f_name)
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    try:
                        run_sql_script(content)
                    except Exception as e:
                        log_msg(f"    [!] Lỗi khi import {f_name}: {e}")
                        
                    current_progress += 1
                    self.ui_data_import.progressBar.setValue(int((current_progress / total_files) * 90))
                    QtWidgets.QApplication.processEvents()
                
                # Cập nhật thay đổi vào DB trước khi xóa
                self.connection.commit()
                
                # 3. Lọc dữ liệu ITEMS_CODE
                # Sử dụng cơ chế ON DELETE CASCADE của Database:
                # Chỉ cần XÓA các item_codes không được check trong bảng items_code, 
                # CSDL sẽ tự động xóa tất cả cấu hình Camera, Model, Trọng số liên quan!
                if unchecked_item_codes:
                    try:
                        cursor.execute("SHOW TABLES LIKE 'items_code'")
                        if cursor.fetchone():
                            log_msg(f" -> Đang lọc dữ liệu: Xóa {len(unchecked_item_codes)} Item Codes không được chọn...")
                            placeholders = ', '.join(['%s'] * len(unchecked_item_codes))
                            cursor.execute(f"DELETE FROM `items_code` WHERE name_line_code IN ({placeholders})", tuple(unchecked_item_codes))
                            self.connection.commit()
                    except Exception as e:
                        log_msg(f"    [!] Lỗi khi lọc Item Codes: {e}")

            # === AUTO-RESTORE WORKSPACE_WEIGHTS ===
            if hasattr(self, 'extracted_backup_dir') and self.extracted_backup_dir:
                weights_source = os.path.join(self.extracted_backup_dir, 'workspace_weights')
                if os.path.exists(weights_source):
                    log_msg("--- Đang phục hồi Model Weights ---")
                    import sys, shutil
                    if getattr(sys, 'frozen', False):
                        app_data = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or os.path.expanduser('~')
                        BASE_DIR = os.path.join(app_data, 'MBC_Vision_Inspector')
                    else:
                        BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
                    weights_dir = os.path.join(BASE_DIR, 'workspace_weights')
                    os.makedirs(weights_dir, exist_ok=True)
                    
                    copied = 0
                    for item in os.listdir(weights_source):
                        s = os.path.join(weights_source, item)
                        d = os.path.join(weights_dir, item)
                        if os.path.isdir(s):
                            shutil.copytree(s, d, dirs_exist_ok=True)
                        else:
                            shutil.copy2(s, d)
                        copied += 1
                    log_msg(f" -> Đã phục hồi {copied} models vào hệ thống thành công!")

            self.ui_data_import.progressBar.setValue(100)
            log_msg("\n==== HOÀN TẤT IMPORT DỮ LIỆU THÀNH CÔNG ====")
            QtWidgets.QMessageBox.information(None, "Thành công", "Quá trình Import CSDL và Model Weights đã hoàn tất!")

        except Exception as e:
            log_msg(f"\n[!] LỖI NGHIÊM TRỌNG: {e}")
            
    def close_window(self):
        if hasattr(self.ui_data_import, 'tabWidget'):
            self.ui_data_import.tabWidget.window().close()