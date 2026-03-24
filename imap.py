import imaplib
import email
from email.header import decode_header

class SimpleMailClient:
    def __init__(self, login, password, imap_server="imap.smtp.dev", imap_port=993):
        self.login = login
        self.password = password
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.mail = None

    def connect(self):
        self.mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
        self.mail.login(self.login, self.password)
        self.mail.select("INBOX")

    def fetch_latest_unseen(self):
        status, messages = self.mail.search(None, 'UNSEEN')
        message_ids = messages[0].split()

        if not message_ids:
            print("Нет непрочитанных писем.")
            return

        latest_id = message_ids[-1]
        status, msg_data = self.mail.fetch(latest_id, '(RFC822)')

        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])

                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding or "utf-8")
                print(f"Тема: {subject}")

                body = self._extract_body(msg)
                return body

    def _extract_body(self, msg):
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                if content_type == "text/plain" and "attachment" not in content_disposition:
                    return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")
        else:
            return msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="ignore")
        return "[Пустое тело]"

    def logout(self):
        if self.mail:
            self.mail.logout()
