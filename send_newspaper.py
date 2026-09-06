import os
import csv
import io
import urllib.request
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from arxiv_summarizer import fetch_arxiv_papers, summarize_paper

load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")

client = genai.Client()

def get_recipients_from_google_sheet(sheet_id):
    """Google Tablolar'dan e-posta listesini otomatik çeker."""
    if not sheet_id:
        print("⚠️ GOOGLE_SHEET_ID .env dosyasında tanımlı değil!")
        return []
        
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    try:
        response = urllib.request.urlopen(url)
        csv_data = response.read().decode('utf-8')
        
        reader = csv.reader(io.StringIO(csv_data))
        next(reader, None)  # Başlık satırını atla
        
        recipients = set()
        for row in reader:
            if len(row) >= 2 and "@" in row[1]:
                recipients.add(row[1].strip())
            elif len(row) >= 1 and "@" in row[0]:
                recipients.add(row[0].strip())
                
        return list(recipients)
    except Exception as e:
        print(f"⚠️ Google Sheets okuma hatası: {e}")
        return []

def build_html_newsletter(papers_with_summaries):
    today_str = datetime.now().strftime("%d.%m.%Y")
    cards_html = ""
    for paper in papers_with_summaries:
        cards_html += f"""
        <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
            <span style="background-color: #ebf8ff; color: #2b6cb0; font-size: 11px; font-weight: bold; padding: 4px 8px; border-radius: 4px;">arXiv Matematik</span>
            <h3 style="color: #2d3748; font-size: 17px; margin-top: 10px; margin-bottom: 6px;">{paper['title']}</h3>
            <p style="color: #718096; font-size: 12px; margin-top: 0;"><strong>Yazarlar:</strong> {paper['authors']}</p>
            <div style="background-color: #f7fafc; border-left: 4px solid #3182ce; padding: 12px; margin-bottom: 14px;">
                <p style="color: #2d3748; font-size: 13.5px; margin: 0; line-height: 1.5;">{paper['summary']}</p>
            </div>
            <a href="{paper['link']}" target="_blank" style="background-color: #3182ce; color: #ffffff; text-decoration: none; font-size: 12px; font-weight: bold; padding: 8px 14px; border-radius: 5px; display: inline-block;">Makaleyi Oku &rarr;</a>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: sans-serif; background-color: #f8fafc; margin: 0; padding: 20px;">
        <div style="max-width: 650px; margin: 0 auto;">
            <div style="text-align: center; padding: 15px 0; border-bottom: 2px solid #e2e8f0; margin-bottom: 25px;">
                <h1 style="color: #1a202c; font-size: 24px; margin: 0;">🗞️ Günlük Matematik Gazetesi</h1>
                <p style="color: #718096; font-size: 13px; margin-top: 5px;">{today_str} • Günün Öne Çıkan arXiv Makaleleri</p>
            </div>
            {cards_html}
            <div style="text-align: center; margin-top: 35px; color: #a0aec0; font-size: 11px; border-top: 1px solid #e2e8f0; padding-top: 15px;">
                <p>Akdeniz Üniversitesi Otomatik Akademik Asistan Sistemi</p>
                <p><i>💡 Özel bir konu aratmak için bu e-postaya doğrudan "Yanıtla" diyerek konuyu yazabilirsiniz.</i></p>
                <p><i>Abonelikten çıkmak için bu e-postayı "İPTAL" yazarak yanıtlayabilirsiniz.</i></p>
            </div>
        </div>
    </body>
    </html>
    """

def send_email_gmail(to_email, subject, html_content):
    msg = MIMEMultipart("alternative")
    msg["From"] = f"Matematik Gazetesi <{GMAIL_USER}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Reply-To"] = GMAIL_USER

    msg.attach(MIMEText(html_content, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD.replace(" ", ""))
        server.sendmail(GMAIL_USER, to_email, msg.as_string())

def send_newsletter_to_all():
    print("1. Google Tablolar üzerinden güncel abone listesi çekiliyor...")
    recipients = get_recipients_from_google_sheet(GOOGLE_SHEET_ID)
    
    # Abonelikten çıkmış (kara listeye alınmış) kişileri listeden ayıkla
    if os.path.exists("iptal_edilenler.txt"):
        with open("iptal_edilenler.txt", "r", encoding="utf-8") as f:
            unsubbed = [line.strip().lower() for line in f if line.strip()]
        recipients = [r for r in recipients if r.lower() not in unsubbed]

    if not recipients:
        print("⚠️ Gönderilecek aktif abone bulunamadı!")
        return

    print(f"   Bulunan Aktif Abone Sayısı: {len(recipients)}")
    print("2. arXiv'den makaleler çekiliyor...")
    raw_papers = fetch_arxiv_papers(category="math.NT", max_results=2) + fetch_arxiv_papers(category="math.AG", max_results=1)

    print("3. Gemini API ile özetler oluşturuluyor...")
    papers_with_summaries = []
    for paper in raw_papers:
        summary = summarize_paper(paper['title'], paper['abstract'])
        papers_with_summaries.append({
            "title": paper['title'],
            "authors": paper['authors'],
            "link": paper['link'],
            "summary": summary
        })

    print("4. E-postalar gönderiliyor...")
    html_content = build_html_newsletter(papers_with_summaries)
    subject = f"🗞️ Günlük Matematik Gazetesi - {datetime.now().strftime('%d.%m.%Y')}"

    for email_addr in recipients:
        try:
            send_email_gmail(email_addr, subject, html_content)
            print(f"  ✅ Gönderildi: {email_addr}")
        except Exception as e:
            print(f"  ❌ Hata ({email_addr}): {e}")

if __name__ == "__main__":
    send_newsletter_to_all()