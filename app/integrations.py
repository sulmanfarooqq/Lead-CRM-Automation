import smtplib, json
from email.message import EmailMessage
import httpx
from app.config import get_settings

def monday_sync(lead):
    s = get_settings()
    if not s.monday_api_token or not s.monday_board_id: return False, "Monday.com is not configured"
    cols = {
      s.monday_email_column_id: {"email":lead["email"],"text":lead["email"]} if lead.get("email") else None,
      s.monday_phone_column_id:lead.get("phone"), s.monday_property_type_column_id:lead.get("property_type"),
      s.monday_budget_column_id:lead.get("budget_raw"), s.monday_location_column_id:lead.get("preferred_location"),
      s.monday_timeline_column_id:lead.get("buying_timeline"),
      s.monday_message_column_id:{"text":lead["message"]} if lead.get("message") else None,
      s.monday_priority_column_id:{"label":lead.get("priority")},
      s.monday_stage_column_id:{"label":"New"},
      s.monday_followup_column_id:{"date":lead.get("follow_up_due","")[:10]}
    }
    values = {k:v for k,v in cols.items() if k and v is not None}
    query = """mutation ($board: ID!, $group: String, $name: String!, $values: JSON!) {
      create_item(board_id:$board,group_id:$group,item_name:$name,column_values:$values,create_labels_if_missing:true){id} }"""
    try:
        r = httpx.post(s.monday_api_url,headers={"Authorization":s.monday_api_token,"API-Version":"2025-10"},
          json={"query":query,"variables":{"board":str(s.monday_board_id),"group":s.monday_group_id or None,
          "name":lead["full_name"],"values":json.dumps(values)}},timeout=20)
        r.raise_for_status()
        body = r.json()
        if body.get("errors"): return False,str(body["errors"])
        return True,str(body["data"]["create_item"]["id"])
    except Exception as exc: return False,str(exc)

def notify_team(lead, duplicate=False):
    s = get_settings()
    subject = f"[{lead['priority'].upper()}] {'Repeat enquiry' if duplicate else 'New lead'}: {lead['full_name']}"
    body = (f"Lead: {lead['full_name']}\nPriority: {lead['priority']}\nAssigned to: {lead.get('assigned_to')}\n"
      f"Email: {lead.get('email')}\nPhone: {lead.get('phone')}\nBudget: {lead.get('budget_raw')}\n"
      f"Location: {lead.get('preferred_location')}\nTimeline: {lead.get('buying_timeline')}\n"
      f"Follow-up due: {lead.get('follow_up_due')}\n\nThe buyer has not been contacted by this system.")
    email_sent = slack_sent = False
    recipient = lead.get("assigned_email") or s.sales_rep_email
    if s.smtp_host and s.smtp_from_email and recipient:
        try:
            msg=EmailMessage(); msg["Subject"]=subject; msg["From"]=s.smtp_from_email; msg["To"]=recipient; msg.set_content(body)
            with smtplib.SMTP(s.smtp_host,s.smtp_port,timeout=15) as server:
                if s.smtp_use_tls: server.starttls()
                if s.smtp_username: server.login(s.smtp_username,s.smtp_password)
                server.send_message(msg)
            email_sent=True
        except Exception: pass
    if s.slack_webhook_url:
        try:
            r=httpx.post(s.slack_webhook_url,json={"text":f"*{subject}*\n{body}"},timeout=10); r.raise_for_status(); slack_sent=True
        except Exception: pass
    return {"email_sent":email_sent,"slack_sent":slack_sent}
