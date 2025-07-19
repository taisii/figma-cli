class DiffEngine:

    @staticmethod
    def detect_changes(old_objects, new_objects):
        old_map = {obj["id"]: obj for obj in old_objects}
        new_map = {obj["id"]: obj for obj in new_objects}

        added = [obj for obj in new_objects if obj["id"] not in old_map]
        deleted = [obj for obj in old_objects if obj["id"] not in new_map]
        modified = []

        for obj_id, new_obj in new_map.items():
            if obj_id in old_map:
                old_obj = old_map[obj_id]
                if new_obj != old_obj:
                    modification = {"id": obj_id}
                    if new_obj.get("text") != old_obj.get("text"):
                        modification["old_text"] = old_obj.get("text")
                        modification["new_text"] = new_obj.get("text")
                    # 他の変更（位置、色など）もここに追加できる
                    modified.append(modification)

        return {"added": added, "deleted": deleted, "modified": modified}
