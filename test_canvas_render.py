import sys
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPolygonF, QImage

app = QtWidgets.QApplication(sys.argv + ['-platform', 'offscreen'])

w = 1100
h = 620

image = QImage(w, h, QImage.Format_ARGB32)
image.fill(QColor("#FFFFFF"))

painter = QPainter(image)
painter.setRenderHint(QPainter.Antialiasing)

# 1. Lưới CAD: Lưới phụ (25px) nét chấm, lưới chính (100px) nét liền mảnh
pen_minor = QPen(QColor("#f1f5f9"), 1, Qt.DotLine)
pen_major = QPen(QColor("#e2e8f0"), 1, Qt.SolidLine)

for x in range(25, w, 25):
    painter.setPen(pen_major if (x % 100 == 0) else pen_minor)
    painter.drawLine(x, 0, x, h)
for y in range(25, h, 25):
    painter.setPen(pen_major if (y % 100 == 0) else pen_minor)
    painter.drawLine(0, y, w, y)

# 2. Hai đường trục tọa độ chính X và Y
pen_axis_x = QPen(QColor("#2563eb"), 2, Qt.SolidLine)
painter.setPen(pen_axis_x)
painter.drawLine(0, 1, w, 1)

pen_axis_y = QPen(QColor("#16a34a"), 2, Qt.SolidLine)
painter.setPen(pen_axis_y)
painter.drawLine(1, 0, 1, h)

# Mũi tên đầu trục X & Y
arrow_x = w - 10
painter.setBrush(QBrush(QColor("#2563eb")))
poly_x = QPolygonF([QPointF(arrow_x, 1), QPointF(arrow_x - 10, -4), QPointF(arrow_x - 10, 6)])
painter.drawPolygon(poly_x)

arrow_y = h - 10
painter.setBrush(QBrush(QColor("#16a34a")))
poly_y = QPolygonF([QPointF(1, arrow_y), QPointF(-4, arrow_y - 10), QPointF(6, arrow_y - 10)])
painter.drawPolygon(poly_y)

# 3. Thước đo pixel (Ruler Ticks & Coordinate Values)
painter.setFont(QFont("Segoe UI", 7, QFont.Bold))

# Vạch chia và số trục X (dọc mép trên, mỗi 100px)
for x in range(100, w - 40, 100):
    painter.setPen(QPen(QColor("#94a3b8"), 1.2))
    painter.drawLine(x, 0, x, 6)
    if x >= 160:
        painter.setPen(QColor("#64748b"))
        painter.drawText(QRectF(x - 25, 4, 50, 12), Qt.AlignCenter, f"{x}")

# Vạch chia và số trục Y (dọc mép trái, mỗi 100px)
for y in range(100, h - 20, 100):
    painter.setPen(QPen(QColor("#94a3b8"), 1.2))
    painter.drawLine(0, y, 6, y)
    painter.setPen(QColor("#64748b"))
    painter.drawText(QRectF(8, y - 7, 35, 14), Qt.AlignLeft | Qt.AlignVCenter, f"{y}")

# 4. Panel Gizmo Hệ Trục Tọa Độ tại góc trên bên trái
panel_rect = QRectF(10, 8, 146, 58)
painter.setBrush(QBrush(QColor(255, 255, 255, 245)))
painter.setPen(QPen(QColor("#cbd5e1"), 1.4))
painter.drawRoundedRect(panel_rect, 6, 6)

ox = 28.0
oy = 34.0

# Trục X trong Gizmo
painter.setPen(QPen(QColor("#2563eb"), 2.2))
painter.setBrush(QBrush(QColor("#2563eb")))
painter.drawLine(QPointF(ox, oy), QPointF(ox + 34, oy))
poly_gx = QPolygonF([QPointF(ox + 40, oy), QPointF(ox + 32, oy - 4), QPointF(ox + 32, oy + 4)])
painter.drawPolygon(poly_gx)

# Trục Y trong Gizmo
painter.setPen(QPen(QColor("#16a34a"), 2.2))
painter.setBrush(QBrush(QColor("#16a34a")))
painter.drawLine(QPointF(ox, oy), QPointF(ox, oy + 16))
poly_gy = QPolygonF([QPointF(ox, oy + 22), QPointF(ox - 4, oy + 14), QPointF(ox + 4, oy + 14)])
painter.drawPolygon(poly_gy)

# Gốc O
painter.setPen(QPen(QColor("#0f172a"), 1.5))
painter.setBrush(QBrush(QColor("#ffffff")))
painter.drawEllipse(QPointF(ox, oy), 3.0, 3.0)

painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
painter.setPen(QColor("#0f172a"))
painter.drawText(QPointF(ox - 14, oy + 3), "O")

painter.setPen(QColor("#2563eb"))
painter.drawText(QPointF(ox + 44, oy + 4), "+X")

painter.setPen(QColor("#16a34a"))
painter.drawText(QPointF(ox - 8, oy + 22), "+Y")

painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
painter.setPen(QColor("#1e293b"))
painter.drawText(QRectF(14, 10, 138, 13), Qt.AlignLeft, "📐 Hệ Tọa Độ Ảnh (0,0)")

painter.setFont(QFont("Segoe UI", 7, QFont.Normal))
painter.setPen(QColor("#475569"))
painter.drawText(QRectF(74, 23, 78, 12), Qt.AlignLeft, "X: 0 → Width")
painter.drawText(QRectF(74, 35, 78, 12), Qt.AlignLeft, "Y: 0 ↓ Height")
painter.drawText(QRectF(74, 47, 78, 12), Qt.AlignLeft, "Đơn vị: Pixel (px)")

# 5. Vẽ thử HUD trung tâm
hud_text = "📍 TOẠ ĐỘ: Box 1 [X=185, Y=140] | Box 2 [X=580, Y=140] | ΔX = 395 px"
painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
bw = max(560.0, float(len(hud_text) * 7.5))
bh = 26.0
hud_x = max(165.0, (w - bw) / 2)
hud_rect = QRectF(hud_x, 8, bw, bh)
painter.setBrush(QBrush(QColor("#ffffff")))
painter.setPen(QPen(QColor("#cbd5e1"), 1.5))
painter.drawRoundedRect(hud_rect, 6, 6)
painter.setPen(QColor("#334155"))
painter.drawText(hud_rect, Qt.AlignCenter, hud_text)

# 6. Vẽ thử Status Badge bên dưới HUD
status_text = "✓ THỎA MÃN ĐIỀU KIỆN (PASS) | Đối Tượng 1.X_MIN < Vùng Quy Chiếu 2.X_MIN"
status_bg = QColor("#f0fdf4")
status_border = QColor("#22c55e")
status_color = QColor("#15803d")
painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
tw = max(440.0, float(len(status_text) * 7.5 + 40.0))
tw = min(tw, float(w - 30.0))
th = 28.0
badge_rect = QRectF(max(165.0, (w - tw) / 2), 42.0, tw, th)
painter.setBrush(QBrush(status_bg))
painter.setPen(QPen(status_border, 1.6))
painter.drawRoundedRect(badge_rect, 6, 6)
painter.setPen(status_color)
painter.drawText(badge_rect, Qt.AlignCenter, status_text)

painter.end()

image.save("c:/project_vision/intenal/canvas_preview.png")
print("Rendered full composite preview to canvas_preview.png successfully")
