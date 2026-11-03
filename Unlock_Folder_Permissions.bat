@echo off
:: ============================================================================
:: AI VISION PRO - UNLOCK FOLDER PERMISSIONS
:: ============================================================================
:: Script tự động mở khóa toàn bộ quyền ghi (Modify / Write) cho thư mục cài đặt
:: phần mềm khi nằm trong C:\Program Files hoặc C:\Program Files (x86).
:: Sau khi chạy, bạn có thể chỉnh sửa và lưu code trực tiếp trong scripts_editor
:: hoặc bên ngoài mà không bao giờ gặp lỗi 'Permission denied'.
:: ============================================================================

title AI Vision Pro - Unlock Permissions

:: 1. Kiểm tra quyền Administrator, nếu chưa có thì tự động gọi UAC để nâng quyền
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Dang yeu cau quyen Administrator...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd -ArgumentList '/c \"\"%~dpnx0\"\" elevated' -Verb RunAs"
    exit /b
)

set "TARGET_DIR=%~dp0"
echo ============================================================================
echo   AI VISION PRO - MO KHOA QUYEN GHI THU MUC
echo ============================================================================
echo.
echo [*] Thu muc muc tieu: "%TARGET_DIR%"
echo.
echo [1/3] Xoa thuoc tinh chi doc (Read-Only) tren tat ca cac file...
attrib -R "%TARGET_DIR%*.*" /S /D >nul 2>&1

echo [2/3] Cap quyen Modify (Ghi/Sua/Xoa) cho nhom nguoi dung (Built-in Users)...
icacls "%TARGET_DIR%" /grant *S-1-5-32-545:(OI)(CI)M /T /C >nul 2>&1

echo [3/3] Cap quyen Modify cho Everyone va Users...
icacls "%TARGET_DIR%" /grant *S-1-1-0:(OI)(CI)M /grant Users:(OI)(CI)M /T /C >nul 2>&1

echo.
echo ============================================================================
echo [THANH CONG] DA MO KHOA QUYEN GHI THANH CONG!
echo.
echo Tu bay gio ban co the thoai mai:
echo   - Chinh sua va bam Luu file (Ctrl+S) trong scripts_editor cua phan mem.
echo   - Chinh sua code truc tiep trong 'Open file location' qua Notepad/VS Code.
echo   - Khong con bi loi 'Permission denied'.
echo ============================================================================
echo.
if "%1" neq "elevated" pause

