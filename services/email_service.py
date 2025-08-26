import email
import imaplib
import json
import os
import smtplib
import uuid
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, List, Optional

import core.env
from agent.agent import Agent
from core.config import EmailConfig, load_config
from core.errors import ConfigError, ExternalToolError
from core.logging import logger

# Base directory for artifacts
BASE_ARTIFACTS_DIR = Path("artifacts")

class EmailService:
    def __init__(self, account_type: str):
        """Initializes the email service for a specific account type (e.g., 'gmail')."""
        self.config = load_config('email', EmailConfig)
        if not hasattr(self.config, account_type):
            raise ConfigError(f"Account type '{account_type}' not in email config.")

        self.account_config = getattr(self.config, account_type)
        self.email_user = core.env.EMAIL_USER
        self.email_pass = core.env.EMAIL_PASS

        if not self.email_user or not self.email_pass:
            raise ConfigError(f"Email credentials (e.g., GMAIL_USER, GMAIL_PASS) not set in environment.")

        self.imap_server = self.account_config['imap_host']
        self.smtp_server = self.account_config['smtp_host']
        self.smtp_port = self.account_config['smtp_port']
        self.drafts_dir = BASE_ARTIFACTS_DIR / "email_drafts"
        self.drafts_dir.mkdir(parents=True, exist_ok=True)

    def _connect_imap(self):
        """Connects to the IMAP server and logs in."""
        try:
            mail = imaplib.IMAP4_SSL(self.imap_server)
            mail.login(self.email_user, self.email_pass)
            return mail
        except imaplib.IMAP4.error as e:
            # This is a specific exception for IMAP errors (e.g., login failure)
            raise ExternalToolError(f"IMAP connection failed: {e}")

    def list_unread_emails(self) -> List[Dict[str, str]]:
        """Retrieves a list of unread emails."""
        try:
            mail = self._connect_imap()
        except ExternalToolError as e:
            logger.error(f"Cannot list unread emails, connection failed: {e}")
            return []

        mail.select('inbox')
        status, messages = mail.search(None, 'UNSEEN')
        if status != 'OK':
            logger.error("Fehler beim Suchen nach ungelesenen E-Mails.")
            mail.logout()
            return []

        unread_emails = []
        for num in messages[0].split():
            status, data = mail.fetch(num, '(RFC822)')
            if status == 'OK':
                msg = email.message_from_bytes(data[0][1])
                subject, encoding = email.header.decode_header(msg['subject'])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding if encoding else 'utf-8')

                sender, encoding = email.header.decode_header(msg['from'])[0]
                if isinstance(sender, bytes):
                    sender = sender.decode(encoding if encoding else 'utf-8')

                unread_emails.append({
                    'id': num.decode(),
                    'from': sender,
                    'subject': subject
                })

        mail.logout()
        return unread_emails

    def fetch_email(self, email_id: str) -> Optional[EmailMessage]:
        """Fetches a specific email by its ID."""
        try:
            mail = self._connect_imap()
        except ExternalToolError as e:
            logger.error(f"Cannot fetch email, connection failed: {e}")
            return None

        try:
            mail.select('inbox')
            status, data = mail.fetch(email_id, '(RFC822)')
            if status == 'OK':
                return email.message_from_bytes(data[0][1])
            else:
                logger.error(f"Could not fetch email with ID {email_id}.")
                return None
        finally:
            mail.logout()

    def get_draft(self, draft_id: str) -> Optional[Dict]:
        """Loads a draft's content from a file."""
        draft_path = self.drafts_dir / draft_id
        if not draft_path.exists():
            return None
        with open(draft_path, "r") as f:
            return json.load(f)

    def _get_email_body(self, msg: EmailMessage) -> str:
        """Extracts the text body from an EmailMessage."""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                cdispo = str(part.get('Content-Disposition'))
                if ctype == 'text/plain' and 'attachment' not in cdispo:
                    body = part.get_payload(decode=True)
                    return body.decode()
        else:
            body = msg.get_payload(decode=True)
            return body.decode()
        return ""

    async def draft_reply(self, original_email_id: str, agent: Agent, reply_style: str = "formal") -> str:
        """
        Generates a reply draft using the provided agent, saves it, and returns the draft ID.
        """
        original_msg = self.fetch_email(original_email_id)
        if not original_msg:
            raise ExternalToolError(f"Original email '{original_email_id}' not found.")

        # Extract content and create a prompt for the agent
        original_body = self._get_email_body(original_msg)
        sender = original_msg['From']
        subject = original_msg['subject']

        prompt_history = [
            {"role": "system", "content": "Du bist ein hilfreicher Assistent. Deine Aufgabe ist es, E-Mail-Antworten zu verfassen."},
            {"role": "user", "content": f"Bitte verfasse eine {reply_style}e Antwort auf die folgende E-Mail von '{sender}' mit dem Betreff '{subject}':\n\n---\n{original_body}\n---"}
        ]

        # Generate the reply body using the agent
        llm_body_text = await agent.execute_prompt(prompt_history)
        # Simple conversion to HTML
        llm_body_html = f"<p>{llm_body_text.replace('\n', '<br>')}</p>"

        draft_id = f"draft_{uuid.uuid4()}.json"
        draft_content = {
            "original_email_id": original_email_id,
            "to": original_msg['Reply-To'] or original_msg['From'],
            "cc": "",
            "bcc": "",
            "subject": f"Re: {original_msg['subject']}",
            "body_text": llm_body_text,
            "body_html": llm_body_html,
            "attachments": []
        }

        draft_path = self.drafts_dir / draft_id
        with open(draft_path, "w") as f:
            json.dump(draft_content, f, indent=2)

        logger.info(f"Saved email draft {draft_id} to {draft_path.resolve()}")
        return draft_id

    async def edit_draft(self, original_draft_id: str, edit_instruction: str, agent: Agent) -> str:
        """Edits an existing draft based on user instructions."""
        original_draft = self.get_draft(original_draft_id)
        if not original_draft:
            raise FileNotFoundError(f"Original draft '{original_draft_id}' not found.")

        # Create a new prompt for the agent
        prompt_history = [
            {"role": "system", "content": "Du bist ein hilfreicher Assistent. Deine Aufgabe ist es, E-Mail-Entwürfe basierend auf Anweisungen zu überarbeiten."},
            {"role": "user", "content": f"Hier ist der vorherige Entwurf:\n\n---\n{original_draft['body_text']}\n---\n\nBitte überarbeite ihn mit der folgenden Anweisung: '{edit_instruction}'"}
        ]

        # Generate the new reply body
        new_body_text = await agent.execute_prompt(prompt_history)
        new_body_html = f"<p>{new_body_text.replace('\n', '<br>')}</p>"

        # Create a new draft file
        new_draft_id = f"draft_{uuid.uuid4()}.json"
        new_draft_content = {
            **original_draft, # Copy over old details like 'to', 'subject' etc.
            "body_text": new_body_text,
            "body_html": new_body_html,
        }

        new_draft_path = self.drafts_dir / new_draft_id
        with open(new_draft_path, "w") as f:
            json.dump(new_draft_content, f, indent=2)

        logger.info(f"Saved edited draft {new_draft_id}, based on {original_draft_id}.")
        return new_draft_id

    def confirm_and_send(self, draft_id: str) -> str:
        """
        Loads a draft from the artifacts directory and sends it via SMTP with TLS.
        """
        draft_path = self.drafts_dir / draft_id
        if not draft_path.exists():
            raise FileNotFoundError(f"Draft '{draft_id}' not found at {draft_path}.")

        with open(draft_path, "r") as f:
            draft = json.load(f)

        msg = EmailMessage()
        msg['From'] = self.email_user
        msg['To'] = draft['to']
        msg['Subject'] = draft['subject']

        msg.set_content(draft['body_text'])
        msg.add_alternative(draft['body_html'], subtype='html')

        # Attachment handling can be added here in a future iteration.

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_user, self.email_pass)
                server.send_message(msg)
                logger.info(f"Email sent successfully to {draft['to']}.")

            # Clean up the draft file after sending
            os.remove(draft_path)
            return "OK"

        except smtplib.SMTPException as e:
            raise ExternalToolError(f"SMTP failed to send email: {e}")

if __name__ == '__main__':
    # Beispiel für die Verwendung
    # Stellen Sie sicher, dass Ihre .env-Datei und configs/email.yml korrekt eingerichtet sind.
    try:
        gmail_service = EmailService('gmail')
        unread = gmail_service.list_unread_emails()
        print("Ungelesene E-Mails:", unread)

        if unread:
            first_email_content = gmail_service.fetch_email(unread[0]['id'])
            # print("\nInhalt der ersten E-Mail:\n", first_email_content)

            # Beispiel für das Entwerfen einer Antwort
            # In a real scenario, you would initialize an Agent here
            # agent = Agent()
            # draft = gmail_service.draft_reply(unread[0]['id'], agent, "Das ist eine Testantwort.")
            # print("\nAntwortentwurf erstellt:", draft)

            # if draft:
            #     gmail_service.confirm_and_send(draft)

    except Exception as e:
        print(f"Ein Fehler ist aufgetreten: {e}")
