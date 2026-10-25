# routers/webhooks.py
from datetime import UTC, datetime, timedelta

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from models.webhook import CapturedWebhook, WebhookSession
from schemas.webhook import (
    CapturedWebhookResponse,
    SessionCreateResponse,
    WebhookCatchResponse,
)

router = APIRouter()


# --- Gestionnaire WebSocket ---
class WebhookConnectionManager:
    def __init__(self):
        self.active_rooms: Dict[str, List[WebSocket]] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        if session_id not in self.active_rooms:
            self.active_rooms[session_id] = []
        self.active_rooms[session_id].append(websocket)

    def disconnect(self, session_id: str, websocket: WebSocket):
        if session_id in self.active_rooms:
            if websocket in self.active_rooms[session_id]:
                self.active_rooms[session_id].remove(websocket)
            if not self.active_rooms[session_id]:
                del self.active_rooms[session_id]

    async def broadcast(self, session_id: str, payload: dict):
        if session_id in self.active_rooms:
            for connection in self.active_rooms[session_id]:
                try:
                    await connection.send_json(payload)
                except Exception:
                    pass


manager = WebhookConnectionManager()


# --- Routes HTTP ---


@router.post(
    "/sessions",
    response_model=SessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session():
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=24)
    session = await WebhookSession.create(expires_at=expires_at)
    return SessionCreateResponse(session_id=session.id, expires_at=session.expires_at)


@router.get(
    "/sessions/{session_id}/requests",
    response_model=list[CapturedWebhookResponse],
)
async def list_requests(session_id: str):
    session = await WebhookSession.get_or_none(id=session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session inexistante ou expirée.",
        )

    # Tortoise récupère les objets et Pydantic les sérialise automatiquement
    requests = await CapturedWebhook.filter(session=session).limit(100)
    return requests


@router.api_route(
    "/catch/{session_id}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
    response_model=WebhookCatchResponse,
)
async def catch_webhook(session_id: str, request: Request):
    session = await WebhookSession.get_or_none(id=session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Point de terminaison webhook inexistant ou expiré.",
        )

    body_bytes = await request.body()
    body_str = None
    if body_bytes:
        try:
            body_str = body_bytes.decode("utf-8")
        except UnicodeDecodeError:
            body_str = f"<binaire : {len(body_bytes)} octets>"

    record = await CapturedWebhook.create(
        session=session,
        method=request.method,
        url_path=str(request.url.path),
        headers=dict(request.headers.items()),
        query_params=dict(request.query_params.items()),
        body=body_str,
        ip_address=request.client.host if request.client else "unknown",
    )

    payload = {
        "id": record.id,
        "method": record.method,
        "url_path": record.url_path,
        "headers": record.headers,
        "query_params": record.query_params,
        "body": record.body,
        "ip_address": record.ip_address,
        "created_at": record.created_at.isoformat(),
    }
    await manager.broadcast(session_id, payload)

    return WebhookCatchResponse(captured_id=record.id)


@router.websocket("/ws/{session_id}")
async def websocket_webhook(websocket: WebSocket, session_id: str):
    await manager.connect(session_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)
