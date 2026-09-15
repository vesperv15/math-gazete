import os
import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv
from google import genai
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client()

# --- RENDER İÇİN SAĞLIK KONTROLÜ SUNUCUSU ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Aktif")

def start_health_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()
# ---------------------------------------------

def extract_search_query_with_gemini(raw_email_body):
    prompt = f"""
    Aşağıda bir akademisyenin gelen bir e-postaya verdiği yanıt metni yer alıyor.
    Bu metindeki e-posta imzalarını, selamlaşmaları ve eski ileti alıntılarını temizle.
    Sadece kullanıcının aramak istediği matematiksel konuyu/anahtar kelimeyi İngilizce olarak döndür.
    Eğer herhangi bir konu yoksa sadece 'INVALID' yaz.
    
    E-Posta Metni:
    {raw_email_body}
    """
    response = client.models.generate_content(
        model='gemini-3.6-flash',
        contents=prompt,
    )
    return response.text.strip()

def search_arxiv_by_keyword(query, max_results=3):
    encoded_query = urllib.parse.quote(query)
    url = f"http://export.arxiv.org/api/query?search_query=all:{encoded_query}&sortBy=submittedDate&sortOrder=descending&max_results={max_results}"
    
    response = urllib.request.urlopen(url)
    xml_data = response.read()
    root = ET.fromstring(xml_data)
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    
    papers = []
    for entry in root.findall('atom:entry', ns):
        title = entry.find('atom:title', ns).text.strip().replace('\n', ' ')
        summary = entry.find('atom:summary', ns).text.strip().replace('\n', ' ')
        link = entry.find('atom:id', ns).text.strip()
        authors = [author.find('atom:name', ns).text for author in entry.findall('atom:author', ns)]
        
        papers.append({
            "title": title,
            "abstract": summary,
            "link": link,
            "authors": ", ".join(authors[:3])
        })
    return papers

def summarize_paper(title, abstract):
    prompt = f"""
    Aşağıda matematik alanında yazılmış bir makalenin başlığı ve özeti yer alıyor.
    Bu makaleyi akademisyenlerin hızlıca anlayabileceği 'günlük gazete haberi' üslubuyla Türkçe olarak özetle.
    
    Kurallar:
    - Tam olarak 2 cümle olsun.
    - TEMİZ METİN kuralı: Kesinlikle '$' sembolü veya LaTeX kodları kullanma.
    
    Başlık: {title}
    Özet: {abstract}
    """
    response = client.models.generate_content(
        model='gemini-3.6-flash',
        contents=prompt,
    )
    return response.text.strip()

def build_search_response_html(query, papers_with_summaries):
    cards_html = ""
    for paper in papers_with_summaries:
        cards_html += f"""
        <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
            <h3 style="color: #2d3748; font-size: 16px; margin-top: 0;">{paper['title']}</h3>
            <p style="color: #718096; font-size: 12px;"><strong>Yazarlar:</strong> {paper['authors']}</p>
            <div style="background-color: #f7fafc; border-left: 4px solid #3182ce; padding: 12px; margin-bottom: 14px;">
                <p style="color: #2d3748; font-size: 13.5px; margin: 0;">{paper['summary']}</p>
            </div>
            <a href="{paper['link']}" target="_blank" style="background-color: #3182ce; color: #ffffff; text-decoration: none; font-size: 12px; font-weight: bold; padding: 8px 14px; border-radius: 4px; display: inline-block;">Makaleyi Oku &rarr;</a>
        </div>
        """

    return f"""
    <html>
    <body style="font-family: sans-serif; background-color: #f8fafc; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2b6cb0;">🔍 '{query}' Konulu Arama Sonuçları</h2>
            <p style="color: #4a5568; font-size: 14px;">arXiv üzerinde bulduğum en güncel 3 makale ve özetleri:</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin-bottom: 20px;">
            {cards_html}
        </div>
    </body>
    </html>
    """

def send_reply_email(to_email, subject, html_content):
    msg = MIMEMultipart("alternative")
    msg["From"] = f"Matematik Asistanı <{GMAIL_USER}>"
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(html_content, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD.replace(" ", ""))
        server.sendmail(GMAIL_USER, to_email, msg.as_string())

def add_to_blacklist(email_to_remove, file_path="iptal_edilenler.txt"):
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(email_to_remove.strip() + "\n")

def check_inbox_and_reply():
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_APP_PASSWORD.replace(" ", ""))
        mail.select("inbox")

        status, messages = mail.search(None, 'UNSEEN')
        email_ids = messages[0].split()

        if not email_ids:
            return

        for e_id in email_ids:
            status, msg_data = mail.fetch(e_id, '(RFC822)')
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    sender_email = email.utils.parseaddr(msg.get("From"))[1]
                    
                    raw_body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                raw_body = part.get_payload(decode=True).decode()
                                break
                    else:
                        raw_body = msg.get_payload(decode=True).decode()

                    search_query = extract_search_query_with_gemini(raw_body)
                    
                    if search_query and search_query != "INVALID":
                        if search_query.upper() in ["IPTAL", "İPTAL", "UNSUBSCRIBE", "STOP"]:
                            add_to_blacklist(sender_email)
                            send_reply_email(
                                sender_email, 
                                "Günlük Matematik Gazetesi - Abonelik İptali", 
                                "<p>Aboneliğiniz talebiniz üzerine sonlandırılmıştır. Artık günlük gazete almayacaksınız.</p>"
                            )
                            print(f"🚫 {sender_email} adresi abonelikten çıkmak istedi ve kara listeye eklendi.")
                            continue
                        
                        print(f"\n📩 Yanıt Yakalandı! Gönderen: {sender_email} | Temizlenen Konu: '{search_query}'")
                        raw_papers = search_arxiv_by_keyword(search_query, max_results=3)
                        
                        papers_with_summaries = []
                        for paper in raw_papers:
                            summary = summarize_paper(paper['title'], paper['abstract'])
                            papers_with_summaries.append({
                                "title": paper['title'],
                                "authors": paper['authors'],
                                "link": paper['link'],
                                "summary": summary
                            })

                        html_content = build_search_response_html(search_query, papers_with_summaries)
                        send_reply_email(sender_email, f"🔍 Arama Sonucu: {search_query}", html_content)
                        print(f"✅ Yanıt e-postası {sender_email} adresine gönderildi!")

        mail.logout()
    except Exception as e:
        print(f"⚠️ Hata: {str(e)}")

if __name__ == "__main__":
    # Arka planda HTTP sunucusunu başlatır
    threading.Thread(target=start_health_server, daemon=True).start()
    
    print("🎧 Akıllı E-posta Dinleyici Başlatıldı...")
    while True:
        check_inbox_and_reply()
        time.sleep(60)
