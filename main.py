from fastapi import FastAPI, HTTPException
from atlassian import Jira
from typing import Dict, Any
import os

app = FastAPI()
jira = Jira(
    url=os.environ["JIRA_URL"],
    username=os.environ["JIRA_USERNAME"],
    password=os.environ["JIRA_API_TOKEN"]
)

@app.get("/jira/tasks")
async def get_tasks():
    try:
        # Get all tasks assigned to the user
        jql = f'assignee = currentUser() ORDER BY updated DESC'
        issues = jira.jql(jql)
        return {
            "status": "success",
            "tasks": [
                {
                    "key": issue["key"],
                    "summary": issue["fields"]["summary"],
                    "status": issue["fields"]["status"]["name"],
                    "priority": issue["fields"]["priority"]["name"],
                    "updated": issue["fields"]["updated"]
                }
                for issue in issues["issues"]
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/jira/tasks/{task_id}/comment")
async def add_comment(task_id: str, comment: Dict[str, Any]):
    try:
        jira.add_comment(task_id, comment["body"])
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
