import os
import json
from flask import Flask, send_file, Response
from datetime import datetime

app = Flask(__name__)

OUTPUT_DIR = os.path.expanduser("~/CardioClaw/output")
EPISODES_FILE = os.path.join(OUTPUT_DIR, "episodes.json")

SERVER_IP = "157.151.155.75"
PORT = 5000


def load_episodes():
    if not os.path.exists(EPISODES_FILE):
        return []
    with open(EPISODES_FILE, "r") as f:
        return json.load(f)


@app.route("/")
def index():
    episodes = load_episodes()
    return "Cardiology Claw V3.0 — " + str(len(episodes)) + " episode(s) available."


@app.route("/audio/<filename>")
def audio(filename):
    filepath = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(filepath):
        return send_file(filepath, mimetype="audio/mpeg")
    return "File not found", 404


@app.route("/feed.xml")
def feed():
    episodes = load_episodes()

    if not episodes:
        return Response("No episodes available yet.", status=404)

    now = datetime.now()
    build_date = now.strftime("%a, %d %b %Y %H:%M:%S +0000")
    date_str = now.strftime("%B %d %Y")

    items = ""
    for i, ep in enumerate(episodes):
        audio_url = "http://" + SERVER_IP + ":" + str(PORT) + "/audio/" + ep["filename"]
        guid = SERVER_IP + "-" + ep["filename"] + "-" + ep.get("date", date_str).replace(" ", "")
        description = ep["text"][:300].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        items += """
    <item>
      <title>""" + ep["title"] + """</title>
      <description>""" + description + """</description>
      <pubDate>""" + build_date + """</pubDate>
      <enclosure url=\"""" + audio_url + """\" length=\"""" + str(ep["size"]) + """\" type="audio/mpeg"/>
      <guid isPermaLink="false">""" + guid + """</guid>
      <itunes:episode>""" + str(i + 1) + """</itunes:episode>
    </item>"""

    rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Cardiology Report</title>
    <description>Nuclear cardiology briefing — each finding as a separate episode</description>
    <language>en-us</language>
    <lastBuildDate>""" + build_date + """</lastBuildDate>
    <itunes:author>Cardiology Claw</itunes:author>
    <itunes:category text="Health"/>
    <itunes:explicit>false</itunes:explicit>
    <itunes:type>episodic</itunes:type>
    """ + items + """
  </channel>
</rss>"""

    return Response(rss, mimetype="application/rss+xml")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
