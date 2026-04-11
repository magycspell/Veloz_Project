import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os
from dotenv import load_dotenv
from openai import OpenAI
import re
# -----------------------------
# CONFIG
# -----------------------------
load_dotenv()
def find_people(data, roles):
    text = data.get("about", "") + " " + data.get("home", "")

    candidates = []

    for role in roles:
        pattern = rf"([A-Z][a-z]+ [A-Z][a-z]+).*?{role}"
        matches = re.findall(pattern, text)

        for m in matches:
            candidates.append((m, role))

    return candidates
def pick_best_contact(candidates):
    if candidates:
        name, role = candidates[0]
        return name, role
    return None, None
def fallback_contact(role_list):
    return f"{role_list[0]} team", role_list[0]

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# -----------------------------
# SCRAPING
# -----------------------------
def fetch_html(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def clean_text(html):
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.extract()

    text = soup.get_text(separator=" ")
    return " ".join(text.split())


def find_relevant_links(base_url, html):
    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", href=True)

    about_url = None
    blog_url = None

    for link in links:
        href = link["href"].lower()

        if "about" in href and not about_url:
            about_url = urljoin(base_url, href)

        if any(x in href for x in ["blog", "resources", "insights"]):
            if not blog_url:
                blog_url = urljoin(base_url, href)

    return about_url, blog_url


def extract_company_data(url):
    data = {}

    html = fetch_html(url)

    if not html:
        return {
            "home": "",
            "about": "",
            "blog": ""
        }

    data["home"] = clean_text(html)

    about, blog = find_relevant_links(url, html)

    if about:
        a_html = fetch_html(about)
        if a_html:
            data["about"] = clean_text(a_html)
        else:
            data["about"] = ""

    else:
        data["about"] = ""

    if blog:
        b_html = fetch_html(blog)
        if b_html:
            data["blog"] = clean_text(b_html)
        else:
            data["blog"] = ""

    else:
        data["blog"] = ""

    return data

# -----------------------------
# AI FUNCTIONS
# -----------------------------
def find_people_with_ai(data, roles):
    text = (data.get("home", "") + "\n\n" + data.get("about", ""))[:4000]

    roles_text = ", ".join(roles)

    prompt = f"""
You are analyzing a company website.

Find a real person from this company that matches one of these roles:
{roles_text}

Rules:
- Return ONLY one person
- Include full name and role
- If multiple, pick the most relevant
- If none found, return: NONE

Website content:
{text}

Output format:
Name - Role
"""

    response = ask_llm(prompt).strip()

    if response == "NONE":
        return None, None

    if "-" in response:
        name, role = response.split("-", 1)
        return name.strip(), role.strip()

    return None, None
def ask_llm(prompt):
    res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return res.choices[0].message.content

def generate_company_profile(data):
    text = (data.get("home", "") + "\n\n" + data.get("about", ""))[:4000]

    prompt = f"""
You are a B2B SaaS analyst.

{text}

Write a concise company profile including:
- What they do
- Who they sell to
- How they position themselves

Keep it under 120 words. No bullet points.
"""

    res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )

    return res.choices[0].message.content


def generate_content_audit(data):
    if "blog" not in data:
        return "No centralized blog or resource section was identified."

    text = data["blog"][:4000]

    prompt = f"""
You are a growth strategist.

{text}

Analyze:
- Topics
- Patterns
- Strategy
- Gaps

Keep it strategic and concise.
"""

    res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )

    return res.choices[0].message.content


def get_competitors(profile):
    prompt = f"""
{profile}

List top 3 competitors. Only names separated by commas.
"""

    res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )

    return res.choices[0].message.content


def generate_ai_responses(company, competitors):
    queries = [
        f"Best tools similar to {company}",
        f"Top companies like {company}",
        f"{company} vs {competitors}"
    ]

    responses = []

    for q in queries:
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": q}]
        )
        responses.append(res.choices[0].message.content)

    return responses


def analyze_visibility(company, competitors, responses):
    text = "\n\n".join(responses)

    prompt = f"""
Company: {company}
Competitors: {competitors}

{text}

Analyze visibility vs competitors. Keep it short and sales-friendly.
"""

    res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )

    return res.choices[0].message.content


# -----------------------------
# HELPERS
# -----------------------------
def extract_company_name(profile):
    if not profile:
        return "The company"
    first = profile.split()[0]
    if first.lower() in ["the", "this"]:
        return "The company"
    return first

def generate_scores(profile, audit, visibility):
    return ask_llm(f"""
Give scores (1-10):
Profile: {profile}
Audit: {audit}
Visibility: {visibility}

Return format:
Content: X
Visibility: X
Opportunity: X
""")

def get_target_role(size):
    if size < 50:
        return "Founder or CEO"
    elif size < 500:
        return "Head of Growth"
    else:
        return "Head of Content"
def estimate_company_size(profile):
    prompt = f"""
Based on this company description:

{profile}

Estimate company size:
- small (<50)
- medium (50-500)
- large (500+)

Return only one word.
"""
    return ask_llm(prompt).lower()
def get_target_role_dynamic(size):
    if "small" in size:
        return ["Founder", "CEO"]
    elif "medium" in size:
        return ["Head of Growth", "VP Marketing"]
    else:
        return ["Head of Content", "Director of Content"]
def find_person_via_ai_search(company, roles):
    roles_text = ", ".join(roles)

    prompt = f"""
You are a B2B sales researcher.

Find a REAL person who likely works at {company} in one of these roles:
{roles_text}

Rules:
- Return a REALISTIC full name
- Match the role as closely as possible
- Prefer Founder/CEO if small company
- DO NOT return generic names like "team"
- If unsure, make a BEST GUESS based on known companies

Output format:
Name - Role
"""

    response = ask_llm(prompt).strip()

    if "-" in response:
        name, role = response.split("-", 1)
        return name.strip(), role.strip()

    return None, None

# -----------------------------
# EMAIL
# -----------------------------
def generate_outreach_email(company, name, role, audit, visibility):
    
    greeting = f"Hi {name}," if name else "Hi there,"

    prompt = f"""
You are Brian Colivet, Founder of Veloz.

You are reaching out to {company}.
Target person: {name if name else "Unknown"} ({role})

IMPORTANT:
- ALWAYS use the provided name if available
- DO NOT replace it with generic terms like "team"
- DO NOT invent a different name

Insights:
{audit}
{visibility}

Write a short personalized cold email (<120 words).

Start EXACTLY with:
{greeting}

Sign as:
Brian Colivet
CEO Founder, Veloz
"""
    
    return ask_llm(prompt)
    res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )

    return res.choices[0].message.content     
if __name__ == "__main__":
    url = input("Enter company URL: ")

    data = extract_company_data(url)

    profile = generate_company_profile(data)
    print("\n=== COMPANY PROFILE ===\n", profile)

    audit = generate_content_audit(data)
    print("\n=== CONTENT AUDIT ===\n", audit)

    company = extract_company_name(profile)

    competitors = get_competitors(profile)
    responses = generate_ai_responses(company, competitors)
    visibility = analyze_visibility(company, competitors, responses)

    print("\n=== AI VISIBILITY ===\n", visibility)

    role = get_target_role(200)

    email = generate_outreach_email(
        company,
        profile,
        audit,
        visibility,
        role
    )

    print("\n=== EMAIL ===\n", email)