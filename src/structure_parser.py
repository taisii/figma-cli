import math

class StructureParser:
    def __init__(self, config):
        self.config = config

    def parse(self, objects):
        tagged_objects = self._tag_objects(objects)
        clusters = self._cluster_objects(tagged_objects)
        connections = self._extract_connections(objects)
        return {
            "objects": tagged_objects,
            "clusters": clusters,
            "connections": connections,
        }

    def _tag_objects(self, objects):
        color_map = {v: k for k, v in self.config["color_tags"].items()}
        for obj in objects:
            color_data = obj.get("color")
            if color_data and isinstance(color_data, dict):
                r, g, b, a = color_data.values()
                hex_color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
                if hex_color in self.config["color_tags"]:
                    obj["tag"] = self.config["color_tags"][hex_color]
        return objects

    def _cluster_objects(self, objects):
        threshold = self.config["clustering_threshold"]
        nodes = [obj for obj in objects if obj["type"] != "CONNECTOR" and obj.get("position")]
        clusters = []
        visited = set()

        for i in range(len(nodes)):
            if i in visited:
                continue
            current_cluster = []
            self._dfs(i, nodes, visited, current_cluster, threshold)
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
        return math.sqrt((pos1["x"] - pos2["x"])**2 + (pos1["y"] - pos2["y"])**2)

    def _extract_connections(self, objects):
        connections = []
        for obj in objects:
            if obj["type"] == "CONNECTOR":
                start = obj.get("connectorStart")
                end = obj.get("connectorEnd")
                if start and end:
                    connections.append((start, end))
        return connections
