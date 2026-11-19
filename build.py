#!/usr/bin/env python3
"""Build the portfolio into _site/.

Add a write-up: drop a Markdown file into content/posts/ (front matter: title, date, slug, summary).
Add a detection: add an entry to data/detections.json. Then commit; GitHub Actions rebuilds and publishes.
Local preview: python3 build.py && python3 -m http.server -d _site 8000
"""
import datetime as dt
import html
import json
import pathlib
import re
import shutil

import markdown

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "_site"
CFG = json.loads((ROOT / "config.json").read_text())
TPL = {p.stem: p.read_text() for p in (ROOT / "templates").glob("*.html")}


def fill(tpl, **vals):
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(vals.get(m.group(1), "")), tpl)


def esc(s):
    return html.escape(str(s), quote=True)


def long_date(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B %Y')}"


def contact_links():
    links = [("GitHub", CFG.get("github"))]
    if CFG.get("linkedin"):
        links.append(("LinkedIn", CFG["linkedin"]))
    if CFG.get("email"):
        links.append(("Email", "mailto:" + CFG["email"]))
    if CFG.get("resume_pdf"):
        links.append(("Résumé (PDF)", CFG["resume_pdf"]))
    return " ".join(f'<a href="{esc(u)}">{n}</a>' for n, u in links if u)


def page(path, title, description, content, depth):
    root = "../" * depth
    doc = fill(TPL["base"], title=esc(title), description=esc(description), root=root,
               name=esc(CFG["name"]), content=content, contact_links=contact_links())
    target = OUT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(doc)


def read_posts():
    posts = []
    for f in sorted((ROOT / "content" / "posts").glob("*.md")):
        raw = f.read_text()
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
        meta = dict(line.split(": ", 1) for line in m.group(1).splitlines() if ": " in line)
        meta["body"] = markdown.markdown(m.group(2), extensions=["tables", "fenced_code"])
        posts.append(meta)
    return sorted(posts, key=lambda p: p["date"], reverse=True)


def build():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "static", OUT)
    if CFG.get("custom_domain"):
        (OUT / "CNAME").write_text(CFG["custom_domain"] + "\n")

    posts = read_posts()
    dets = json.loads((ROOT / "data" / "detections.json").read_text())
    contribs = json.loads((ROOT / "data" / "contributions.json").read_text())

    # Write-ups
    for p in posts:
        body = fill(TPL["post"], root="../../", title=esc(p["title"]), date=p["date"],
                    date_long=long_date(p["date"]), body=p["body"])
        page(f"writeups/{p['slug']}/index.html", f"{p['title']} | {CFG['name']}", p["summary"], body, 2)
    rows = "\n".join(
        f'    <li><time datetime="{p["date"]}">{long_date(p["date"])}</time>'
        f'<a href="{p["slug"]}/">{esc(p["title"])}</a><p>{esc(p["summary"])}</p></li>' for p in posts)
    page("writeups/index.html", f"Write-ups | {CFG['name']}", "Detection engineering write-ups",
         fill(TPL["list"], post_rows=rows), 1)

    # Home
    det_rows = []
    for d in dets:
        links = []
        if d.get("writeup"):
            links.append(f'<a href="writeups/{d["writeup"]}/">Write-up</a>')
        links.append(f'<a href="{esc(d["code"])}">Rules and tests</a>')
        status = "pass" if d["result"].lower() == "pass" else "review"
        det_rows.append(
            f'      <tr><td class="date">{d["date"]}</td>'
            f'<td><span class="d-title">{esc(d["title"])}</span><span class="d-area">{esc(d["area"])}</span>'
            f'<span class="d-detail">{esc(d["detail"])}</span><span class="d-links">{" ".join(links)}</span></td>'
            f'<td><a href="{esc(d["source_url"])}">{esc(d["source"])}</a></td>'
            f'<td>{esc(d["rules"])}</td><td><span class="status {status}">{esc(d["result"])}</span></td></tr>')
    con_rows = "\n".join(
        f'    <li><span class="proj">{esc(c["project"])}</span><a href="{esc(c["url"])}">{esc(c["title"])} ({esc(c["ref"])})</a>'
        f'<span class="status review">{esc(c["status"])}</span></li>' for c in contribs)
    latest = dets[0]
    wu_rows = "\n".join(
        f'    <li><time datetime="{p["date"]}">{long_date(p["date"])}</time>'
        f'<a class="post-title" href="writeups/{p["slug"]}/">{esc(p["title"])}</a>'
        f'<p>{esc(p["summary"])}</p></li>' for p in posts)
    resume_btn = (f'<a class="btn btn-quiet" href="{esc(CFG["resume_pdf"])}">Résumé (PDF)</a> '
                  if CFG.get("resume_pdf") else "")
    home = fill(TPL["home"], root="", role=esc(CFG["role"]), repo=esc(CFG["repo"]),
                linkedin=esc(CFG["linkedin"]), github=esc(CFG["github"]), resume_btn=resume_btn,
                latest_title=esc(latest["title"]),
                latest_source=esc(latest["source"]), latest_date=long_date(latest["date"]),
                detection_rows="\n".join(det_rows), contribution_rows=con_rows, writeup_rows=wu_rows)
    page("index.html", f"{CFG['name']} — detection engineering & home SOC", CFG["role"], home, 0)

    # About
    page("about/index.html", f"About | {CFG['name']}", "About Mohammed Alkahala",
         fill(TPL["about"], repo=esc(CFG["repo"]), contact_links=contact_links()), 1)
    print(f"built {len(posts)} write-up(s), {len(dets)} detection(s) into {OUT}")


if __name__ == "__main__":
    build()
