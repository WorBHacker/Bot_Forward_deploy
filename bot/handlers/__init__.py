from .master_channel import router as master_router
from .admin_panel import router as admin_router
from .chat_member import router as chat_member_router
from .control_panel import router as control_panel_router

__all__ = ["master_router", "admin_router", "chat_member_router", "control_panel_router"]
