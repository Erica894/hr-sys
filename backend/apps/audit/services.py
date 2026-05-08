import json
import uuid
from django.db import connection


def log_action(event: str, actor, resource_type: str, resource_id: int,
               before: dict, after: dict, ip: str = "", request_id: str = "",
               actor_role: str = "") -> None:
    if not request_id:
        request_id = str(uuid.uuid4())
    actor_id = actor.id if actor and hasattr(actor, "id") else None
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO audit.audit_log
              (actor_id, actor_role, action, resource_type, resource_id, before, after, ip, request_id)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
            """,
            [actor_id, actor_role, event, resource_type, resource_id,
             json.dumps(before or {}), json.dumps(after or {}), ip or None, request_id],
        )
