import urllib.request
import urllib.error
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
    """
    url = f"https://export.arxiv.org/api/query?search_query=cat:{category}&sortBy=submittedDate&sortOrder=descending&max_results={max_results}"

    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'AkademikGazeteBot/1.0 (mailto:akademikgazete7@gmail.com)',
            'Accept': 'application/atom+xml,application/xml;q=0.9,*/*;q=0.8',
        }
    )

    # arXiv sunucu hataları (406, 429, 502, 503 vb.) için otomatik bekleme ve yeniden deneme mantığı
    xml_data = None
    last_error_body = None
    for attempt in range(4):  # Şansı artırmak için deneme sayısını 4 yaptık
        try:
            time.sleep(3)  # arXiv'i yormamak için her istek öncesi garanti 3 sn bekle
            response = urllib.request.urlopen(req)
            xml_data = response.read()
            break
        except urllib.error.HTTPError as e:
            # Sunucunun gerçekte ne döndürdüğünü görmek için hata gövdesini oku
            try:
                last_error_body = e.read().decode('utf-8', errors='replace')[:500]
            except Exception:
                last_error_body = "(gövde okunamadı)"

            # Hem rate-limit/reddetme (406, 429) hem de sunucu çökmelerini (502, 503, 504) yakala
            if e.code in [406, 429, 502, 503, 504]:
                bekleme_suresi = 5 * (attempt + 1)
                print(f"⏳ arXiv sunucusu meşgul/reddetti (Hata {e.code}). Gövde: {last_error_body}")
                print(f"{bekleme_suresi} saniye bekleniyor...")
                time.sleep(bekleme_suresi)
            else:
                print(f"Beklenmeyen hata gövdesi: {last_error_body}")
                raise e

    if not xml_data:
        raise Exception(f"arXiv sunucusuna ulaşılamadı (Sunucu yanıt vermiyor). Son hata gövdesi: {last_error_body}")

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
    Makale başlığı ve özetini Gemini API ile gazete formatına dönüştürür.
    """
    prompt = f"""
    Aşağıda matematik alanında yazılmış bir makalenin başlığı ve özeti yer alıyor.
    Bu makaleyi akademisyenlerin hızlıca anlayabileceği 'günlük gazete haberi' üslubuyla Türkçe olarak özetle.

    Kurallar:
    - Tam olarak 2 cümle olsun.
    - İlk cümle çalışmanın ne yaptığını/neye odaklandığını söylesin.
    - İkinci cümle elde edilen temel matematiksel sonucu veya yeniliği vurgulasın.
    - TEMİZ METİN kuralı: Kesinlikle '$' sembolü veya LaTeX kodları (\mathrm, \mathbb vb.) KULLANMA. 
    Matematiksel ifadeleri düz metin ve standart karakterlerle yaz (Örn: '$\\mathrm{{GL}}_2(\\mathbb{{Q}})$' yerine 'GL_2(Q)', '$L$' yerine 'L').

    Başlık: {title}
    Özet: {abstract}
    """

    response = client.models.generate_content(
        model='gemini-3.6-flash',
        contents=prompt,
    )

    return response.text.strip()

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
