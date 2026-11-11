import re
from urllib.parse import urlparse
from core.config import ConfigsettingManager
import re
from urllib.parse import urlparse, urlunparse
import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

class PhantomNodedetector:
    def __init__(self, config):
        self.config = config

    def _normalize_url(self, url: str) -> str:
        if not url:
            return ""
        try:
            parsed = urlparse(url.strip())
            scheme = parsed.scheme.lower() or "http"
            netloc = parsed.netloc.lower()
            if not netloc and parsed.path and not parsed.path.startswith('/'):
                return url.strip().rstrip('/').lower()

            path = parsed.path.rstrip('/')
            if not path:
                path = ""

            if parsed.query:
                q_parsed = parse_qs(parsed.query, keep_blank_values=True)
                sorted_q = sorted(q_parsed.items())
                query = f"?{urlencode(sorted_q, doseq=True)}"
            else:
                query = ""

            return f"{scheme}://{netloc}{path}{query}"
        except Exception:
            return url.strip().rstrip('/').lower()

    def hidden_pathsearcher(self, base_url: str, found_nodes: list) -> set:
        pnodes = set()
        normalized_inputs = {self._normalize_url(node) for node in found_nodes if node}
        mutationsreplacer = self.config.get('phantom_detector.mutations', [{'find': 'profile', 'replace': 'settings'}])

        for node in found_nodes:
            if not node:
                continue
            norm_node = self._normalize_url(node)
            if "predicted_step=" in norm_node:
                continue

            for rule in mutationsreplacer:
                find_pattern = rule.get('find', '')
                replace_value = rule.get('replace', '')
                if not find_pattern:
                    continue
                try:
                    if re.search(find_pattern, norm_node, re.IGNORECASE):
                        potential = re.sub(find_pattern, replace_value, norm_node, flags=re.IGNORECASE)
                        norm_potential = self._normalize_url(potential)

                        if norm_potential not in normalized_inputs:
                            parsed_pot = urlparse(norm_potential)
                            q_parsed = parse_qs(parsed_pot.query, keep_blank_values=True)
                            q_parsed['predicted_step'] = ['1']

                            marked_url = urlunparse(parsed_pot._replace(query=urlencode(q_parsed, doseq=True)))
                            pnodes.add(self._normalize_url(marked_url))
                except re.error:
                    continue

        common_endpoints = self.config.get('phantom_detector.common_endpoints', [])
        unique_roots = set()

        for node in found_nodes:
            if not node or '/' not in node:
                continue
            try:
                parsed_node = urlparse(node)
                if not parsed_node.scheme or not parsed_node.netloc:
                    continue
                path_dir = os.path.dirname(parsed_node.path) if '.' in os.path.basename(parsed_node.path) else parsed_node.path.rstrip('/')
                root_url = urlunparse((parsed_node.scheme, parsed_node.netloc, path_dir, '', '', ''))
                unique_roots.add(root_url)
            except Exception:
                continue

        for root_path in unique_roots:
            p_root = root_path.rstrip('/')
            parsed_root = urlparse(p_root)
            path_segments = [seg for seg in parsed_root.path.split('/') if seg]

            if len(path_segments) > 3:
                continue

            for ce in common_endpoints:
                p_ce = ce.lstrip('/')
                potential_ce = self._normalize_url(f"{p_root}/{p_ce}")
                if potential_ce not in normalized_inputs:
                    pnodes.add(potential_ce)

        return pnodes


class Dpredictor:
    def __init__(self, config):
        self.config = config

    def _normalize_url(self, url: str) -> str:
        if not url:
            return ""
        try:
            parsed = urlparse(url.strip())
            scheme = parsed.scheme.lower() or "http"
            netloc = parsed.netloc.lower()
            if not netloc and parsed.path and not parsed.path.startswith('/'):
                return url.strip().rstrip('/').lower()

            path = parsed.path.rstrip('/')
            if not path:
                path = ""

            if parsed.query:
                q_parsed = parse_qs(parsed.query, keep_blank_values=True)
                sorted_q = sorted(q_parsed.items())
                query = f"?{urlencode(sorted_q, doseq=True)}"
            else:
                query = ""

            return f"{scheme}://{netloc}{path}{query}"
        except Exception:
            return url.strip().rstrip('/').lower()

    def predict_path(self, current_url: str) -> set:
        predictions = set()
        if not current_url or "predicted_step=" in str(current_url):
            return predictions

        norm_current = self._normalize_url(current_url)
        patterns = self.config.get('predictor.patterns', [r"api/v[0-9]+"])

        for pattern in patterns:
            try:
                if re.search(pattern, current_url, re.IGNORECASE):
                    parsed = urlparse(current_url)
                    if not parsed.scheme or not parsed.netloc:
                        continue

                    base = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"

                    if "api" in pattern.lower():
                        prediction = self._normalize_url(f"{base}/api-docs")
                    elif any(k in pattern.lower() for k in ["actuator", "metrics"]):
                        prediction = self._normalize_url(f"{base}/actuator/env")
                    elif any(k in pattern.lower() for k in ["swagger", "docs"]):
                        prediction = self._normalize_url(f"{base}/swagger-ui.html")
                    else:
                        prediction = self._normalize_url(f"{base}/admin")

                    if prediction != norm_current:
                        parsed_pred = urlparse(prediction)
                        q_parsed = parse_qs(parsed_pred.query, keep_blank_values=True)
                        q_parsed['predicted_step'] = ['1']

                        marked_pred = urlunparse(parsed_pred._replace(query=urlencode(q_parsed, doseq=True)))
                        predictions.add(self._normalize_url(marked_pred))
            except re.error as e:
                print(f" Ошибка {pattern}: {e}")
        return predictions
