"""Tools grouped per agent. Step 5 imports these lists."""
from app.tools.kb_tools import search_knowledge_base
from app.tools.order_tools import get_order_status, process_refund, update_record
from app.tools.email_tools import send_email
from app.tools.ticket_tools import escalate_to_human, check_ticket_status
from app.tools.verify_tools import request_verification, confirm_verification

KNOWLEDGE_TOOLS = [search_knowledge_base]
ACTION_TOOLS = [request_verification, confirm_verification, get_order_status, process_refund,
                update_record, check_ticket_status]
EMAIL_TOOLS = [send_email]
ESCALATION_TOOLS = [escalate_to_human]
