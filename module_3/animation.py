import random
from PyQt5 import QtCore, QtGui, QtWidgets

class AIVisionScene(QtWidgets.QGraphicsScene):
    def __init__(self, parent=None):
        super(AIVisionScene, self).__init__(parent)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(40) # ~25fps
        
        self.scan_y = 0
        self.scan_dir = 1
        self.points = []
        for _ in range(30):
            self.points.append([random.randint(0, 500), random.randint(0, 400), random.uniform(-1.5, 1.5), random.uniform(-1.5, 1.5)])
        self.boxes = []
        
    def update_frame(self):
        # Update scene rect to match viewport size precisely
        if self.views():
            view = self.views()[0]
            self.setSceneRect(QtCore.QRectF(view.viewport().rect()))
        self.update()
        
    def drawBackground(self, painter, rect):
        scene_rect = self.sceneRect()
        w = scene_rect.width()
        h = scene_rect.height()
        
        if w <= 0 or h <= 0: return
        
        painter.fillRect(scene_rect, QtGui.QColor("#0d1117")) # Dark background
        
        # Draw grid
        painter.setPen(QtGui.QPen(QtGui.QColor(48, 54, 61, 80), 1))
        for x in range(0, int(w), 30):
            painter.drawLine(x, 0, x, int(h))
        for y in range(0, int(h), 30):
            painter.drawLine(0, y, int(w), y)
            
        # Draw points and connections
        for p in self.points:
            p[0] += p[2]
            p[1] += p[3]
            # Clamp inside boundaries and bounce
            if p[0] < 0: 
                p[0] = 0; p[2] *= -1
            elif p[0] > w: 
                p[0] = w; p[2] *= -1
            if p[1] < 0: 
                p[1] = 0; p[3] *= -1
            elif p[1] > h: 
                p[1] = h; p[3] *= -1
            
        painter.setPen(QtGui.QPen(QtGui.QColor(88, 166, 255, 60), 1))
        for i in range(len(self.points)):
            for j in range(i+1, len(self.points)):
                dx = self.points[i][0] - self.points[j][0]
                dy = self.points[i][1] - self.points[j][1]
                if dx*dx + dy*dy < 5000: # Distance threshold
                    painter.drawLine(int(self.points[i][0]), int(self.points[i][1]), int(self.points[j][0]), int(self.points[j][1]))
        
        painter.setPen(QtGui.QPen(QtGui.QColor(88, 166, 255, 200), 2))
        painter.setBrush(QtGui.QColor(88, 166, 255))
        for p in self.points:
            painter.drawEllipse(int(p[0])-2, int(p[1])-2, 4, 4)
            
        # Draw Laser Scanner
        self.scan_y += 3 * self.scan_dir
        if self.scan_y > h or self.scan_y < 0:
            self.scan_dir *= -1
            
        painter.setPen(QtGui.QPen(QtGui.QColor(57, 211, 83, 200), 2))
        painter.drawLine(0, int(self.scan_y), int(w), int(self.scan_y))
        
        grad = QtGui.QLinearGradient(0, self.scan_y - 30 * self.scan_dir, 0, self.scan_y)
        grad.setColorAt(0, QtGui.QColor(57, 211, 83, 0))
        grad.setColorAt(1, QtGui.QColor(57, 211, 83, 70))
        painter.fillRect(QtCore.QRectF(0, min(self.scan_y, self.scan_y - 30 * self.scan_dir), w, 30), grad)
        
        # Draw Random Bounding Boxes
        if random.random() < 0.04 and w > 120 and h > 120:
            bw, bh = random.randint(40, 120), random.randint(40, 120)
            self.boxes.append([random.randint(0, int(w)-bw), random.randint(0, int(h)-bh), bw, bh, 30])
            
        for b in self.boxes[:]:
            alpha = min(255, max(0, int(b[4] * 8.5)))
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 123, 114, alpha), 1))
            painter.drawRect(b[0], b[1], b[2], b[3])
            
            # Corner accents
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 123, 114, alpha), 2))
            l = 12
            painter.drawLine(b[0], b[1], b[0]+l, b[1])
            painter.drawLine(b[0], b[1], b[0], b[1]+l)
            painter.drawLine(b[0]+b[2], b[1], b[0]+b[2]-l, b[1])
            painter.drawLine(b[0]+b[2], b[1], b[0]+b[2], b[1]+l)
            painter.drawLine(b[0], b[1]+b[3], b[0]+l, b[1]+b[3])
            painter.drawLine(b[0], b[1]+b[3], b[0], b[1]+b[3]-l)
            painter.drawLine(b[0]+b[2], b[1]+b[3], b[0]+b[2]-l, b[1]+b[3])
            painter.drawLine(b[0]+b[2], b[1]+b[3], b[0]+b[2], b[1]+b[3]-l)
            
            painter.setFont(QtGui.QFont("Consolas", 8, QtGui.QFont.Bold))
            painter.setPen(QtGui.QColor(255, 123, 114, alpha))
            painter.drawText(b[0], b[1]-5, f"DETECTION: {80 + (b[4]*3)%20}%")
            
            b[4] -= 1
            if b[4] <= 0:
                self.boxes.remove(b)


import math, random

# ─────────────────────────────────────────────────────────────────────────────
# PLC Signal Communication Visualization — PRE / GRAB / POST cycle
# Mirrors the actual handshake in main_core.py:
#   PRE : gate=ON, busy=ON, ready=OFF  → PLC fires trigger → AI grabs image
#   GRAB: camera capture in progress
#   POST: gate=OFF, busy=OFF, ready=ON → complete=ON → reset
# ─────────────────────────────────────────────────────────────────────────────
class PLCSignalScene(QtWidgets.QGraphicsScene):

    # Index constants matching SIGNALS list
    IDX = {"READY":0,"RUN":1,"TRIGGER":2,"BUSY":3,"GATE":4,"COMPLETE":5,"RESET":6}
    SIGNALS = ["READY","RUN","TRIGGER","BUSY","GATE","COMPLETE","RESET"]
    COLORS  = [
        QtGui.QColor("#3fb950"),QtGui.QColor("#58a6ff"),QtGui.QColor("#f0883e"),
        QtGui.QColor("#d2a8ff"),QtGui.QColor("#79c0ff"),QtGui.QColor("#56d364"),
        QtGui.QColor("#ff7b72"),
    ]

    # Cycle phases: (phase_name, duration_ticks, signals_on_indices, direction_per_signal)
    # direction: 1=PLC→AI(right), -1=AI→PLC(left)
    CYCLE = [
        # PRE-grab: PLC sends GATE/BUSY ON, READY OFF → AI receives
        ("PRE-GRAB",  60,  [4,3],    { 4:1, 3:1 }),   # GATE, BUSY → right
        # PLC sends TRIGGER ON → AI
        ("TRIGGER",   30,  [4,3,2],  { 2:1 }),         # TRIGGER → right
        # AI sends READY OFF (acknowledge) → PLC
        ("ACK",       20,  [4,3,2],  { 0:-1 }),         # READY ← left
        # GRAB in progress
        ("GRABBING",  55,  [4,3,2,1],{}),
        # POST-grab: AI sends GATE/BUSY OFF
        ("POST-GRAB", 45,  [1,5],    { 4:-1,3:-1 }),   # GATE, BUSY ← left
        # COMPLETE signal AI→PLC
        ("COMPLETE",  30,  [5],      { 5:-1 }),         # COMPLETE ← left
        # RESET
        ("RESET",     25,  [],       { 6:1 }),           # RESET → right
        # READY ON restored
        ("IDLE",      50,  [0],      { 0:1 }),           # READY → right
    ]


    def __init__(self, parent=None):
        super().__init__(parent)
        self._tick        = 0
        self._pulse_phase = 0.0
        self._packets     = []     # {sig, x, dir, speed, tail}
        self._particles   = []     # {x,y,vx,vy,life,col}
        self._flash       = {}     # sig_idx -> remaining_ticks of flash
        self._signal_states = [False]*len(self.SIGNALS)
        # cycle state
        self._phase_idx   = 0
        self._phase_tick  = 0
        self._phase_name  = ""
        self._grab_flash  = 0     # white flash when GRABBING starts
        self._timeline_x  = 0.0  # 0..1 progress within phase

        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self._step)
        self._timer.start(35)

    def _fire_packet(self, sig_idx, direction, speed=None):
        spd = speed or random.uniform(0.006, 0.012)
        self._packets.append({
            "sig": sig_idx, "dir": direction,
            "x": 0.0 if direction > 0 else 1.0,
            "speed": spd, "tail": []
        })

    def _spawn_particles(self, px, cy, col, n=10):
        for _ in range(n):
            angle = random.uniform(0, 2*math.pi)
            spd   = random.uniform(0.5, 2.5)
            self._particles.append({
                "x":px,"y":cy,"vx":math.cos(angle)*spd,"vy":math.sin(angle)*spd,
                "life":random.randint(15,35),"col":col
            })

    def _step(self):
        self._tick        += 1
        self._pulse_phase += 0.07
        if self._grab_flash > 0:
            self._grab_flash -= 1

        # ── advance cycle ──
        phase_name, duration, on_indices, fire_map = self.CYCLE[self._phase_idx]
        self._phase_name = phase_name
        self._phase_tick += 1
        self._timeline_x  = min(1.0, self._phase_tick / duration)

        # Update signal states for this phase
        for i in range(len(self.SIGNALS)):
            self._signal_states[i] = (i in on_indices)

        # Fire packets at start of phase (tick==1)
        if self._phase_tick == 1:
            for sig_idx, direction in fire_map.items():
                self._fire_packet(sig_idx, direction)
            if phase_name == "GRABBING":
                self._grab_flash = 18

        # Occasional extra random packets during GRABBING for liveliness
        if phase_name == "GRABBING" and self._tick % 15 == 0:
            self._fire_packet(random.choice([1,2,3]), random.choice([1,-1]), 0.009)

        # Advance to next phase
        if self._phase_tick >= duration:
            self._phase_idx  = (self._phase_idx + 1) % len(self.CYCLE)
            self._phase_tick = 0

        # ── advance packets ──
        alive = []
        for p in self._packets:
            prev_x = p["x"]
            p["x"] += p["dir"] * p["speed"]
            p["tail"].append(prev_x)
            if len(p["tail"]) > 8:
                p["tail"].pop(0)
            if 0.0 <= p["x"] <= 1.0:
                alive.append(p)
            else:
                # burst particles at arrival
                col = self.COLORS[p["sig"]]
                self._flash[p["sig"]] = 12
        self._packets = alive

        # ── advance particles ──
        alive_p = []
        for pt in self._particles:
            pt["x"] += pt["vx"]; pt["y"] += pt["vy"]
            pt["vy"] += 0.08   # slight gravity
            pt["life"] -= 1
            if pt["life"] > 0:
                alive_p.append(pt)
        self._particles = alive_p

        # ── decay flashes ──
        self._flash = {k:v-1 for k,v in self._flash.items() if v > 1}

        if self.views():
            vp = self.views()[0].viewport().rect()
            self.setSceneRect(QtCore.QRectF(vp))
        self.update()

    def drawBackground(self, painter, rect):
        sr = self.sceneRect()
        W, H = sr.width(), sr.height()
        if W <= 0 or H <= 0: return

        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # ── background ──
        painter.fillRect(sr, QtGui.QColor("#0d1117"))

        # ── GRAB camera flash overlay ──
        if self._grab_flash > 0:
            alpha = int(self._grab_flash * 9)
            painter.fillRect(sr, QtGui.QColor(255, 230, 100, alpha))

        # ── faint grid ──
        painter.setPen(QtGui.QPen(QtGui.QColor(35, 45, 58, 70), 1))
        for x in range(0, int(W), 26):
            painter.drawLine(x, 0, x, int(H))
        for y in range(0, int(H), 26):
            painter.drawLine(0, y, int(W), y)

        n     = len(self.SIGNALS)
        pad   = 16
        bar_h = 18   # bottom timeline bar height
        row_h = (H - 2*pad - bar_h - 22) / (n + 1)

        box_w = 88
        plc_x = pad
        ai_x  = W - pad - box_w

        # ── phase label top ──
        phase_col = {"PRE-GRAB":QtGui.QColor("#f0883e"),"TRIGGER":QtGui.QColor("#ff7b72"),
                     "ACK":QtGui.QColor("#d2a8ff"),"GRABBING":QtGui.QColor("#ffd700"),
                     "POST-GRAB":QtGui.QColor("#79c0ff"),"COMPLETE":QtGui.QColor("#56d364"),
                     "RESET":QtGui.QColor("#ff7b72"),"IDLE":QtGui.QColor("#3fb950")}.get(
                     self._phase_name, QtGui.QColor("#58a6ff"))
        t_alpha = int(190 + 55*math.sin(self._pulse_phase))
        painter.setFont(QtGui.QFont("Consolas", 9, QtGui.QFont.Bold))
        painter.setPen(QtGui.QColor(88,166,255,t_alpha))
        painter.drawText(QtCore.QRectF(0,2,W,16), QtCore.Qt.AlignCenter,
                         "◈  PLC ⟷ AI-PC  SIGNAL HANDSHAKE  ◈")
        painter.setFont(QtGui.QFont("Consolas", 8, QtGui.QFont.Bold))
        painter.setPen(phase_col)
        painter.drawText(QtCore.QRectF(0,18,W,14), QtCore.Qt.AlignCenter,
                         f"[ {self._phase_name} ]")

        box_h = H - 2*pad - bar_h - 22

        # ── draw PLC & AI-PC blocks ──
        for bx, label, accent in [(plc_x,"PLC",QtGui.QColor("#58a6ff")),
                                   (ai_x,"AI-PC",QtGui.QColor("#3fb950"))]:
            # ambient glow
            glow = QtGui.QRadialGradient(bx+box_w/2, pad+22+box_h/2, box_w*1.2)
            glow.setColorAt(0, QtGui.QColor(accent.red(),accent.green(),accent.blue(),20))
            glow.setColorAt(1, QtGui.QColor(0,0,0,0))
            painter.fillRect(QtCore.QRectF(bx-20,pad+22-10,box_w+40,box_h+20), glow)

            # box
            painter.setBrush(QtGui.QColor(18,24,32))
            painter.setPen(QtGui.QPen(accent, 1.5))
            painter.drawRoundedRect(QtCore.QRectF(bx, pad+22, box_w, box_h), 7, 7)

            # label
            painter.setFont(QtGui.QFont("Consolas", 10, QtGui.QFont.Bold))
            painter.setPen(accent)
            painter.drawText(QtCore.QRectF(bx, pad+22, box_w, 26),
                             QtCore.Qt.AlignCenter, label)

            # LED per signal
            for i, sig in enumerate(self.SIGNALS):
                cy    = pad + 22 + 26 + row_h*(i+0.5) + row_h/2
                is_on = self._signal_states[i]
                col   = self.COLORS[i]
                flash = self._flash.get(i,0)

                led_r = 5 + (3 if flash > 0 else 0)
                if is_on or flash:
                    glow2 = QtGui.QRadialGradient(bx+box_w/2, cy, led_r*3)
                    glow2.setColorAt(0, QtGui.QColor(col.red(),col.green(),col.blue(),120))
                    glow2.setColorAt(1, QtGui.QColor(0,0,0,0))
                    painter.setBrush(glow2); painter.setPen(QtCore.Qt.NoPen)
                    painter.drawEllipse(QtCore.QPointF(bx+box_w/2, cy), led_r*3, led_r*3)
                    painter.setBrush(col)
                    painter.setPen(QtGui.QPen(col.lighter(160), 1))
                else:
                    painter.setBrush(QtGui.QColor(28,38,50))
                    painter.setPen(QtGui.QPen(QtGui.QColor(55,70,88), 1))
                painter.drawEllipse(QtCore.QPointF(bx+box_w/2, cy), led_r, led_r)

                # signal label (left block only)
                if bx == plc_x:
                    painter.setFont(QtGui.QFont("Consolas", 7))
                    painter.setPen(col if (is_on or flash) else QtGui.QColor(80,95,115))
                    painter.drawText(QtCore.QRectF(bx+2, cy-8, box_w-4, 16),
                                     QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, sig)

        # ── lanes & packets ──
        lane_x0 = plc_x + box_w + 5
        lane_x1 = ai_x - 5
        lane_w  = lane_x1 - lane_x0

        for i, sig in enumerate(self.SIGNALS):
            cy    = pad + 22 + 26 + row_h*(i+0.5) + row_h/2
            col   = self.COLORS[i]
            is_on = self._signal_states[i]
            flash = self._flash.get(i, 0)

            # track
            tk_alpha = 60 if is_on else 20
            painter.setPen(QtGui.QPen(QtGui.QColor(col.red(),col.green(),col.blue(),tk_alpha), 3))
            painter.drawLine(QtCore.QPointF(lane_x0, cy), QtCore.QPointF(lane_x1, cy))

            # glow line when active
            if is_on:
                gl = QtGui.QLinearGradient(lane_x0,cy,lane_x1,cy)
                gl.setColorAt(0,  QtGui.QColor(col.red(),col.green(),col.blue(),0))
                gl.setColorAt(0.5,QtGui.QColor(col.red(),col.green(),col.blue(),90))
                gl.setColorAt(1,  QtGui.QColor(col.red(),col.green(),col.blue(),0))
                painter.setPen(QtGui.QPen(QtGui.QBrush(gl), 2))
                painter.drawLine(QtCore.QPointF(lane_x0,cy), QtCore.QPointF(lane_x1,cy))

            # connector dots
            for cx2 in (lane_x0, lane_x1):
                painter.setBrush(col if (is_on or flash) else QtGui.QColor(38,50,65))
                painter.setPen(QtCore.Qt.NoPen)
                painter.drawEllipse(QtCore.QPointF(cx2, cy), 4, 4)

        # ── draw packet tails & heads ──
        for p in self._packets:
            i   = p["sig"]
            col = self.COLORS[i]
            cy  = pad + 22 + 26 + row_h*(i+0.5) + row_h/2
            px  = lane_x0 + p["x"] * lane_w
            going = p["dir"] > 0

            # tail (fading trail)
            for ti, tx in enumerate(p["tail"]):
                tail_px = lane_x0 + tx * lane_w
                alpha   = int(120 * (ti+1) / (len(p["tail"])+1))
                r = max(1, 4 - (len(p["tail"])-ti)//2)
                painter.setBrush(QtGui.QColor(col.red(),col.green(),col.blue(),alpha))
                painter.setPen(QtCore.Qt.NoPen)
                painter.drawEllipse(QtCore.QPointF(tail_px, cy), r, r)

            # outer glow
            grad = QtGui.QRadialGradient(px, cy, 16)
            grad.setColorAt(0, QtGui.QColor(col.red(),col.green(),col.blue(),110))
            grad.setColorAt(1, QtGui.QColor(0,0,0,0))
            painter.setBrush(grad); painter.setPen(QtCore.Qt.NoPen)
            painter.drawEllipse(QtCore.QPointF(px, cy), 16, 16)

            # core
            painter.setBrush(col)
            painter.setPen(QtGui.QPen(QtCore.Qt.white, 0.8))
            painter.drawEllipse(QtCore.QPointF(px, cy), 5, 5)

            # arrowhead
            ao = 10 if going else -10
            a5 = 5  if going else -5
            tip  = QtCore.QPointF(px+ao, cy)
            lft  = QtCore.QPointF(px+ao-a5, cy-4)
            rgt  = QtCore.QPointF(px+ao-a5, cy+4)
            painter.setBrush(col); painter.setPen(QtCore.Qt.NoPen)
            painter.drawPolygon(QtGui.QPolygonF([tip, lft, rgt]))

            # register flash-burst on arrival already handled in _step

        # ── particles ──
        for pt in self._particles:
            c = pt["col"]
            a = max(0, min(255, int(pt["life"]*6)))
            painter.setBrush(QtGui.QColor(c.red(),c.green(),c.blue(),a))
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawEllipse(QtCore.QPointF(pt["x"],pt["y"]), 2, 2)

        # ── bottom timeline bar ──
        bar_y = H - bar_h - 2
        total_ticks = sum(d for _,d,_,_ in self.CYCLE)
        elapsed = sum(self.CYCLE[j][1] for j in range(self._phase_idx)) + self._phase_tick
        prog = elapsed / total_ticks

        painter.setBrush(QtGui.QColor(28,36,46)); painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(QtCore.QRectF(pad, bar_y, W-2*pad, bar_h-2), 3, 3)

        bar_grad = QtGui.QLinearGradient(pad, bar_y, pad+(W-2*pad)*prog, bar_y)
        bar_grad.setColorAt(0, phase_col.darker(130))
        bar_grad.setColorAt(1, phase_col)
        painter.setBrush(bar_grad)
        painter.drawRoundedRect(QtCore.QRectF(pad, bar_y, (W-2*pad)*prog, bar_h-2), 3, 3)

        painter.setFont(QtGui.QFont("Consolas", 7))
        painter.setPen(QtGui.QColor(200,210,220,200))
        painter.drawText(QtCore.QRectF(pad+4, bar_y, W-2*pad-8, bar_h-2),
                         QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft,
                         f"CYCLE  {int(prog*100):3d}%  —  {self._phase_name}")

