import streamlit as st
from Backend_pipeline import *

st.set_page_config(page_title="Veloz AI", layout="wide")

st.title("🚀 Prospect Intelligence Engine")
st.markdown("Turn any company into a qualified lead instantly.")

url = st.text_input("Enter company URL")

if st.button("Run Analysis"):
    with st.spinner("Running AI analysis..."):

        data = extract_company_data(url)

        profile = generate_company_profile(data)
        audit = generate_content_audit(data)

        company = extract_company_name(profile)
        

        competitors = get_competitors(profile)
        responses = generate_ai_responses(company, competitors)
        visibility = analyze_visibility(company, competitors, responses)

        scores = generate_scores(profile, audit, visibility)

        # ---------------- CONTACT DETECTION (AGREGADO) ----------------
        size = estimate_company_size(profile)
        roles = get_target_role_dynamic(size)

        candidates = find_people(data, roles)
        name, role = find_people_with_ai(data, roles)
        

        if not name:
            name, role = fallback_contact(roles)
        # -------------------------------------------------------------

        # ⚠️ reemplazamos esta línea para usar name y role
        email = generate_outreach_email(company, name, role, audit, visibility)

        # ---------------- UI ----------------
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("🏢 Company Profile")
            st.write(profile)

            st.subheader("📊 Scores")
            st.write(scores)

        with col2:
            st.subheader("🧠 Content Audit")
            st.write(audit)

            st.subheader("👀 AI Visibility")
            st.write(visibility)

        st.subheader("🏁 Competitors")
        st.write(competitors)

        # 🆕 opcional pero MUY útil para demo
        st.subheader("🎯 Target Contact")
        st.write(f"Name: {name}")
        st.write(f"Role: {role}")
        st.write(f"Company Size: {size}")

        st.subheader("📧 Outreach Email")
        st.text_area("Copy & send", email, height=200)

        st.success("Analysis complete ✅")