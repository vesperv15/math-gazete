import subprocess
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
    NOT: urllib.request bu ortamda arXiv tarafından (muhtemelen TLS/HTTP
    imza seviyesinde bir bot-filtresiyle) 406 ile reddediliyordu; curl ise
    aynı istekte sorunsuz çalıştığı için burada subprocess ile curl kullanılıyor.
    """
    url = f"https://export.arxiv.org/api/query?search_query=cat:{category}&sortBy=submittedDate&sortOrder=descending&max_results={max_results}"

    xml_data = None
    last_error = None
    for attempt in range(4):  # Şansı artırmak için deneme sayısını 4 yaptık
        try:
            time.sleep(3)  # arXiv'i yormamak için her istek öncesi garanti 3 sn bekle
            result = subprocess.run(
                [
                    'curl', '-s', '-f', '--max-time', '20',
                    '-H', 'User-Agent: AkademikGazeteBot/1.0 (mailto:akademikgazete7@gmail.com)',
                    url
                ],
                capture_output=True,
                check=True,
            )
            xml_data = result.stdout
            break
        except subprocess.CalledProcessError as e:
            last_error = f"curl exit code {e.returncode}, stderr: {e.stderr.decode('utf-8', errors='replace')[:300]}"
            bekleme_suresi = 5 * (attempt + 1)
            print(f"⏳ arXiv isteği başarısız ({last_error}). {bekleme_suresi} saniye bekleniyor...")
            time.sleep(bekleme_suresi)

    if not xml_data:
        raise Exception(f"arXiv sunucusuna ulaşılamadı. Son hata: {last_error}")

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
