import math
import re

class StructureParser:
    def __init__(self, config):
        self.config = config

    def parse(self, objects):
        # 各タギング処理を実行
        objects_with_color_tags = self._tag_objects_by_color(objects)
        objects_with_all_tags = self._tag_objects_by_hashtag(objects_with_color_tags)
        
        connections = self._extract_connections(objects)
        tagged_connections = self._tag_connections(connections)

        clusters = self._cluster_objects(objects_with_all_tags)
        
        return {
            "objects": objects_with_all_tags,
            "clusters": clusters,
            "connections": tagged_connections,
        }

    def _tag_objects_by_color(self, objects):
        color_tags_config = self.config.get("color_tags", {})
        for obj in objects:
            if "tags" not in obj:
                obj["tags"] = []
            color_data = obj.get("color")
            if color_data and isinstance(color_data, dict):
                r, g, b, a = color_data.values()
                hex_color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
                if hex_color in color_tags_config:
                    obj["tags"].append(color_tags_config[hex_color])
        return objects

    def _tag_objects_by_hashtag(self, objects):
        hashtags_config = self.config.get("figma_semantics", {}).get("hashtags", {})
        for obj in objects:
            if "semantic_tags" not in obj:
                obj["semantic_tags"] = []
            text = obj.get("text", "")
            if text:
                found_hashtags = re.findall(r"(#[a-zA-Z0-9_]+)", text)
                for hashtag in found_hashtags:
                    if hashtag in hashtags_config:
                        obj["semantic_tags"].append(hashtags_config[hashtag])
        return objects

    def _tag_connections(self, connections):
        connector_colors_config = self.config.get("figma_semantics", {}).get("connector_colors", {})
        for conn in connections:
            if "semantic_tags" not in conn:
                conn["semantic_tags"] = []
            color_data = conn.get("color")
            if color_data and isinstance(color_data, dict):
                r, g, b, a = color_data.values()
                hex_color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
                if hex_color in connector_colors_config:
                    conn["semantic_tags"].append(connector_colors_config[hex_color])
        return connections

    def _cluster_objects(self, objects):
        threshold = self.config.get("clustering_threshold", 100)
        nodes = [obj for obj in objects if obj.get("type") != "CONNECTOR" and obj.get("position")]
        clusters = []
        visited = set()

        for i in range(len(nodes)):
            if i in visited:
                continue
            current_cluster = []
            self._dfs(i, nodes, visited, current_cluster, threshold)
            if current_cluster:
                clusters.append(current_cluster)
        return clusters

    def _dfs(self, node_idx, nodes, visited, current_cluster, threshold):
        visited.add(node_idx)
        current_cluster.append(nodes[node_idx])
        for i in range(len(nodes)):
            if i not in visited and self._distance(nodes[node_idx], nodes[i]) < threshold:
                self._dfs(i, nodes, visited, current_cluster, threshold)

    def _distance(self, node1, node2):
        pos1 = node1["position"]
        pos2 = node2["position"]
        if not pos1 or not pos2:
            return float('inf')
        return math.sqrt((pos1["x"] - pos2["x"])**2 + (pos1["y"] - pos2["y"])**2)

    def _extract_connections(self, objects):
        connections = []
        for obj in objects:
            if obj.get("type") == "CONNECTOR":
                start = obj.get("connectorStart")
                end = obj.get("connectorEnd")
                # Make a copy to avoid modifying the original object list
                conn_data = obj.copy()
                conn_data["start_node_id"] = start
                conn_data["end_node_id"] = end
                connections.append(conn_data)
        return connections