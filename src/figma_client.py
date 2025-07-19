import os
import requests

class FigmaClient:
    def __init__(self):
        self.api_token = os.getenv("FIGMA_API_TOKEN")
        self.board_url = os.getenv("FIGJAM_BOARD_URL")
        if not self.api_token or not self.board_url:
            raise ValueError("FIGMA_API_TOKEN and FIGJAM_BOARD_URL must be set in .env file")

    def get_figma_objects(self):
        file_key = self.board_url.split("/")[-2]
        api_url = f"https://api.figma.com/v1/files/{file_key}"
        headers = {"X-Figma-Token": self.api_token}
        response = requests.get(api_url, headers=headers)

        if response.status_code != 200:
            raise Exception(f"Figma API request failed with status code {response.status_code}")

        data = response.json()
        flat_list = []

        def extract_children(node):
            if 'children' in node:
                for child in node['children']:
                    item = {
                        "id": child.get("id"),
                        "text": child.get("characters"),
                        "position": child.get("absoluteBoundingBox"),
                        "type": child.get("type"),
                        "connectorStart": child.get("connectorStart", {}).get("endpointNodeId"),
                        "connectorEnd": child.get("connectorEnd", {}).get("endpointNodeId"),
                    }
                    fills_data = child.get("fills")
                    if fills_data and isinstance(fills_data, list) and len(fills_data) > 0:
                        first_fill = fills_data[0]
                        if isinstance(first_fill, dict) and "color" in first_fill:
                            item["color"] = first_fill["color"]
                        else:
                            item["color"] = None
                    else:
                        item["color"] = None
                    flat_list.append(item)
                    extract_children(child) # Recursively call for nested children

        if 'document' in data:
            extract_children(data['document'])

        return flat_list
