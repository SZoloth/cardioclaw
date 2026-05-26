import os
import re
import json
import feedparser
from openai import OpenAI
from Bio import Entrez
from anthropic import Anthropic
from datetime import datetime, timedelta

# =============================================================================
# CARDIOLOGY CLAW V3.0 — Nuclear Cardiology Briefing for Blind MD User
# Uses OpenAI TTS gpt-4o-mini-tts for natural voice quality
# =============================================================================

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
except ImportError:
    pass

Entrez.email = "zoloth1@verizon.net"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

ALERT_EMAIL_TO = os.environ.get("ALERT_EMAIL_TO", "")
ALERT_EMAIL_FROM = os.environ.get("ALERT_EMAIL_FROM", "")
ALERT_EMAIL_PASSWORD = os.environ.get("ALERT_EMAIL_PASSWORD", "")

MAX_NUCLEAR_ARTICLES = 4
MAX_GENERAL_ARTICLES = 3
MAX_RSS_ITEMS = 2
MAX_FINDINGS = 8
MAX_ABSTRACT_CHARS = 12000

OUTPUT_DIR = os.path.expanduser("~/CardioClaw/output")
EPISODES_FILE = os.path.join(OUTPUT_DIR, "episodes.json")
BACKUP_DIR = os.path.expanduser("~/CardioClaw/output_prev")

CLAUDE_MODEL = "claude-sonnet-4-6"
OPENAI_TTS_MODEL = "gpt-4o-mini-tts"
OPENAI_VOICE = "nova"
OPENAI_TTS_INSTRUCTIONS = (
    "Speak clearly and professionally at a measured, calm pace. "
    "You are a knowledgeable medical colleague briefing a physician. "
    "Pronounce medical terminology carefully and accurately. "
    "Pause naturally between sentences. Do not rush."
)

NUCLEAR_CARDIOLOGY_TERMS = (
    "nuclear cardiology[MeSH Terms] OR cardiac PET OR "
    "myocardial perfusion imaging OR cardiac SPECT OR "
    "coronary flow reserve OR cardiac amyloid OR "
    "cardiac sarcoidosis OR radionuclide ventriculography OR "
    "PET myocardial OR flurpiridaz OR "
    "cardiac molecular imaging OR myocardial blood flow"
)

GENERAL_CARDIOLOGY_TERMS = (
    "cardiology AND ("
    "randomized controlled trial[pt] OR "
    "guideline[pt] OR "
    "meta-analysis[pt] OR "
    "practice guideline[pt]"
    ")"
)

GOOGLE_NEWS_FEEDS = {
    "Nuclear Cardiology News":   "https://news.google.com/rss/search?q=nuclear+cardiology&hl=en-US&gl=US&ceid=US:en",
    "Cardiac PET News":          "https://news.google.com/rss/search?q=cardiac+PET+imaging&hl=en-US&gl=US&ceid=US:en",
    "ASNC News":                 "https://news.google.com/rss/search?q=ASNC+nuclear+cardiology&hl=en-US&gl=US&ceid=US:en",
    "Myocardial Perfusion News": "https://news.google.com/rss/search?q=myocardial+perfusion+imaging&hl=en-US&gl=US&ceid=US:en",
}

GENERAL_FEEDS = {
    "AHA Circulation":        "https://www.ahajournals.org/action/showFeed?type=etoc&feed=rss&jc=circ",
    "JACC":                   "https://www.jacc.org/action/showFeed?type=etoc&feed=rss&jc=jacc",
    "BMJ Heart":              "https://heart.bmj.com/rss/current.xml",
    "ACC":                    "https://www.acc.org/rss/latest-in-cardiology",
    "NEJM":                   "https://www.nejm.org/action/showFeed?jc=nejm&type=etoc&feed=rss",
    "Lancet":                 "https://www.thelancet.com/rssfeed/lancet_online.xml",
    "JAMA Cardiology":        "https://jamanetwork.com/journals/jamacardiology/rss",
    "ESC":                    "https://www.escardio.org/rss/guidelines-news.xml",
    "European Heart Journal": "https://academic.oup.com/rss/site_5375/3158.xml",
    "Journal of Nuclear Medicine": "https://jnm.snmjournals.org/rss/ahead.xml",
}

DAILY_FEEDS = {
    "AHA Circulation":        "https://www.ahajournals.org/action/showFeed?type=etoc&feed=rss&jc=circ",
    "JACC":                   "https://www.jacc.org/action/showFeed?type=etoc&feed=rss&jc=jacc",
    "BMJ Heart":              "https://heart.bmj.com/rss/current.xml",
    "ACC":                    "https://www.acc.org/rss/latest-in-cardiology",
    "Journal of Nuclear Medicine": "https://jnm.snmjournals.org/rss/ahead.xml",
}


def fetch_rss_content(feeds, label, max_items_per_feed=MAX_RSS_ITEMS):
    print(f"DEBUG: Fetching {len(feeds)} {label} feed(s)...")
    all_content = []
    for name, url in feeds.items():
        try:
            feed = feedparser.parse(
                url,
                request_headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
            )
            if not feed.entries:
                print(f"  {name}: no entries.")
                continue
            items = feed.entries[:max_items_per_feed]
            print(f"  {name}: {len(items)} item(s).")
            for item in items:
                title = item.get("title", "No title")
                summary = item.get("summary", item.get("description", ""))
                summary = re.sub(r"<[^>]+>", " ", summary).strip()
                summary = " ".join(summary.split())[:300]
                all_content.append(f"[{name}] {title}\n{summary}")
        except Exception as e:
            print(f"  {name}: Failed — {e}")
    print(f"DEBUG: {label} RSS total — {len(all_content)} item(s).")
    return "\n\n".join(all_content)


def search_pubmed(search_term, from_date, to_date, max_results):
    full_term = f"({search_term}) AND {from_date}:{to_date}[Publication Date]"
    print(f"DEBUG: PubMed search ({max_results} max)...")
    with Entrez.esearch(db="pubmed", term=full_term, retmax=max_results) as handle:
        record = Entrez.read(handle)
    ids = record["IdList"]
    print(f"DEBUG: Found {len(ids)} article(s).")
    return ids


def fetch_pubmed_abstracts(ids):
    if not ids:
        return ""
    print(f"DEBUG: Fetching {len(ids)} abstracts...")
    with Entrez.efetch(db="pubmed", id=ids, rettype="abstract", retmode="text") as handle:
        raw_text = handle.read()
    raw_text = raw_text[:MAX_ABSTRACT_CHARS]
    print(f"DEBUG: Received {len(raw_text)} characters.")
    return raw_text


def summarize_with_claude(content, briefing_type, timeframe, total_sources):
    print(f"DEBUG: Sending to {CLAUDE_MODEL}...")
    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    today_str = datetime.now().strftime("%B %d, %Y")
    day_name = datetime.now().strftime("%A")

    if briefing_type == "weekly":
        scope = "the past 7 days"
        word_limit = 80
        briefing_label = "weekly"
    else:
        scope = timeframe
        word_limit = 60
        briefing_label = "daily"

    prompt = (
        f"You are preparing a {briefing_label} nuclear cardiology briefing "
        f"for a blind retired physician who is a nuclear cardiologist. "
        f"The listener cannot see anything — this will be read aloud as audio episodes. "
        f"Content covers {scope}. Today is {day_name}, {today_str}.\n\n"
        f"CRITICAL FORMAT — return EXACTLY this structure, one finding per line:\n\n"
        f"FINDING_1|[Source]: [Finding text]\n"
        f"FINDING_2|[Source]: [Finding text]\n"
        f"... up to {MAX_FINDINGS} findings maximum ...\n\n"
        f"DO NOT include INTRO or OUTRO — those are added automatically.\n"
        f"Return ONLY the FINDING lines, nothing else.\n\n"
        f"CONTENT RULES:\n"
        f"- Plain text only. No markdown, asterisks, dashes, bullets, or symbols.\n"
        f"- Each finding is one self-contained paragraph of {word_limit} words or less.\n"
        f"- Written as natural spoken sentences.\n"
        f"- Mention the source naturally in the finding text itself.\n"
        f"- Each finding must make complete sense on its own.\n\n"
        f"PRIORITISATION:\n"
        f"1. Nuclear cardiology guidelines from ASNC or SNMMI — ALWAYS LEAD\n"
        f"2. New nuclear imaging techniques, tracers, or protocols\n"
        f"3. PET or SPECT trial results with direct clinical impact\n"
        f"4. Nuclear cardiology news — conferences, regulatory approvals\n"
        f"5. General cardiology guideline changes from ACC or AHA\n"
        f"6. Major RCT results relevant to nuclear cardiology\n"
        f"7. Other significant general cardiology findings\n\n"
        f"QUALITY:\n"
        f"- Note if small, observational, or preliminary\n"
        f"- Flag if finding changes current practice\n"
        f"- For general findings note nuclear imaging relevance\n\n"
        f"Content:\n\n{content}"
    )

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.content[0].text
    print(f"DEBUG: Raw response ({len(raw)} chars).")
    return raw


def parse_findings(raw_text):
    findings = []
    lines = raw_text.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("FINDING_"):
            try:
                header, text = line.split(":", 1)
                if "|" in header:
                    _, source = header.split("|", 1)
                else:
                    source = "Research"
                findings.append({
                    "source": source.strip(),
                    "text": text.strip()
                })
            except Exception as e:
                print(f"  Parse error: {line[:50]} — {e}")
    print(f"DEBUG: Parsed {len(findings)} finding(s).")
    return findings


def build_episodes(findings, briefing_type, today_str, day_name):
    episodes = []
    total = len(findings)

    if briefing_type == "weekly":
        briefing_label = "weekly"
        scope_phrase = "This week's briefing covers the past seven days."
    else:
        briefing_label = "daily"
        scope_phrase = "Today's briefing covers the latest findings."

    if total == 0:
        intro_text = (
            f"Good morning. Today is {day_name}, {today_str}. "
            f"This is your {briefing_label} nuclear cardiology briefing. "
            f"There are no new findings available today. Please check back tomorrow."
        )
    else:
        intro_text = (
            f"Good morning. Today is {day_name}, {today_str}. "
            f"This is your {briefing_label} nuclear cardiology briefing. "
            f"{scope_phrase} "
            f"You have {total} finding{'s' if total > 1 else ''} today. "
            f"Nuclear cardiology findings appear first, followed by general cardiology. "
            f"Say next episode to advance to the first finding."
        )

    episodes.append({
        "type": "intro",
        "title": f"Introduction — {today_str}",
        "text": intro_text
    })

    for i, finding in enumerate(findings, 1):
        if i == 1:
            position_phrase = f"Finding {i} of {total}."
            nav_phrase = "Say next episode for the next finding." if total > 1 else "Say next episode for the conclusion."
        elif i == total:
            position_phrase = f"Finding {i} of {total}. This is the final finding."
            nav_phrase = "Say next episode for the conclusion."
        else:
            position_phrase = f"Finding {i} of {total}."
            nav_phrase = "Say next episode to continue."

        finding_text = (
            f"{position_phrase} "
            f"{finding['text']} "
            f"{nav_phrase}"
        )

        episodes.append({
            "type": "finding",
            "title": f"Finding {i} of {total} — {finding['source']}",
            "text": finding_text
        })

    if total > 0:
        outro_text = (
            f"That concludes your {briefing_label} nuclear cardiology briefing "
            f"for {day_name}, {today_str}. "
            f"You heard {total} finding{'s' if total > 1 else ''} today. "
            f"Have a good day."
        )
        episodes.append({
            "type": "outro",
            "title": f"Conclusion — {today_str}",
            "text": outro_text
        })

    return episodes


def generate_audio(episodes, today_str):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    episode_meta = []
    client = OpenAI(api_key=OPENAI_API_KEY)
    date_tag = datetime.now().strftime("%Y%m%d")

    # Back up current episodes before overwriting
    backup_current_episodes()

    # Clear old episode files
    for f in os.listdir(OUTPUT_DIR):
        if f.startswith("episode_") and f.endswith(".mp3"):
            os.remove(os.path.join(OUTPUT_DIR, f))
    if os.path.exists(EPISODES_FILE):
        os.remove(EPISODES_FILE)

    for i, ep in enumerate(episodes):
        filename = f"episode_{i:02d}_{ep['type']}_{date_tag}.mp3"
        filepath = os.path.join(OUTPUT_DIR, filename)

        print(f"DEBUG: Generating audio — {ep['title']}...")
        try:
            response = client.audio.speech.create(
                model=OPENAI_TTS_MODEL,
                voice=OPENAI_VOICE,
                input=ep["text"],
                instructions=OPENAI_TTS_INSTRUCTIONS
            )
            response.stream_to_file(filepath)
            size = os.path.getsize(filepath)
            print(f"  Saved: {filename} ({size // 1024} KB)")

            episode_meta.append({
                "filename": filename,
                "title": ep["title"],
                "text": ep["text"],
                "type": ep["type"],
                "date": today_str,
                "size": size
            })
        except Exception as e:
            print(f"  Audio generation failed for {ep['title']}: {e}")

    with open(EPISODES_FILE, "w") as f:
        json.dump(episode_meta, f, indent=2)

    print(f"\nSuccess: {len(episode_meta)} episode(s) generated.")
    return episode_meta


def generate_error_episode(message, today_str):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    client = OpenAI(api_key=OPENAI_API_KEY)
    filename = "episode_00_error.mp3"
    filepath = os.path.join(OUTPUT_DIR, filename)
    try:
        response = client.audio.speech.create(
            model=OPENAI_TTS_MODEL,
            voice=OPENAI_VOICE,
            input=message,
            instructions=OPENAI_TTS_INSTRUCTIONS
        )
        response.stream_to_file(filepath)
        size = os.path.getsize(filepath)
        episodes = [{
            "filename": filename,
            "title": f"System Message — {today_str}",
            "text": message,
            "type": "error",
            "date": today_str,
            "size": size
        }]
        with open(EPISODES_FILE, "w") as f:
            json.dump(episodes, f, indent=2)
    except Exception as e:
        print(f"Error episode generation failed: {e}")


def send_alert_email(subject, body):
    """Send an email alert via Gmail SMTP. Silently skips if credentials not set."""
    if not all([ALERT_EMAIL_TO, ALERT_EMAIL_FROM, ALERT_EMAIL_PASSWORD]):
        print("Email alert skipped — credentials not configured in .env")
        return
    try:
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText(body)
        msg["Subject"] = f"[Cardio Claw] {subject}"
        msg["From"] = ALERT_EMAIL_FROM
        msg["To"] = ALERT_EMAIL_TO
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(ALERT_EMAIL_FROM, ALERT_EMAIL_PASSWORD)
            server.sendmail(ALERT_EMAIL_FROM, ALERT_EMAIL_TO, msg.as_string())
        print(f"Alert email sent: {subject}")
    except Exception as e:
        print(f"Alert email failed (non-fatal): {e}")


def backup_current_episodes():
    """Copy current episodes to backup dir before overwriting."""
    if not os.path.exists(EPISODES_FILE):
        return
    try:
        import shutil
        os.makedirs(BACKUP_DIR, exist_ok=True)
        for f in os.listdir(BACKUP_DIR):
            os.remove(os.path.join(BACKUP_DIR, f))
        for f in os.listdir(OUTPUT_DIR):
            if f.startswith("episode_") and f.endswith(".mp3"):
                shutil.copy2(os.path.join(OUTPUT_DIR, f), os.path.join(BACKUP_DIR, f))
        shutil.copy2(EPISODES_FILE, os.path.join(BACKUP_DIR, "episodes.json"))
        print("DEBUG: Current episodes backed up to output_prev/")
    except Exception as e:
        print(f"DEBUG: Backup failed (non-fatal): {e}")


def restore_backup_episodes():
    """Restore previous week's episodes if the current run failed."""
    backup_json = os.path.join(BACKUP_DIR, "episodes.json")
    if not os.path.exists(backup_json):
        print("DEBUG: No backup episodes available to restore.")
        return False
    try:
        import shutil
        for f in os.listdir(OUTPUT_DIR):
            if f.startswith("episode_") and f.endswith(".mp3"):
                os.remove(os.path.join(OUTPUT_DIR, f))
        if os.path.exists(EPISODES_FILE):
            os.remove(EPISODES_FILE)
        for f in os.listdir(BACKUP_DIR):
            shutil.copy2(os.path.join(BACKUP_DIR, f), os.path.join(OUTPUT_DIR, f))
        print("DEBUG: Previous episodes restored from output_prev/")
        return True
    except Exception as e:
        print(f"DEBUG: Restore failed: {e}")
        return False


def main():
    today = datetime.now()
    is_monday = today.weekday() == 0
    briefing_type = "weekly" if is_monday else "daily"
    today_str = today.strftime("%B %d, %Y")
    day_name = today.strftime("%A")

    print("=" * 60)
    print(f"  CARDIOLOGY CLAW V3.0 — OpenAI TTS — {briefing_type.upper()}")
    print(f"  {today.strftime('%A, %B %d %Y at %I:%M %p')}")
    print("=" * 60)

    if not ANTHROPIC_API_KEY or not OPENAI_API_KEY:
        print("ERROR: API keys not configured. Check .env file.")
        send_alert_email(
            "FAILED — API keys missing",
            f"Cardio Claw failed on {day_name}, {today_str}.\n\n"
            f"API keys are not set. Check the .env file on the Oracle server "
            f"at ~/CardioClaw/.env and ensure ANTHROPIC_API_KEY and OPENAI_API_KEY are present."
        )
        return

    yesterday_str = (today - timedelta(days=1)).strftime("%Y/%m/%d")
    today_date_str = today.strftime("%Y/%m/%d")
    thirty_days_str = (today - timedelta(days=30)).strftime("%Y/%m/%d")
    seven_days_str = (today - timedelta(days=7)).strftime("%Y/%m/%d")

    if is_monday:
        from_date = seven_days_str
        to_date = today_date_str
        timeframe = "the past 7 days"
        journal_feeds = GENERAL_FEEDS
    else:
        from_date = yesterday_str
        to_date = today_date_str
        timeframe = "yesterday"
        journal_feeds = DAILY_FEEDS

    try:
        google_content = fetch_rss_content(GOOGLE_NEWS_FEEDS, "Google News")
        journal_content = fetch_rss_content(journal_feeds, "Journal")

        print("\nSearching PubMed — nuclear cardiology...")
        nuclear_ids = search_pubmed(
            NUCLEAR_CARDIOLOGY_TERMS, from_date, to_date, MAX_NUCLEAR_ARTICLES
        )

        print("Searching PubMed — general cardiology high impact...")
        general_ids = search_pubmed(
            GENERAL_CARDIOLOGY_TERMS, from_date, to_date, MAX_GENERAL_ARTICLES
        )

        if not is_monday and not nuclear_ids and not general_ids:
            print("Nothing from yesterday. Falling back to 30 days...")
            from_date = thirty_days_str
            timeframe = "the past 30 days"
            nuclear_ids = search_pubmed(
                NUCLEAR_CARDIOLOGY_TERMS, from_date, today_date_str, MAX_NUCLEAR_ARTICLES
            )
            general_ids = search_pubmed(
                GENERAL_CARDIOLOGY_TERMS, from_date, today_date_str, MAX_GENERAL_ARTICLES
            )

        nuclear_content = fetch_pubmed_abstracts(nuclear_ids)
        general_content = fetch_pubmed_abstracts(general_ids)

        combined = ""
        source_count = 0

        if nuclear_content:
            combined += "=== PRIMARY: NUCLEAR CARDIOLOGY — PUBMED ===\n\n" + nuclear_content + "\n\n"
            source_count += len(nuclear_ids)

        if general_content:
            combined += "=== PRIMARY: GENERAL CARDIOLOGY — PUBMED ===\n\n" + general_content + "\n\n"
            source_count += len(general_ids)

        if journal_content:
            combined += "=== JOURNAL RSS ===\n\n" + journal_content + "\n\n"
            source_count += 1

        if google_content:
            combined += (
                "=== SECONDARY: NUCLEAR CARDIOLOGY NEWS ===\n"
                "Use only for society announcements or regulatory news not in PubMed above.\n\n"
                + google_content
            )
            source_count += 1

        combined = combined[:25000]

        if not combined.strip():
            msg = (
                f"Good morning. Today is {day_name}, {today_str}. "
                f"This is your {briefing_type} nuclear cardiology briefing. "
                f"There are no new findings available today. Please check back tomorrow."
            )
            generate_error_episode(msg, today_str)
            return

        raw = summarize_with_claude(combined, briefing_type, timeframe, source_count)
        findings = parse_findings(raw)

        if not findings:
            print("ERROR: No findings parsed.")
            msg = (
                f"Good morning. Today is {day_name}, {today_str}. "
                f"The briefing system encountered a formatting error. "
                f"Please check the system logs."
            )
            generate_error_episode(msg, today_str)
            return

        episodes = build_episodes(findings, briefing_type, today_str, day_name)
        generate_audio(episodes, today_str)

        finding_count = len(episodes) - 2  # exclude intro and outro
        send_alert_email(
            f"OK — {finding_count} findings — {today_str}",
            f"Cardio Claw ran successfully on {day_name}, {today_str}.\n\n"
            f"{finding_count} findings generated.\n\n"
            f"Feed: http://157.151.155.75:5000/feed.xml"
        )

        print("\n--- EPISODE LIST ---")
        for ep in episodes:
            print(f"  {ep['title']}")
        if len(episodes) > 1:
            print(f"\n--- FIRST FINDING PREVIEW ---")
            print(episodes[1]['text'][:300] + "...")
        print("-" * 40)

    except Exception as e:
        import traceback
        print(f"\nSystem Error: {str(e)}")
        traceback.print_exc()

        # Restore previous week's episodes so the feed isn't empty
        restored = restore_backup_episodes()
        restore_note = (
            "Previous week's episodes have been restored to the feed."
            if restored else
            "No backup episodes were available."
        )

        # Alert Steve
        send_alert_email(
            f"FAILED — {today_str}",
            f"Cardio Claw failed on {day_name}, {today_str}.\n\n"
            f"Error: {str(e)}\n\n"
            f"{restore_note}\n\n"
            f"Check log: ~/CardioClaw/cardio_claw.log"
        )

        # Only generate spoken error episode if no backup to fall back on
        if not restored:
            msg = (
                f"Good morning. Today is {day_name}, {today_str}. "
                f"The cardiology briefing system encountered an error "
                f"and was unable to generate this week's findings. "
                f"Please check the system logs."
            )
            try:
                generate_error_episode(msg, today_str)
            except Exception:
                pass


if __name__ == "__main__":
    main()
