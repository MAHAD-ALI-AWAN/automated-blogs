import os
import sqlite3
import hashlib
import logging
import urllib.request
import xml.etree.ElementTree as ET
import json
import random
import re
import subprocess
import ollama
from datetime import datetime, timezone

# Logging Config
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

DB_PATH = "data/blog_history.db"
OLLAMA_MODEL = "llama3.2"

MASTER_FEEDS = [
    "https://news.ycombinator.com/rss",
    "https://www.theverge.com/rss/index.xml",
    "https://feeds.feedburner.com/TheHackersNews",
    "https://www.bleepingcomputer.com/feed/",
    "http://feeds.bbci.co.uk/news/technology/rss.xml",
    "https://rss.cnn.com/rss/cnn_tech.rss",
    "https://www.techmeme.com/feed.xml"
]

UNSPLASH_IMAGE_POOL = [
    "photo-1500530855697-b586d89ba3ee",
    "photo-1493246507139-91e8fad9978e",
    "photo-1518770660439-4636190af475",
    "photo-1522202176988-66273c2fd55f",
    "photo-1516321318423-f06f85e504b3",
    "photo-1488590528505-98d2b5aba04b",
    "photo-1446776653964-20c1d3a81b06",
    "photo-1516321165247-4aa89a48be28",
    "photo-1531297484001-80022131f5a1",
    "photo-1526379095098-d400fd0bf935",
    "photo-1504384308090-c894fdcc538d",
    "photo-1498050108023-c5249f4df085"
]

def generate_unique_image_url(title, variant="cover"):
    seed = hashlib.sha256(f"{title}:{variant}".encode("utf-8")).hexdigest()
    index = int(seed[:8], 16) % len(UNSPLASH_IMAGE_POOL)
    photo_id = UNSPLASH_IMAGE_POOL[index]
    sig = int(seed[:10], 16) % 100000
    return f"https://images.unsplash.com/{photo_id}?auto=format&fit=crop&w=1200&q=80&sig={sig}"

def normalize_title_key(title):
    return hashlib.sha256(re.sub(r'[^a-z0-9]+', ' ', title.lower()).strip().encode('utf-8')).hexdigest()

def init_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processed_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url_hash TEXT UNIQUE,
            title_hash TEXT,
            title TEXT,
            source_url TEXT,
            category TEXT,
            published_at TEXT
        )
    """)

    columns = cursor.execute("PRAGMA table_info(processed_posts)").fetchall()
    existing_columns = {col[1] for col in columns}
    if 'title_hash' not in existing_columns:
        cursor.execute("ALTER TABLE processed_posts ADD COLUMN title_hash TEXT")

    legacy_rows = cursor.execute("SELECT id, title FROM processed_posts WHERE title_hash IS NULL AND title IS NOT NULL").fetchall()
    for row_id, title in legacy_rows:
        cursor.execute("UPDATE processed_posts SET title_hash = ? WHERE id = ?", (normalize_title_key(title), row_id))

    cursor.execute("""
        DELETE FROM processed_posts
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM processed_posts
            GROUP BY COALESCE(title_hash, url_hash)
        )
    """)

    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_processed_posts_title_hash ON processed_posts(title_hash)")
    conn.commit()
    conn.close()

def is_already_processed(title, url=None):
    title_hash = normalize_title_key(title)
    url_hash = hashlib.sha256((url or '').encode()).hexdigest() if url else ''
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM processed_posts WHERE title_hash = ? OR url_hash = ?", (title_hash, url_hash))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def mark_as_processed(title, url, category):
    url_hash = hashlib.sha256(url.encode()).hexdigest()
    title_hash = normalize_title_key(title)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO processed_posts (url_hash, title_hash, title, source_url, category, published_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (url_hash, title_hash, title, url, category, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()

def fetch_random_topic():
    logging.info("Global feeds se trending topics fetch ho rahe hain...")
    headers = {'User-Agent': 'Mozilla/5.0'}

    feeds = MASTER_FEEDS.copy()
    random.shuffle(feeds)

    for feed_url in feeds:
        try:
            req = urllib.request.Request(feed_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                xml_data = response.read()

            root = ET.fromstring(xml_data)
            channel = root.find('channel')
            items = channel.findall('item') if channel is not None else root.findall('{http://www.w3.org/2005/Atom}entry')

            random.shuffle(items)
            for item in items[:10]:
                title_elem = item.find('title')
                link_elem = item.find('link')
                desc_elem = item.find('description')

                if title_elem is None:
                    title_elem = item.find('{http://www.w3.org/2005/Atom}title')
                if link_elem is None:
                    link_elem = item.find('{http://www.w3.org/2005/Atom}link')
                if desc_elem is None:
                    desc_elem = item.find('{http://www.w3.org/2005/Atom}summary')

                title = title_elem.text if title_elem is not None and title_elem.text else "Untitled"

                if link_elem is not None:
                    link = link_elem.text if link_elem.text else link_elem.attrib.get('href', '')
                else:
                    link = ""

                summary = desc_elem.text if desc_elem is not None and desc_elem.text else ""

                if link:
                    normalized_title = (title or '').strip()
                    if normalized_title and not is_already_processed(normalized_title, link):
                        logging.info(f"Naya global hot topic mila: {title}")
                        return {"title": title, "summary": summary, "url": link}

        except Exception as e:
            logging.error(f"Feed error ({feed_url}): {e}")
            continue

    return None

def clean_topic_summary(summary):
    if not summary:
        return ""
    text = re.sub(r'<[^>]+>', ' ', summary)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def strip_leading_duplicate_title(raw_text, title):
    if not raw_text:
        return raw_text

    lines = raw_text.splitlines()
    if not lines:
        return raw_text

    first_line = lines[0].strip()
    heading_match = re.match(r'^(#{1,6})\s*(.+?)\s*$', first_line)
    if not heading_match:
        return raw_text

    heading_text = heading_match.group(2).strip()
    if normalize_title_key(heading_text) == normalize_title_key(title):
        lines = lines[1:]
        if lines and re.fullmatch(r'={3,}|-{3,}', lines[0].strip()):
            lines = lines[1:]
        return '\n'.join(lines).strip()

    return raw_text

def normalize_generated_article(title, content, cover_url, secondary_url):
    raw = content or ""
    raw = re.sub(r'^---\s*[\s\S]*?\n---\s*', '', raw.strip())

    raw = re.sub(r'(?m)^\*\*([^*]+)\*\*\s*$', r'## \1', raw)
    raw = re.sub(r'(?m)^\*([^*]+)\*\s*$', r'## \1', raw)

    raw = re.sub(r'(?i)(?<!\!)\[\s*image\s*:\s*(https?://[^\]\n]+)\]', r'![Image](\1)', raw)
    raw = re.sub(r'(?i)(?<!\!)\bimage\s*:\s*(https?://[^\s\]]+)', r'![Image](\1)', raw)
    raw = re.sub(r'!\[[^\]]*\]\([^\)]+\)', '', raw)
    raw = re.sub(r'\[[^\]]*?:\s*(https?://[^\]]+?)\]\((https?://[^\)]+)\)', '', raw)
    raw = re.sub(r'\[[^\]]*?\]\((https?://[^\)]+)\)', '', raw)
    raw = re.sub(r'\n{3,}', '\n\n', raw).strip()

    raw = re.sub(r'(?im)^\s*\[\s*image\s*:\s*(https?://[^\]]+)\s*\]\s*$', r'![Image](\1)', raw)
    raw = re.sub(r'(?im)^\s*image\s*:\s*(https?://\S+)\s*$', r'![Image](\1)', raw)
    raw = strip_leading_duplicate_title(raw, title)

    if not raw:
        raw = (
            f"## Executive Overview\nThis development represents a major shift in how modern engineering challenges are approached across global markets.\n\n"
            f"## Deep-Dive Analysis\nIndustry experts are analyzing the underlying architecture and implications of this release."
        )

    article_body = raw.strip()
    article_body = article_body.replace(f"# {title}", '').replace(f"## {title}", '').replace(f"### {title}", '').strip()
    article_body = re.sub(r'(?im)^\s*\!\[\s*Image\s*\]\((https?://[^\)]+)\)\s*$', '', article_body)
    article_body = article_body.strip()

    final_article = (
        f"# {title}\n\n"
        f"![Cover Image]({cover_url})\n\n"
        f"{article_body}\n\n"
        f"> **💡 Key Takeaway:** Understanding the trajectory of {title.lower()} is essential for stakeholders looking to stay ahead of upcoming tech paradigms.\n\n"
        f"![Secondary Image]({secondary_url})\n"
    )

    final_article = re.sub(r'\n{3,}', '\n\n', final_article).strip()
    return final_article

def ai_discover_category_and_generate(topic):
    logging.info("Generating comprehensive, high-depth article...")

    title = (topic.get('title') or 'Trending Story').strip()
    summary = clean_topic_summary(topic.get('summary'))
    if not summary:
        summary = title
    cover_url = generate_unique_image_url(title, 'cover')
    secondary_url = generate_unique_image_url(title, 'secondary')

    prompt = f"""
    You are a senior tech journalist and principal technology analyst for a premier digital publication.
    Write an in-depth, highly comprehensive, and professional long-form article based on the provided topic.

    Topic Title: {title}
    Topic Context: {summary}

    STRICT STRUCTURAL REQUIREMENTS:
    1. Line 1 MUST start with "CATEGORY: " followed by a precise professional category (e.g., "CATEGORY: Artificial Intelligence", "CATEGORY: Cybersecurity", "CATEGORY: Cloud Engineering").
    2. Followed by a rich, multi-section markdown article with clear markdown headings (e.g., ## Executive Overview). Do not use bold text for headings; use proper markdown heading syntax.
    3. Include H2 (`##`) subheadings covering:
       - Executive Overview & Background
       - Technical Breakdown / Core Mechanics
       - Market Implications & Industry Impact
       - A detailed Markdown comparison/data table summarizing key metrics or components.
       - Future Outlook & Strategic Takeaways
    4. Maintain an authoritative, engaging, and polished publication tone.
    """

    try:
        response = ollama.generate(
            model=OLLAMA_MODEL,
            prompt=prompt,
            options={
                "temperature": 0.4,
                "num_predict": 1200,
                "num_ctx": 4096,
            },
            stream=False,
        )
        response_text = response.get('response', '').strip()
        
        category = "Hot Trends"
        if "CATEGORY:" in response_text:
            parts = response_text.split("CATEGORY:", 1)
            lines = parts[1].strip().split("\n")
            category = lines[0].strip()
            response_text = "\n".join(lines[1:]).strip()

        normalized = normalize_generated_article(title, response_text, cover_url, secondary_url)
        return category, True, normalized
        
    except Exception as e:
        logging.error(f"Ollama generation error: {e}")
        fallback_text = (
            f"## Executive Overview\nThis development marks a crucial turning point in current technological advancements.\n\n"
            f"## Core Analysis\nAnalysts are closely examining the broader effects on architecture, security, and market adoption.\n\n"
            f"| Metric / Aspect | Details |\n|---|---|\n| Core Focus | {title} |\n| Status | Active Evolution |\n"
        )
        return "Hot Trends", True, normalize_generated_article(title, fallback_text, cover_url, secondary_url)

def save_to_markdown(content, title, category, is_hot=True):
    output_dir = "frontend/output_posts"
    os.makedirs(output_dir, exist_ok=True)

    filename = "".join(c if c.isalnum() else "_" for c in title).lower()[:50] + ".md"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    logging.info(f"Article saved: {filepath} [{category}]")

    json_path = "frontend/posts.json"
    posts = []
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as jf:
                posts = json.load(jf)
        except:
            posts = []

    new_post = {
        "title": title,
        "file": filename,
        "category": category,
        "is_hot": is_hot,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    }

    if not any(p['file'] == filename for p in posts):
        posts.insert(0, new_post)

    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(posts, jf, indent=4)

    return True

def generate_sitemap_xml():
    logging.info("Generating sitemap.xml from posts.json...")
    json_path = "frontend/posts.json"
    sitemap_path = "frontend/sitemap.xml"
    
    if not os.path.exists(json_path):
        logging.warning("posts.json not found, skipping sitemap generation.")
        return

    try:
        with open(json_path, "r", encoding="utf-8") as jf:
            posts = json.load(jf)
    except Exception as e:
        logging.error(f"Error reading posts.json for sitemap: {e}")
        return

    today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    static_pages = [
        {"loc": "https://bytepulseblogs.online/", "priority": "1.0", "changefreq": "daily"},
        {"loc": "https://bytepulseblogs.online/about.html", "priority": "0.8", "changefreq": "monthly"},
        {"loc": "https://bytepulseblogs.online/privacy.html", "priority": "0.8", "changefreq": "monthly"},
        {"loc": "https://bytepulseblogs.online/contact.html", "priority": "0.8", "changefreq": "monthly"}
    ]

    for page in static_pages:
        xml += "  <url>\n"
        xml += f"    <loc>{page['loc']}</loc>\n"
        xml += f"    <lastmod>{today_date}</lastmod>\n"
        xml += f"    <changefreq>{page['changefreq']}</changefreq>\n"
        xml += f"    <priority>{page['priority']}</priority>\n"
        xml += "  </url>\n"

    for post in posts:
        file_name = post.get("file")
        if file_name:
            post_url = f"https://bytepulseblogs.online/post.html?file={file_name}"
            post_date = post.get("date", today_date).split(" ")[0]
            
            xml += "  <url>\n"
            xml += f"    <loc>{post_url}</loc>\n"
            xml += f"    <lastmod>{post_date}</lastmod>\n"
            xml += f"    <changefreq>weekly</changefreq>\n"
            xml += f"    <priority>0.7</priority>\n"
            xml += "  </url>\n"

    xml += "</urlset>"

    with open(sitemap_path, "w", encoding="utf-8") as sf:
        sf.write(xml)

    logging.info(f"Sitemap successfully generated at {sitemap_path}")

def auto_push_to_github():
    try:
        subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        logging.info("Git repo not initialized; skipping GitHub push.")
        return False

    try:
        remotes = subprocess.run(["git", "remote"], capture_output=True, text=True, check=True).stdout.strip().splitlines()
        if not remotes:
            logging.warning("No git remote configured; skipping GitHub push.")
            return False

        tracked_paths = [
            "frontend/output_posts", 
            "frontend/posts.json", 
            "frontend/sitemap.xml", 
            "data/blog_history.db"
        ]
        for path in tracked_paths:
            if os.path.exists(path):
                subprocess.run(["git", "add", "-f", path], check=True)

        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True).stdout.strip()
        if not status:
            logging.info("No new content to push to GitHub.")
            return False

        branch_name = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, check=True).stdout.strip() or "main"
        subprocess.run(["git", "commit", "-m", "Auto blog update - Comprehensive deep dive & sitemap"], check=True)
        subprocess.run(["git", "push", "origin", branch_name], check=True)
        logging.info(f"GitHub push succeeded to origin/{branch_name}.")
        return True
    except subprocess.CalledProcessError as exc:
        logging.error(f"GitHub auto-push failed: {exc}")
        return False

def run_pipeline():
    init_db()
    topic = fetch_random_topic()

    if not topic:
        logging.info("No New Topic Found.")
        return

    category, is_hot, article_content = ai_discover_category_and_generate(topic)
    success = save_to_markdown(article_content, topic["title"], category, is_hot)

    if success:
        mark_as_processed(topic["title"], topic["url"], category)
        
        # Sitemap generate karein
        generate_sitemap_xml()
        
        # GitHub par push karein
        auto_push_to_github()
        logging.info("Pipeline Execution Finished Successfully!")

if __name__ == "__main__":
    run_pipeline()