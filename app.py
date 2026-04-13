import streamlit as st
from Backend_pipeline import *

st.set_page_config(page_title="Veloz AI", layout="wide")

st.title("🚀 Prospect Intelligence Engine")
st.markdown("Turn any company into a qualified lead instantly.")

def run_analysis(url):  # Bug 3 fix: removed @st.cache_data
    data = extract_company_data(url)

    if data is None:
        data = {"home": "", "about": "", "blog": ""}

    profile = generate_company_profile(data)
    audit = generate_content_audit(data)

    company = extract_company_from_url(url)  # Bug 4 fix: use URL-based extractor, url is available here

    company_type = classify_company_type(profile)  
    if "saas" in company_type:
        competitors = get_competitors(profile, company)  # Bug 1 fix: added company argument
    else:
        focus = refine_scope_for_large_company(company)
        competitors = get_competitors(profile + f"\nFocus on: {focus}", company)  # Bug 1 fix

    visibility = generate_scores(profile, audit, "")  # Bug 2 fix: removed non-existent functions

    scores = generate_scores(profile, audit, visibility)

    size = estimate_company_size(profile)
    roles = get_target_role_dynamic(size)

    name, role = find_person_via_ai_search(f"{company} ({url})", roles)
    if not name:
        name, role = fallback_contact(roles)

    email = generate_outreach_email(company, name, role, audit, visibility)

    return {
        "profile": profile,
        "audit": audit,
        "company": company,
        "competitors": competitors,
        "visibility": visibility,
        "scores": scores,
        "size": size,
        "name": name,
        "role": role,
        "email": email,
    }

url = st.text_input("Enter company URL")

if st.button("Run Analysis"):
    if not url:
        st.warning("Please enter a company URL first.")
    else:
        with st.spinner("Running AI analysis..."):
            result = run_analysis(url)

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("🏢 Company Profile")
                st.write(result["profile"])

                st.subheader("📊 Scores")
                st.write(result["scores"])

            with col2:
                st.subheader("🧠 Content Audit")
                st.write(result["audit"])

                st.subheader("👀 AI Visibility")
                st.write(result["visibility"])

            st.subheader("🏁 Competitors")
            st.write(result["competitors"])

            st.subheader("🎯 Target Contact")
            st.write(f"Name: {result['name']}")
            st.write(f"Role: {result['role']}")
            st.write(f"Company Size: {result['size']}")

            st.subheader("📧 Outreach Email")
            st.text_area("Copy & send", result["email"], height=200)

            st.success("Analysis complete ✅")