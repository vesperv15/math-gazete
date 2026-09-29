import requests
import xml.etree.ElementTree as ET
import os
import time
from google import genai
from dotenv import load_dotenv

load_dotenv()

# Gemini API İstemcisi
client = genai.Client()

def fetch_arxiv_papers(category="math.NT", max_results=2):
    """
    arXiv API'den belirtilen matematik kategorisindeki son makaleleri çeker.
    subprocess/curl yerine doğrudan güvenli Python requests katmanı kullanılır.
    """
    url = f"https://export.arxiv.org/api/query?search_query=cat:{category}&sortBy=submittedDate&sortOrder=descending&max_results={max_results}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/atom+xml, application/xml, */*'
    }

    xml_data = None
    last_error = None
    
    for attempt in range(4):
        try:
            time.sleep(2)  # arXiv sunucularını kitlememek için bekleme
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                xml_data = response.content
                break
            else:
                last_error = f"HTTP {response.status_code}"
                print(f"⏳ arXiv yanıt vermedi ({last_error}). Yeniden deneniyor...")
        except Exception as e:
            last_error = str(e)
            print(f"⏳ arXiv bağlantı denemesi {attempt + 1} başarısız: {e}")

        bekleme_suresi = 5 * (attempt + 1)
        time.sleep(bekleme_suresi)

    if not xml_data:
        print(f"⚠️ arXiv'den '{category}' kategorisi için makale çekilemedi. Son Hata: {last_error}")
        return []

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
    """
    Makale başlığı ve özeti Gemini API ile gazete formatına dönüştürür.
    """
    prompt = f"""
    Aşağıda matematik alanında yazılmış bir makalenin başlığı ve özeti yer alıyor.
    Bu makaleyi akademisyenlerin hızlıca anlayabileceği 'günlük gazete haberi' üslubuyla Türkçe olarak özetle.

    Kurallar:
    - Tam olarak 2 cümle olsun.
    - İlk cümle çalışmanın ne yaptığını/neye odaklandığını söylesin.
    - İkinci cümle elde edilen temel matematiksel sonucu veya yeniliği vurgulasın.
    - TEMİZ METİN kuralı: Kesinlikle '$' sembolü veya LaTeX kodları (\\mathrm, \\mathbb vb.) KULLANMA. 
    Matematiksel ifadeleri düz metin ve standart karakterlerle yaz (Örn: '$\\mathrm{{GL}}_2(\\mathbb{{Q}})$' yerine 'GL_2(Q)', '$L$' yerine 'L').

    Başlık: {title}
    Özet: {abstract}
    """

    last_error = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt,
            )
            return response.text.strip()
        except Exception as e:
            last_error = e
            bekleme_suresi = 15 * (attempt + 1)
            print(f"⏳ Gemini API meşgul/hata verdi ({e}). {bekleme_suresi} saniye bekleniyor...")
            time.sleep(bekleme_suresi)

    raise last_error

if __name__ == "__main__":
    print("arXiv'den son Sayılar Teorisi (math.NT) makaleleri çekiliyor ve özetleniyor...\n")
    raw_papers = fetch_arxiv_papers(category="math.NT", max_results=2)

    for i, paper in enumerate(raw_papers, 1):
        print(f"=== Makale {i} ===")
        print(f"Orijinal Başlık: {paper['title']}")
        print(f"Yazarlar: {paper['authors']}")

        turkish_summary = summarize_paper(paper['title'], paper['abstract'])
        print(f"\n[Gazete Özeti]:\n{turkish_summary}")
        print(f"\nDevamını Oku: {paper['link']}\n" + "-"*40)
