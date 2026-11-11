import re
import networkx as nx
from .config import ConfigsettingManager

class Analyzer:
    def __init__(self) -> None:
        self.config = ConfigsettingManager()

    def calc_score(self, url: str) -> int:
        score = 0
        rules = self.config.get('analyzer.rules', [
            {'pattern': '(admin|backend)', 'weight': 100},
            {'pattern': r'api/v[0-9]+', 'weight': 70}
        ])
        for rule in rules:
            pattern = rule.get('pattern', '')
            weight = rule.get('weight', 0)
            try:
                if re.search(pattern, url, re.IGNORECASE):
                    score += weight
            except re.error as e:
                print(f"[-] Ошибка в синтаксисе регулярного выражения {pattern}: {e}")

        return min(score, 100)

    @staticmethod
    def attackPath(config: ConfigsettingManager, graph: nx.DiGraph, target_url: str):
        start_node = config.get('scaner.start_url', 'https://example.com')
        try:
            paths = list(nx.all_simple_paths(graph, source=start_node, target=target_url))
            return sorted(paths, key=len)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []
        except Exception:
            return []
