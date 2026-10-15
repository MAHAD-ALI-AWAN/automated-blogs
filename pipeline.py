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
from datetime import datetime, timezone
from transformers import pipeline

# Logging Config
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

DB_PATH = "data/blog_history.db"

# Hugging Face model load
try:
    logging.info("Hugging Face se model load ho raha hai...")
    generator = pipeline('text-generation', model='gpt2-medium')
except Exception as e:
    logging.error(f"Model load error: {e}")
    generator = None

# Har tarah ki general aur diverse news feeds (Tech, World News, Science, General)
MASTER_FEEDS = [
    "https://news.ycombinator.com/rss",
    "https://www.theverge.com/rss/index.xml",
    "https://feeds.feedburner.com/TheHackersNews",
    "https://www.bleepingcomputer.com/feed/",
    "http://feeds.bbci.co.uk/news/technology/rss.xml",
    "https://rss.cnn.com/rss/cnn_tech.rss",
    "https://www.techmeme.com/feed.xml",
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "https://rss.cnn.com/rss/cnn_topstories.rss"
]

# Alag-alag categories ke hisab se relevant images ka pool
THEMED_IMAGE_POOLS = {
    "space": [
        "photo-1451187580459-43490279c0fa",
        "photo-1446776653964-20c1d3a81b06",
        "photo-1506703719100-a0f3a48c0f86"
    ],
    "business": [
        "photo-1486406146926-c627a92ad1ab",
        "photo-1590283603385-17ffb3a7f29f",
        "photo-1454165804606-c3d57bc86b40"
    ],
    "health": [
        "photo-1584515979956-d9f6e5d09982",
        "photo-1576091160399-112ba8d25d1d",
        "photo-1505751172876-fa1923c5c528"
    ],
    "tech": [
        "photo-1526379095098-d400fd0bf935",
        "photo-1518770660439-4636190af475",
        "photo-1550751827-4bd374c3f58b"
    ],
    "general": [
        "photo-1499750310107-5fef28a66643",
        "photo-1455390582262-044cdead277a",
        "photo-1507525428034-b723cf961d3e"
    ]
}

def get_relevant_image_url(title, variant="cover"):
    title_lower = title.lower()
    
    # Topic ke words detect karke relevant category select karna
    category = "general"
    if any(w in title_lower for w in ["space", "nasa", "mars", "moon", "orbit", "planet", "star"]):
        category = "space"
    elif any(w in title_lower for w in ["market", "stocks", "money", "business", "economy", "bank", "fund", "startup"]):
        category = "business"
    elif any(w in title_lower for w in ["health", "medical", "cancer", "disease", "doctor", "hospital", "drug", "virus"]):
        category = "health"
    elif any(w in title_lower for w in ["tech", "ai", "software", "cyber", "code", "data", "apple", "google", "microsoft"]):
        category = "tech"

    pool = THEMED_IMAGE_POOLS[category]
    seed = hashlib.sha256(f"{title}:{variant}".encode("utf-8")).hexdigest()
    index = int(seed[:8], 16) % len(pool)
    photo_id = pool[index]
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
                link = link_elem.text if link_elem is not None and link_elem.text else (link_elem.attrib.get('href', '') if link_elem is not None else "")
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
    return re.sub(r'\s+', ' ', text).strip()

def normalize_generated_article(title, summary, generated_text, cover_url, secondary_url):
    raw = generated_text or ""
    
    raw = re.sub(r'\n{3,}', '\n\n', raw).strip()
    last_dot = raw.rfind('.')
    if last_dot != -1:
        raw = raw[:last_dot + 1]

    final_article = (
        f"# {title}\n\n"
        f"![Cover Image]({cover_url})\n\n"
        f"## Executive Overview\n\n"
        f"The rapid evolution of modern events continues to reshape industry standards. "
        f"Recently, **{title}** has emerged as a crucial topic of discussion globally.\n\n"
        f"{summary if summary else 'This development addresses key aspects and introduces significant insights.'}\n\n"
        f"## Detailed Analysis & Insights\n\n"
        f"{raw}\n\n"
        f"## Key Takeaways & Implications\n\n"
        f"* **Global Impact:** Analyzing the broader significance on current trends.\n"
        f"* **Future Outlook:** What stakeholders should expect moving forward.\n\n"
        f"![Secondary Image]({secondary_url})\n\n"
        f"> **💡 Summary Insight:** Understanding the background of {title.lower()} is essential for comprehensive awareness.\n"
    )

    return final_article.strip()

def ai_discover_category_and_generate(topic):
    logging.info("Generating safe-length article...")
    title = (topic.get('title') or 'Trending Story').strip()
    
    summary = clean_topic_summary(topic.get('summary'))
    summary = re.sub(r'\[\.\.\.\]', '', summary).strip()
    if not summary:
        summary = title

    # Topic ke mutabiq relevant images generate karna
    cover_url = get_relevant_image_url(title, 'cover')
    secondary_url = get_relevant_image_url(title, 'secondary')

    prompt = f"Analyzing {title}:"

    generated_text = ""
    try:
        if generator:
            res = generator(
                prompt, 
                max_new_tokens=201,
                num_return_sequences=1, 
                do_sample=True, 
                temperature=0.7,
                truncation=True
            )
            raw_output = res[0]['generated_text']
            
            if raw_output.startswith(prompt):
                generated_text = raw_output[len(prompt):].strip()
            else:
                generated_text = raw_output.strip()
        else:
            generated_text = f"An evaluation of {title} highlights key operational developments and major updates."

        category = "World Affairs" if "world" in title.lower() else "General News"
        normalized = normalize_generated_article(title, summary, generated_text, cover_url, secondary_url)
        return category, True, normalized
    except Exception as e:
        logging.error(f"Generation error: {e}")
        fallback_text = f"An evaluation of {title} highlights key developments."
        return "Trending", True, normalize_generated_article(title, summary, fallback_text, cover_url, secondary_url)

def save_to_markdown(content, title, category, is_hot=True):
    output_dir = "frontend/output_posts"
    os.makedirs(output_dir, exist_ok=True)
    filename = "".join(c if c.isalnum() else "_" for c in title).lower()[:50] + ".md"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

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

def auto_push_to_github():
    try:
        subprocess.run(["git", "config", "--global", "user.name", "GitHub Actions Bot"], check=True)
        subprocess.run(["git", "config", "--global", "user.email", "actions@github.com"], check=True)
        
        tracked_paths = ["frontend/output_posts", "frontend/posts.json", "data/blog_history.db"]
        for path in tracked_paths:
            if os.path.exists(path):
                subprocess.run(["git", "add", "-f", path], check=True)

        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True).stdout.strip()
        if not status:
            logging.info("No new content to push.")
            return

        subprocess.run(["git", "commit", "-m", "Auto update with topic-relevant images"], check=True)
        subprocess.run(["git", "push"], check=True)
        logging.info("Successfully pushed updates to GitHub!")
    except Exception as e:
        logging.error(f"Git push error: {e}")

def run_pipeline():
    init_db()
    topic = fetch_random_topic()
    if not topic:
        logging.info("No new topic found.")
        return

    category, is_hot, article_content = ai_discover_category_and_generate(topic)
    success = save_to_markdown(article_content, topic["title"], category, is_hot)

    if success:
        mark_as_processed(topic["title"], topic["url"], category)
        auto_push_to_github()

if __name__ == "__main__":
    run_pipeline()