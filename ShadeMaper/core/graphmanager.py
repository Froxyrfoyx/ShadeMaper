import json
import networkx as nx
import asyncio
import aiofiles
import json
import networkx as nx
import asyncio
import aiofiles

class GraphManager:
    def __init__(self):
        self.graph = nx.DiGraph()
        self._lock = asyncio.Lock()

    async def add_node(self, n_id, label=None, shape="dot", color='#97c2fc', score: int = 0, status: str = "safe"):
        async with self._lock:
            if n_id not in self.graph:
                self.graph.add_node(n_id, label=label if label else n_id, color=color, shape=shape, score=score, status=status)

    async def add_edge(self, source, to, **options):
        async with self._lock:
            if source not in self.graph:
                self.graph.add_node(source, label=source, color='#97c2fc', shape="dot", score=0, status="safe")
            if to not in self.graph:
                self.graph.add_node(to, label=to, color='#97c2fc', shape="dot", score=0, status="safe")
            self.graph.add_edge(source, to)

    def find_shorttestpath(self, start_node, target_node):
        try:
            if not self.graph.has_node(start_node) or not self.graph.has_node(target_node):
                return None
            path = nx.shortest_path(self.graph, source=start_node, target=target_node)
            return path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    async def save(self, start_node, filename="shade_map.html", json_filename="shade_map.json"):
        async with self._lock:
            actual_start = None
            if start_node:
                start_clean = start_node.rstrip('/')
                for n in self.graph.nodes():
                    if n.rstrip('/') == start_clean:
                        actual_start = n
                        break
            critical_nodes = [n for n, d in self.graph.nodes(data=True) if d.get('score', 0) >= 80 or d.get('status') == 'vulnerable']
            attack_edges = set()
            attack_nodes = set()
            if actual_start and critical_nodes:
                for target in critical_nodes:
                    path = self.find_shorttestpath(actual_start, target)
                    if path:
                        for node_id in path:
                            attack_nodes.add(node_id)
                        for i in range(len(path) - 1):
                            attack_edges.add((path[i], path[i+1]))
            for node, d in self.graph.nodes(data=True):
                self.graph.nodes[node]['label'] = str(node)

                if node == actual_start:
                    self.graph.nodes[node]['color'] = "#ff0033"
                    self.graph.nodes[node]['size'] = 35
                    self.graph.nodes[node]['shape'] = 'diamond'
                elif d.get('score', 0) >= 80 or d.get('status') == 'vulnerable':
                    self.graph.nodes[node]['color'] = "#ff0033"
                    self.graph.nodes[node]['size'] = 30
                    self.graph.nodes[node]['shape'] = 'diamond'
                elif node in attack_nodes:
                    self.graph.nodes[node]['color'] = "#ff0033"
                    self.graph.nodes[node]['size'] = 22
                    self.graph.nodes[node]['shape'] = 'dot'
                else:
                    self.graph.nodes[node]['color'] = 'rgba(168, 85, 247, 0.4)'
                    self.graph.nodes[node]['size'] = 14
                    self.graph.nodes[node]['shape'] = 'dot'

            for u, v in self.graph.edges():
                if (u, v) in attack_edges:
                    self.graph.edges[u, v]['color'] = '#ff0033'
                    self.graph.edges[u, v]['width'] = 3.5
                    self.graph.edges[u, v]['arrows'] = 'to'
                else:
                    self.graph.edges[u, v]['color'] = 'rgba(168, 85, 247, 0.08)'
                    self.graph.edges[u, v]['width'] = 1
                    self.graph.edges[u, v]['arrows'] = 'to'

            nodes_data = []
            for node, d in self.graph.nodes(data=True):
                webgl_size = 9 if d['shape'] == 'diamond' else (5.5 if d['size'] == 22 else 2.5)
                nodes_data.append({
                    "id": str(node),
                    "label": d['label'],
                    "color": d['color'],
                    "val": webgl_size
                })

            links_data = []
            for u, v, d in self.graph.edges(data=True):
                links_data.append({
                    "source": str(u),
                    "target": str(v),
                    "color": d['color'],
                    "width": d['width']
                })

                graph_payload = {"nodes": nodes_data, "links": links_data}
                graph_json = json.dumps(graph_payload, ensure_ascii=False)

                async with aiofiles.open(json_filename, "w", encoding="utf-8") as f:
                            await f.write(graph_json)

                html_template = f"""<!DOCTYPE html>
               <html>
               <head>
                   <meta charset="utf-8">
                   <style>
                       body, html, #graph-container {{
                           width: 100%; height: 100%; margin: 0; padding: 0; overflow: hidden; background: #0c0c0f; position: relative;
                           font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                       }}
                       #graph, #canvas-labels {{
                           position: absolute; top: 0; left: 0; width: 100%; height: 100%;
                       }}
                       #canvas-labels {{
                           pointer-events: none; z-index: 10;
                           will-change: transform;
                       }}
                   </style>
               </head>
               <body>
                   <div id="graph-container">
                       <div id="graph"></div>
                       <canvas id="canvas-labels"></canvas>
                   </div>

                   <script src="vivagraph.js"></script>
                   <script>
                       console.log("DIAG: Запуск графа премиум-уровня");
                       const gData = {graph_json};

                       const graph = Viva.Graph.graph();

                       if (gData && gData.nodes) {{
                           gData.nodes.forEach(node => {{
                               graph.addNode(node.id, {{
                                   label: node.label,
                                   color: node.color,
                                   val: node.val
                               }});
                           }});
                       }}

                       if (gData && gData.links) {{
                           gData.links.forEach(link => {{
                               graph.addLink(link.source, link.target, {{
                                   color: link.color
                               }});
                           }});
                       }}

                       const layout = Viva.Graph.Layout.forceDirected(graph, {{
                           springLength: 350,
                           springCoeff: 0.00008,
                           gravity: -8.0,
                           dragCoeff: 0.04,
                           theta: 0.6
                       }});

                       layout.isStable = function() {{
                           return false;
                       }};

                       const webglGraphics = Viva.Graph.View.webglGraphics();

                       webglGraphics.node(function(node) {{
                           let colorHex = 0xa855f7ff;
                           if (node.data.color === '#ff0033') {{
                               colorHex = 0xff0033ff;
                           }} else if (node.data.color && node.data.color.includes('rgba')) {{
                               colorHex = 0xa855f7bb;
                           }}
                           const size = (node.data.val || 2.5) * 4.5;
                           return Viva.Graph.View.webglSquare(size, colorHex);
                       }});

                       webglGraphics.link(function(link) {{
                           let colorHex = 0xffffff0a;
                           if (link.data.color === '#ff0033') {{
                               colorHex = 0xff003333;
                           }}
                           return Viva.Graph.View.webglLine(colorHex);
                       }});

                       const renderer = Viva.Graph.View.renderer(graph, {{
                           container: document.getElementById('graph'),
                           layout: layout,
                           graphics: webglGraphics,
                           interactive: 'node'
                       }});
                       renderer.run();

                       const labelCanvas = document.getElementById('canvas-labels');
                       const ctx = labelCanvas.getContext('2d');

                       function resizeCanvas() {{
                           labelCanvas.width = window.innerWidth;
                           labelCanvas.height = window.innerHeight;
                           drawLabels();
                       }}
                       window.addEventListener('resize', resizeCanvas);
                       resizeCanvas();

                       function cleanUrlLabel(url, scale) {{
                           if (!url) return "";

                           let clean = url.replace(/^(https?:\\/\\/)?(www\\.)?([^\\/]+)/, "");

                           if (clean === "" || clean === "/") {{
                               return url.replace(/^(https?:\\/\\/)?(www\\.)?/, "");
                           }}

                           let maxChars = 28;
                           if (scale < 0.55) maxChars = 10;
                           else if (scale < 0.8) maxChars = 18;

                           if (clean.length > maxChars) {{
                               return clean.substring(0, maxChars - 3) + "...";
                           }}
                           return clean;
                       }}

                       function drawLabels() {{
                           ctx.clearRect(0, 0, labelCanvas.width, labelCanvas.height);

                           if (typeof renderer.getTransform !== 'function') return;

                           const transform = renderer.getTransform();
                           if (!transform || typeof transform.scale === 'undefined') return;

                           const scale = transform.scale;
                           const offsetX = transform.offsetX;
                           const offsetY = transform.offsetY;

                           if (scale > 0.35) {{
                               graph.forEachNode(function(node) {{
                                   let pos = null;

                                   if (typeof layout.getNodePosition === 'function') {{
                                       pos = layout.getNodePosition(node.id);
                                   }}

                                   if (!pos && typeof webglGraphics.getNodeUI === 'function') {{
                                       const nodeUI = webglGraphics.getNodeUI(node.id);
                                       if (nodeUI && nodeUI.position) pos = nodeUI.position;
                                   }}

                                   if (!pos) return;

                                   const screenX = pos.x * scale + offsetX;
                                   const screenY = pos.y * scale + offsetY;

                                   if (screenX >= 0 && screenX <= labelCanvas.width && screenY >= 0 && screenY <= labelCanvas.height) {{
                                       const size = (node.data.val || 2.5) * 4.5;
                                       const textPaddingY = (size / 2) * scale + 8;

                                       const rawLabel = node.data.label || node.id;
                                       const finalLabel = cleanUrlLabel(rawLabel, scale);

                                       ctx.font = "normal 11px monospace";
                                       ctx.textAlign = 'center';
                                       ctx.textBaseline = 'top';

                                       const textWidth = ctx.measureText(finalLabel).width;
                                       const rectWidth = textWidth + 8;
                                       const rectHeight = 16;

                                       ctx.fillStyle = 'rgba(12, 12, 15, 0.75)';
                                       ctx.fillRect(screenX - rectWidth / 2, screenY + textPaddingY - 2, rectWidth, rectHeight);

                                       ctx.fillStyle = '#ffffff';
                                       ctx.fillText(finalLabel, screenX, screenY + textPaddingY);
                                   }}
                               }});
                           }}
                       }}

                       renderer.on('scale', drawLabels);
                       renderer.on('drag', drawLabels);

                       if (typeof renderer.onFrame === 'function') {{
                           renderer.onFrame(drawLabels);
                       }}

                       layout.on('step', drawLabels);

                       function globalAnimationLoop() {{
                           drawLabels();
                           requestAnimationFrame(globalAnimationLoop);
                       }}
                       requestAnimationFrame(globalAnimationLoop);
                   </script>
               </body>
               </html>
               """




                async with aiofiles.open(filename, "w", encoding="utf-8") as f:
                            await f.write(html_template)
                            print("Файл успешно сохранился")

    async def export_vulns(self, filename='vulns.json'):
        danger_nodes = [{
            'url': str(node), **data
        } for node, data in self.graph.nodes(data=True)
            if data.get('score', 0) >= 50
        ]
        async with aiofiles.open(filename, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(danger_nodes, indent=4, ensure_ascii=False))
        print(f"Экспорт завершен : {len(danger_nodes)}")

    def runAnlasysiss(self, analyzer):
        for node in list(self.graph.nodes()):
            analyzer.calc_score(node)
