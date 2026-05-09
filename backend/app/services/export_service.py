"""
Conversation Export
Export chat conversations in multiple formats
"""

import json
import logging
from typing import Optional
from datetime import datetime
from io import BytesIO

from app.db.postgres import get_db_cursor
from app.services.chat_service import get_thread_messages

logger = logging.getLogger(__name__)


def export_conversation_json(user_id: str, thread_id: str) -> Optional[dict]:
    """
    Export conversation as JSON.
    
    Args:
        user_id: User ID
        thread_id: Thread/conversation ID
        
    Returns:
        JSON dict with conversation data
    """
    try:
        # Get thread info
        with get_db_cursor() as cursor:
            cursor.execute("""
                select id, title, created_at, updated_at
                from public.chat_threads
                where id = %s and user_id = %s
            """, (thread_id, user_id))
            
            thread_row = cursor.fetchone()
            if not thread_row:
                logger.warning("Thread not found: thread_id=%s user_id=%s", thread_id, user_id)
                return None
        
        # Get messages
        messages = get_thread_messages(user_id, thread_id)
        
        # Build export
        export_data = {
            "metadata": {
                "thread_id": str(thread_row["id"]),
                "title": thread_row["title"],
                "created_at": thread_row["created_at"].isoformat() if thread_row["created_at"] else None,
                "updated_at": thread_row["updated_at"].isoformat() if thread_row["updated_at"] else None,
                "export_date": datetime.now().isoformat(),
                "message_count": len(messages),
            },
            "messages": [
                {
                    "id": str(msg.id),
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                    "attachments": [
                        {
                            "id": str(att.id),
                            "filename": att.filename,
                            "type": att.attachment_type,
                            "url": att.url or att.public_url,
                        }
                        for att in msg.attachments
                    ] if msg.attachments else [],
                }
                for msg in messages
            ],
        }
        
        logger.info(
            "Exported conversation as JSON: thread_id=%s messages=%d",
            thread_id,
            len(messages),
        )
        return export_data
    except Exception as e:
        logger.exception("Error exporting conversation as JSON: thread_id=%s", thread_id)
        return None


def export_conversation_markdown(user_id: str, thread_id: str) -> Optional[str]:
    """
    Export conversation as Markdown.
    
    Args:
        user_id: User ID
        thread_id: Thread/conversation ID
        
    Returns:
        Markdown string with conversation
    """
    try:
        # Get thread info
        with get_db_cursor() as cursor:
            cursor.execute("""
                select id, title, created_at
                from public.chat_threads
                where id = %s and user_id = %s
            """, (thread_id, user_id))
            
            thread_row = cursor.fetchone()
            if not thread_row:
                return None
        
        # Get messages
        messages = get_thread_messages(user_id, thread_id)
        
        # Build markdown
        lines = [
            f"# {thread_row['title']}",
            "",
            f"**Created:** {thread_row['created_at'].isoformat() if thread_row['created_at'] else 'N/A'}",
            f"**Messages:** {len(messages)}",
            "",
            "---",
            "",
        ]
        
        for msg in messages:
            role_display = "👤 You" if msg.role == "user" else "🤖 Assistant"
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S") if msg.created_at else "N/A"
            
            lines.extend([
                f"## {role_display} - {timestamp}",
                "",
                msg.content,
                "",
            ])
            
            # Add attachments if any
            if msg.attachments:
                lines.append("**Attachments:**")
                for att in msg.attachments:
                    lines.append(f"- [{att.filename}]({att.url or att.public_url})")
                lines.append("")
            
            lines.append("---")
            lines.append("")
        
        markdown = "\n".join(lines)
        
        logger.info(
            "Exported conversation as Markdown: thread_id=%s messages=%d",
            thread_id,
            len(messages),
        )
        return markdown
    except Exception as e:
        logger.exception("Error exporting conversation as Markdown: thread_id=%s", thread_id)
        return None


def export_conversation_csv(user_id: str, thread_id: str) -> Optional[str]:
    """
    Export conversation as CSV.
    
    Args:
        user_id: User ID
        thread_id: Thread/conversation ID
        
    Returns:
        CSV string with conversation
    """
    try:
        import csv
        from io import StringIO
        
        # Get messages
        messages = get_thread_messages(user_id, thread_id)
        
        # Build CSV
        output = StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(["Timestamp", "Role", "Message", "Attachments"])
        
        # Messages
        for msg in messages:
            timestamp = msg.created_at.isoformat() if msg.created_at else ""
            role = msg.role
            content = msg.content.replace("\n", " ")[:200]  # Truncate long messages
            
            attachments = ""
            if msg.attachments:
                attachments = "; ".join([att.filename for att in msg.attachments])
            
            writer.writerow([timestamp, role, content, attachments])
        
        csv_string = output.getvalue()
        
        logger.info(
            "Exported conversation as CSV: thread_id=%s messages=%d",
            thread_id,
            len(messages),
        )
        return csv_string
    except Exception as e:
        logger.exception("Error exporting conversation as CSV: thread_id=%s", thread_id)
        return None
