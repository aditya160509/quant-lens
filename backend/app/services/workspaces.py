import uuid

# In-memory store
_workspaces = {
    "default": []
}

def get_workspaces(user_id="default"):
    return _workspaces.get(user_id, [])

def save_workspace(name, config, user_id="default"):
    if user_id not in _workspaces:
        _workspaces[user_id] = []
        
    ws = {
        "id": str(uuid.uuid4()),
        "name": name,
        "config": config # JSON blob of layout state
    }
    _workspaces[user_id].append(ws)
    return ws

def delete_workspace(ws_id, user_id="default"):
    workspaces = _workspaces.get(user_id, [])
    _workspaces[user_id] = [w for w in workspaces if w["id"] != ws_id]
    return True
