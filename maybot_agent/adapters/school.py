from .base import base_project

def adapt(project: dict) -> dict:
    data = base_project(project)
    metrics = data.get("metrics", {})
    metrics.update(project.get("metrics", {}))
    data["metrics"] = metrics
    return data
