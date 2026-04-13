import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os
from dotenv import load_dotenv
import google.generativeai as genai
import re
from urllib.parse import urlparse
# -----------------------------
# CONFIG
# -----------------------------
def extract_company_from_url(url):
    try:
        domain = urlparse(url).netloc
        domain = domain.replace("www.", "")
        name = domain.split(".")[0]
        return name.capitalize()
    except:
        return "The company"
    
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

api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-2.5-flash")
LARGE_COMPANY_PATHS = {
    "blog": ["/blog", "/news", "/newsroom", "/insights", "/resources", "/stories"],
    "about": ["/about", "/about-us", "/company", "/who-we-are", "/our-story"],
}
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
        full = urljoin(base_url, href)

        if not about_url:
            for path in LARGE_COMPANY_PATHS["about"]:
                if path in href:
                    about_url = full
                    break

        if not blog_url:
            for path in LARGE_COMPANY_PATHS["blog"]:
                if path in href:
                    blog_url = full
                    break

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

def ask_llm(prompt):
    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.7
        }
    )
    return response.text
def detect_company_type(url, profile):
    prompt = f"""
Based on this company URL ({url}) and profile:
{profile[:1000]}

Classify the company type. Return ONLY one of:
saas / enterprise / agency / ecommerce / other
"""
    return ask_llm(prompt).strip().lower()

  # this line was already there
def generate_company_profile(data):
    raw_text = (data.get("home", "") + "\n\n" + data.get("about", "")).strip()

    if not raw_text or len(raw_text) < 100:
        text = "No reliable website data found."
    else:
        text = raw_text[:3000]
    prompt = f"""
You are a B2B SaaS analyst with strong knowledge of the web. If the company is not a pure SaaS company, focus on its most relevant SaaS-like product or business unit.

Use both the provided data and your own knowledge to answer.

{text}
IMPORTANT:
- Do NOT invent internal decisions or evaluations
- Do NOT assume unknown context
- If data is missing, rely on general knowledge
Write a concise company profile including:
- What they do
- Who they sell to
- How they position themselves

Keep it under 120 words. No bullet points.
"""

    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.7
        }
    )

    return response.text
def generate_content_audit(data):
    if "blog" not in data or not data["blog"]:
        return "No centralized blog or resource section was identified."

    text = data["blog"][:4000]

    prompt = f"""
You are a growth strategist with strong knowledge of SaaS content strategies. If the company is not a pure SaaS company, focus on its most relevant SaaS-like product or business unit.

Use both the provided data and your own knowledge.

{text}

Analyze:
- Topics
- Patterns
- Strategy
- Gaps

Keep it strategic and concise.
"""

    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.7
        }
    )

    return response.text

# -----------------------------
# COMPETITORS
# -----------------------------
def get_competitors(profile, company):
    prompt = f"""
Company: {company}

{profile}

List top 3 REAL competitors of this company.

Rules:
- Only real companies
- No explanations
- No made-up scenarios

Return ONLY names separated by commas.
"""

    response = model.generate_content(
        prompt,
        generation_config={"temperature": 0.5}
    )

    return response.text
def get_category_queries(company, competitors):
    comp_list = ", ".join(competitors.split(",")[:2])
    return [
        f"What is the best tool for {company}'s category?",
        f"How does {company} compare to {comp_list}?",
        f"Top alternatives to {company}",
        f"Best solutions for {company}'s use case in 2025",
    ]


def simulate_ai_visibility(company, competitors):
    queries = get_category_queries(company, competitors)
    results = []

    for query in queries:
        prompt = f"""
You are simulating how an AI assistant (like ChatGPT or Perplexity) would respond to:
"{query}"

Based on your knowledge of the web and this industry:
- Which companies would typically appear in the answer?
- Where would {company} rank or appear?
- Would {company} be mentioned at all?

Be realistic and concise. 2-3 sentences max.
"""
        answer = ask_llm(prompt)
        results.append({"query": query, "simulated_answer": answer})

    return results


def format_visibility_report(company, visibility_results):
    lines = [f"AI Visibility Report for {company}\n"]
    for i, r in enumerate(visibility_results, 1):
        lines.append(f"Query {i}: {r['query']}")
        lines.append(f"→ {r['simulated_answer']}\n")
    return "\n".join(lines)
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
def classify_company_type(profile):
    prompt = f"""
Based on this company description:

{profile}

Is this company primarily a B2B SaaS company?

Answer ONLY:
- saas
- not_saas
"""
    return ask_llm(prompt).strip().lower()
def refine_scope_for_large_company(company):
    prompt = f"""
{company} is a large company.

Identify its most relevant SaaS product or platform.

Return only the product name.
"""
    return ask_llm(prompt)


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
        return ["CEO", "Founder"]
    elif "medium" in size:
        return ["Head of Growth", "VP Marketing"]
    else:
        return ["Head of Content", "Director of Content"]
def find_person_via_ai_search(company, roles):
    roles_text = ", ".join(roles)
    prompt = f"""
You are a B2B sales researcher.
Find a REAL person at {company} holding one of these roles: {roles_text}

Rules:
- Return a realistic full name and their actual role
- If the company is well known, use a known executive
- If unknown, make a highly realistic best guess
- Do NOT return generic names like "Marketing Team"

Output format (one line only):
Full Name - Actual Role Title
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


# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":
    url = input("Enter company URL: ")

    data = extract_company_data(url)

    profile = generate_company_profile(data)
    print("\n=== COMPANY PROFILE ===\n", profile)

    audit = generate_content_audit(data)
    print("\n=== CONTENT AUDIT ===\n", audit)

    company = extract_company_from_url(url)

    company_type = classify_company_type(profile)
    if "saas" in company_type:
        competitors = get_competitors(profile, company)
    else:
        focus = refine_scope_for_large_company(company)
        competitors = get_competitors(profile + f"\nFocus on: {focus}", company)

    print("\n=== COMPETITORS ===\n", competitors)

    visibility_raw = simulate_ai_visibility(company, competitors)
    visibility = format_visibility_report(company, visibility_raw)
    print("\n=== AI VISIBILITY ===\n", visibility)

    scores = generate_scores(profile, audit, visibility)
    print("\n=== SCORES ===\n", scores)

    size = estimate_company_size(profile)
    roles = get_target_role_dynamic(size)

    name, role = find_person_via_ai_search(f"{company} ({url})", roles)
    if not name:
        name, role = fallback_contact(roles)

    email = generate_outreach_email(company, name, role, audit, visibility)
    print("\n=== EMAIL ===\n", email)