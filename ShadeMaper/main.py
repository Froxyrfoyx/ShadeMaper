import sys
import os
import asyncio
import concurrent.futures
import json
from urllib.parse import urljoin
from PySide6.QtGui import QFont, QPixmap, QPainter, QRadialGradient, QColor
from PySide6.QtCore import Qt, QTimer, QUrl , QObject,Signal
from PySide6.QtWidgets import (QApplication, QBoxLayout, QMainWindow, QWidget, QLabel,
                               QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QPlainTextEdit)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from qasync import asyncSlot, QEventLoop
import networkx as nx
from curl_cffi.requests import AsyncSession
from core.analyzer import Analyzer
from core.crawler import WebantulaCrawler
from core.graphmanager import GraphManager
from core.config import ConfigsettingManager
from core.behavopt import BehavOptimize
import os
import json
import asyncio
import concurrent.futures
from urllib.parse import urlparse, urljoin
import networkx as nx
from logger import AsyncLogger
class QTsignal(QObject):
    node_added = Signal(str, int, str)
    scan_finished = Signal()
    def __init__(self):
        super().__init__()

import concurrent.futures
import os


class WebantulaUI(QMainWindow):

    def __init__(self):
        super().__init__()
        self.crawler = None
        self.analyzer = Analyzer()
        self.signal = QTsignal()
        self.signal.node_added.connect(self.update_ui)
        self.signal.scan_finished.connect(self.on_scan_finished)
        self.setting = ConfigsettingManager()
        self.manager = GraphManager()
        self._thread_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1
        )
        self.logger = AsyncLogger()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com")
        self.setWindowTitle("ShadeMaper")
        self.resize(1100, 800)
        self.setStyleSheet("""
            QMainWindow { background-color: #0d0e15; }
            QLabel { color: #a5a6bc; font-size: 13px; font-weight: bold; }
            QLineEdit { background-color: #161925; border: 1px solid #323751; border-radius: 6px; padding: 8px 12px; color: #ffffff; font-size: 14px; }
            QLineEdit:focus { border: 1px solid #9b51e0; }
            QPushButton { background-color: #7928ca; color: white; border: none; border-radius: 6px; padding: 10px 20px; font-size: 14px; font-weight: bold; }
            QPushButton:hover { background-color: #9b51e0; }
            QPushButton:pressed { background-color: #5b1cb0; }
            QPushButton:disabled { background-color: #323751; color: #a5a6bc; }
        """)

        self.HTML_GRAPH_PATH = os.path.abspath("shade_map.html")
        self.LOG_FILE_PATH = os.path.abspath("shademaper.log")
        self.last_log_size = 0

        self.central_widget = QWidget()
        self.log_area = QPlainTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFixedHeight(120)
        self.log_area.setStyleSheet(
            "background-color: #07080c; color: #a5a6bc; font-family: Consolas;"
            " border: 1px solid #1f2335;"
        )

        self.central_layout = QVBoxLayout(self.central_widget)
        self.central_layout.setContentsMargins(25, 25, 25, 25)
        self.central_layout.setSpacing(15)

        self.btn_scan = QPushButton("Начать сканирование")

        header_layout = QHBoxLayout()
        header_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title = QLabel("ShadeMaper")
        title.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff; letter-spacing: 1px;")
        header_layout.addWidget(title)

        logo_label = QLabel()
        logo_label.setPixmap(self.create_logo(45))
        logo_label.setStyleSheet("margin-left: 10px")
        header_layout.addWidget(logo_label)

        self.btn_scan.clicked.connect(self.start_scan)

        self.view = QWebEngineView()
        self.view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptEnabled, True
        )
        self.view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.WebGLEnabled, True
        )
        self.view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
            True,
        )
        self.view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
        )
        self.view.setStyleSheet(
            "border: 1px solid #1f2335; border-radius: 8px;"
            " background-color: #07080c;"
        )

        self.btn_refresh = QPushButton("Обновить граф")
        self.btn_refresh.clicked.connect(self.sync_widgets_with_files)
        self.central_layout.addWidget(self.btn_refresh)

        if os.path.exists(self.HTML_GRAPH_PATH):
            self.view.setUrl(QUrl.fromLocalFile(self.HTML_GRAPH_PATH))

        self.central_layout.addLayout(header_layout)
        self.central_layout.addWidget(QLabel("Target url:"))
        self.central_layout.addWidget(self.url_input)
        self.central_layout.addWidget(self.btn_scan)
        self.central_layout.addWidget(self.view, stretch=1)
        self.central_layout.addWidget(self.log_area)

        self.btn_export = QPushButton("Export")
        self.btn_export.clicked.connect(self.trigger_export)
        self.central_layout.addWidget(self.btn_export)
        self.setCentralWidget(self.central_widget)
    def sync_widgets_with_files(self):
        if os.path.exists(self.HTML_GRAPH_PATH):
            if self.view.url().isEmpty():
                self.view.setUrl(QUrl.fromLocalFile(self.HTML_GRAPH_PATH))
            else:
                self.view.reload()

        if os.path.exists(self.LOG_FILE_PATH):
            current_size = os.path.getsize(self.LOG_FILE_PATH)
            if current_size < self.last_log_size:
                self.last_log_size = 0
                self.log_area.clear()
            if current_size > self.last_log_size:
                with open(self.LOG_FILE_PATH, "r", encoding="utf-8") as f:
                    f.seek(self.last_log_size)
                    new_lines = f.read()
                    if new_lines:
                        self.log_area.appendPlainText(new_lines.strip())
                        self.log_area.ensureCursorVisible()
                self.last_log_size = current_size

    def init_embedded_canvas(self):
           self.GRAPH_JSON_PATH = os.path.abspath("graph.json")
           self.LOG_FILE_PATH = os.path.abspath("scanner.log")
           self.last_log_size = 0

           self.view.settings().setAttribute(
               QWebEngineSettings.WebAttribute.WebGLEnabled, True
           )
           self.view.settings().setAttribute(
               QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True
           )

           vivagraph_code = ""
           viva_path = os.path.abspath("vivagraph.js")
           if os.path.exists(viva_path):
               with open(viva_path, "r", encoding="utf-8") as f:
                   vivagraph_code = f.read()
           else:
               self.log_area.appendPlainText(f"[WARN] {viva_path} не найден!")

           canvas_html = f"""<!DOCTYPE html>
           <html>
           <head>
               <meta charset="utf-8">
               <style>
                   body, html, #graph-container {{ width: 100%; height: 100%; margin: 0; padding: 0; overflow: hidden; background: #07080c; position: relative; }}
                   #graph, #canvas-labels {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; }}
                   #canvas-labels {{ pointer-events: none; z-index: 10; }}
                   #placeholder {{ color: #323751; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); letter-spacing: 2px; font-weight: bold; font-family: sans-serif; z-index: 11; font-size: 18px; }}
               </style>
           </head>
           <body>
               <div id="graph-container">
                   <div id="placeholder">ОЖИДАНИЕ ЗАПУСКА СКАНИРОВАНИЯ</div>
                   <div id="graph"></div>
                   <canvas id="canvas-labels"></canvas>
               </div>

               <script type="text/javascript">
                   {vivagraph_code}
               </script>

               <script type="text/javascript">
                   let graph, layout, webglGraphics, renderer, labelCanvas, ctx;

                   try {{
                       graph = Viva.Graph.graph();
                       layout = Viva.Graph.Layout.forceDirected(graph, {{
                           springLength: 160, springCoeff: 0.0002, gravity: -0.4, dragCoeff: 0.09, theta: 0.8
                       }});

                       webglGraphics = Viva.Graph.View.webglGraphics();
                       webglGraphics.node(function(node) {{
                           let colorHex = 0xa855f7ff;
                           if (node.data.color === '#ff0033') colorHex = 0xff0033ff;
                           if (node.data.color === '#ffdc00') colorHex = 0xffdc00ff;
                           return Viva.Graph.View.webglSquare((node.data.val || 2.5) * 3.5, colorHex);
                       }});

                       webglGraphics.link(function(link) {{
                           return Viva.Graph.View.webglLine(link.data.color === '#ff0033' ? 0xff0033ff : 0xa855f714);
                       }});

                       renderer = Viva.Graph.View.renderer(graph, {{
                           container: document.getElementById('graph'), layout: layout, graphics: webglGraphics
                       }});
                       renderer.run();

                       labelCanvas = document.getElementById('canvas-labels');
                       ctx = labelCanvas.getContext('2d');
                       window.addEventListener('resize', resizeCanvas);
                       resizeCanvas();
                       requestAnimationFrame(globalAnimationLoop);
                   }} catch (err) {{ console.error("VivaGraph err:", err); }}

                   function resizeCanvas() {{
                       if (labelCanvas) {{ labelCanvas.width = window.innerWidth; labelCanvas.height = window.innerHeight; }}
                   }}

                   function drawLabels() {{
                       if (!ctx || !renderer || !webglGraphics || typeof renderer.getTransform !== 'function') return;
                       ctx.clearRect(0, 0, labelCanvas.width, labelCanvas.height);
                       const transform = renderer.getTransform();
                       if (!transform || transform.scale <= 0.03) return;

                       const scale = transform.scale, offsetX = transform.offsetX || 0, offsetY = transform.offsetY || 0;
                       const halfW = labelCanvas.width / 2, halfH = labelCanvas.height / 2;

                       ctx.fillStyle = '#eeeeee'; ctx.font = 'bold 10px monospace'; ctx.textAlign = 'center'; ctx.textBaseline = 'top';

                       graph.forEachNode(function(node) {{
                           let pos = null;
                           if (typeof webglGraphics.getNodeUI === 'function') {{
                               const nodeUI = webglGraphics.getNodeUI(node.id);
                               if (nodeUI) pos = nodeUI.position;
                           }}
                           if (!pos && typeof layout.getNodePosition === 'function') pos = layout.getNodePosition(node.id);
                           if (!pos) return;

                           const screenX = pos.x * scale + offsetX + halfW;
                           const screenY = pos.y * scale + offsetY + halfH;

                           if (screenX >= 0 && screenX <= labelCanvas.width && screenY >= 0 && screenY <= labelCanvas.height) {{
                               let lbl = (node.data.label || node.id).replace("https://", "").replace("http://", "");
                               if (lbl.length > 25) lbl = lbl.substring(0, 22) + "...";
                               ctx.fillText(lbl, screenX, screenY + ((node.data.val || 2.5) * 3.5 / 2 + 6 / scale) * scale);
                           }}
                       }});
                   }}

                   function globalAnimationLoop() {{ drawLabels(); requestAnimationFrame(globalAnimationLoop); }}

                   function updateGraph(nodesArray, edgesArray) {{
                       if (!graph) return;
                       const ph = document.getElementById('placeholder');
                       if (ph && nodesArray && nodesArray.length > 0) ph.style.display = 'none';

                       if (nodesArray) {{
                           nodesArray.forEach(n => {{
                               const existingNode = graph.getNode(n.id);
                               if (!existingNode) graph.addNode(n.id, {{ label: n.label, color: n.color, val: n.val }});
                               else {{ existingNode.data.color = n.color; existingNode.data.val = n.val; }}
                           }});
                       }}
                       if (edgesArray) {{
                           edgesArray.forEach(e => {{
                               if (!graph.getLink(e.from, e.to)) graph.addLink(e.from, e.to, {{ color: e.color }});
                           }});
                       }}
                   }}
               </script>
           </body>
           </html>
           """

           temp_html_path = os.path.abspath("temp_graph.html")
           with open(temp_html_path, "w", encoding="utf-8") as f:
               f.write(canvas_html)
           self.view.setUrl(QUrl.fromLocalFile(temp_html_path))

           self.update_timer = QTimer(self)
           self.update_timer.timeout.connect(self.poll_files_update)
           self.update_timer.start(1500)


    def poll_files_update(self):
           if os.path.exists(self.LOG_FILE_PATH):
               current_size = os.path.getsize(self.LOG_FILE_PATH)
               if current_size > self.last_log_size:
                   with open(self.LOG_FILE_PATH, "r", encoding="utf-8") as f:
                       f.seek(self.last_log_size)
                       new_logs = f.read()
                       if new_logs:
                           self.log_area.appendPlainText(new_logs.strip())
                           self.log_area.ensureCursorVisible()
                   self.last_log_size = current_size

           if os.path.exists(self.GRAPH_JSON_PATH):
               try:
                   with open(self.GRAPH_JSON_PATH, "r", encoding="utf-8") as f:
                       data = json.load(f)

                   nodes_json = json.dumps(data.get("nodes", []), ensure_ascii=False)
                   edges_json = json.dumps(data.get("edges", []), ensure_ascii=False)

                   self.view.page().runJavaScript(
                       "updateGraph(%s, %s);" % (nodes_json, edges_json)
                   )
               except Exception:
                   pass
    def create_logo(self, size):
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center_x = size / 2
        center_y = size / 2
        corona = QRadialGradient(0.5, 0.5, 0.5)
        corona.setCoordinateMode(QRadialGradient.CoordinateMode.ObjectBoundingMode)
        corona.setColorAt(0.0, QColor(147, 51, 234, 100))
        corona.setColorAt(0.5, QColor(147, 51, 234, 30))
        corona.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(corona)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, size, size)
        painter.save()
        painter.translate(center_x, center_y)
        painter.rotate(-18)
        painter.translate(-center_x, -center_y)
        disk = QRadialGradient(0.46, 0.5, 0.5)
        disk.setCoordinateMode(QRadialGradient.CoordinateMode.ObjectBoundingMode)
        disk.setColorAt(0.0, QColor("#ffffff"))
        disk.setColorAt(0.12, QColor("#f472b6"))
        disk.setColorAt(0.28, QColor("#c084fc"))
        disk.setColorAt(0.55, QColor("#7928ca"))
        disk.setColorAt(0.85, QColor(121, 40, 202, 60))
        disk.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(disk)
        painter.drawEllipse(int(size * 0.04), int(size * 0.28), int(size * 0.92), int(size * 0.44))
        painter.restore()
        photon_ring = QRadialGradient(0.5, 0.5, 0.5)
        photon_ring.setCoordinateMode(QRadialGradient.CoordinateMode.ObjectBoundingMode)
        photon_ring.setColorAt(0.0, QColor("#ffffff"))
        photon_ring.setColorAt(0.4, QColor("#e0b0ff"))
        photon_ring.setColorAt(0.7, QColor("#a855f7"))
        photon_ring.setColorAt(1.0, QColor(147, 51, 234, 0))
        painter.setBrush(photon_ring)
        ring_radius = int(size * 0.28)
        painter.drawEllipse(int(center_x - ring_radius), int(center_y - ring_radius), ring_radius * 2, ring_radius * 2)
        painter.setBrush(QColor("#050508"))
        sphere_radius = int(size * 0.22)
        painter.drawEllipse(int(center_x - sphere_radius), int(center_y - sphere_radius), sphere_radius * 2, sphere_radius * 2)
        painter.end()
        return pixmap

    @asyncSlot()
    async def start_scan(self):
          target_url = self.url_input.text().strip()
          if not target_url:
              self.logger.log("warn", "Попытка запуска сканирования с пустым Target URL")
              return

          self.btn_scan.setEnabled(False)
          self.btn_scan.setText("Сканирование...")

          self.logger.log("info", f"Инициализация ядра сканирования для цели: {target_url}")

          if hasattr(self.manager, 'graph'):
              self.manager.graph.clear()
              self.logger.log("debug", "Граф топологии успешно очищен")

          self.crawler = WebantulaCrawler(
              base_url=target_url,
              manager=self.manager,
              signals=self.signal,
              analyzer=self.analyzer
          )

          try:
              await self.crawler.r.delete("visited")
              await self.crawler.r.delete("task_queue")
              await self.crawler.r.rpush("task_queue", target_url)
              self.logger.log("debug", "База Redis успешно подготовлена, целевой URL добавлен в очередь")
          except Exception as e:
              self.logger.log("fatal", f"Ошибка инициализации хранилища Redis: {e}")
              self.on_scan_finished()
              return

          asyncio.create_task(self.run_scaner(target_url))

    async def run_scaner(self, target_url):
           try:
               self.logger.log("info", "Запуск асинхронного пула воркеров (15 потоков curl_cffi)")
               async with AsyncSession(impersonate="chrome120", verify=False) as session:
                   async def wrapped_req(asset, **kwargs):
                       full_path = urljoin(target_url, asset)
                       self.logger.log("debug", f"Запрос ассета: {asset}")
                       return await session.get(full_path, **kwargs)

                   self.logger.log("debug", "Открытие сессии и загрузка поведенческих факторов сессии")
                   await self.crawler.behav.opensession(wrapped_req)

                   worker_tasks = [asyncio.create_task(self.crawler.run_worker(session)) for _ in range(15)]
                   await asyncio.gather(*worker_tasks, return_exceptions=True)

               await asyncio.sleep(0.5)
               self.logger.log("info", "Сбор ссылок завершен. Запуск корреляционного анализа уязвимостей (Analyzer)")
               self.crawler.manager.runAnlasysiss(self.crawler.analyzer)

               self.logger.log("info", "Экспорт статической WebGL карты в файл shademaper.html")
               await self.manager.save(self.crawler.base_url, "shademaper.html")
               self.logger.log("info", "Сканирование и генерация отчетов успешно завершены")

           except Exception as e:
               self.logger.log("error", f"Критический сбой в основном цикле сканера: {e}")
           finally:
               self.signal.scan_finished.emit()

    def update_ui(self, url, score, status):
            if url.lower().startswith(('javascript:', 'mailto:', 'tel:')):
                return
            self.logger.log("debug", f"Узел добавлен на холст: {url} | Score: {score}")
            self.render_graph()

    def render_graph(self):
            if not hasattr(self, 'manager') or not self.manager.graph.nodes:
                return

            js_nodes = []
            actual_start = self.crawler.base_url if (hasattr(self, 'crawler') and self.crawler) else None

            for node, data in self.manager.graph.nodes(data=True):
                short_label = node.replace("https://", "").replace("http://", "")
                if len(short_label) > 20:
                    short_label = short_label[:20] + '...'

                node_score = data.get('score', 0) if data else 0
                node_status = data.get('status', '') if data else ''

                if actual_start and node.rstrip('/') == actual_start.rstrip('/'):
                    color = '#ff0033'
                    webgl_size = 9.0
                elif node_score >= 80 or node_status == 'vulnerable':
                    color = '#ff0033'
                    webgl_size = 7.5
                elif node_score >= 50:
                    color = '#ffdc00'
                    webgl_size = 5.5
                else:
                    color = '#a855f7'
                    webgl_size = 3.0

                js_nodes.append({
                    'id': str(node),
                    'label': short_label,
                    'color': color,
                    'val': webgl_size
                })

            js_edges = []
            for u, v in self.manager.graph.edges():
                if not str(u).lower().startswith('javascript:') and not str(v).lower().startswith('javascript:'):
                    js_edges.append({"from": str(u), "to": str(v)})

            nodes_json = json.dumps(js_nodes, ensure_ascii=False)
            edges_json = json.dumps(js_edges, ensure_ascii=False)

            js_script = "updateGraph(%s, %s);" % (nodes_json, edges_json)
            self.view.page().runJavaScript(js_script)

    def on_scan_finished(self):
            self.log_area.appendPlainText("[*] Скан успешно завершен. Результаты сохранены.")
            self.btn_scan.setEnabled(True)
            self.btn_scan.setText("Начать сканирование")

    @asyncSlot()
    async def trigger_export(self):
        await self.manager.export_vulns()
        self.log_area.appendPlainText("[*] Экспорт сигнатур завершен.")
