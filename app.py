import os
import pickle
from datetime import datetime
import streamlit as st
from urllib.parse import quote_plus
import asyncio
import pandas as pd
from ScrapperData import search_profile  # Ensure your module is named correctly
form_link="qwertyuio"
st.set_page_config(page_title="LinkedIn People Scraper", layout="centered")
st.title("🔍 LinkedIn People Scraper")

# --- INPUTS ---
technology = st.text_input("Enter Technology", "python")
location = st.selectbox("Select Location", ["Ahmedabad", "Bangalore", "Remote"])

# --- URL Generation ---
def generate_people_url(tech, loc):
    query = f"{tech} {loc}".lower()
    encoded_query = quote_plus(query)
    return f"https://www.linkedin.com/search/results/people/?keywords={encoded_query}&origin=FACETED_SEARCH"

linkedin_url = generate_people_url(technology, location)
st.markdown("#### Generated LinkedIn URL:")
st.write(linkedin_url)

# --- SESSION STATE SETUP ---
if "cookies" not in st.session_state:
    st.session_state.cookies = None

if "df" not in st.session_state:
    st.session_state.df = None

if "filename" not in st.session_state:
    st.session_state.filename = None

# --- SCRAPING FUNCTION ---
def extract_people_data(url, filename):
    with st.spinner("Scraping LinkedIn... Please wait."):
        cookies = search_profile.load_cookies()

        if cookies is None:
            st.warning("🔐 Logging in with Selenium...")
            driver = search_profile.selenium_login()
            driver.quit()
            cookies = search_profile.load_cookies()
            st.success("✅ Cookies saved.")
        else:
            st.success("✅ Using stored cookies.")
        # Save cookies in session
        st.session_state.cookies = cookies

        # Ensure folder exists
        os.makedirs("scraped_files", exist_ok=True)
        file_path = os.path.join("scraped_files", filename)

        # Scrape and save Excel file
        asyncio.run(search_profile.scrape_with_playwright(cookies, url, file_path))
        st.success(f"🎉 Scraping completed and file saved: `{filename}`")

        # Load data into DataFrame
        try:
            df = pd.read_excel(file_path)
            st.session_state.df = df
            st.session_state.filename = filename
        except Exception as e:
            st.error(f"❌ Failed to read Excel file: {e}")

# --- START SCRAPING ---
if st.button("🚀 Start Extracting Data"):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"linkedin_people_{timestamp}.xlsx"
    extract_people_data(linkedin_url, filename)

# --- SHOW RESULTS ---
if st.session_state.df is not None:
    st.info(f"📄 Showing extracted data from `{st.session_state.filename}`")

    for index, row in st.session_state.df.iterrows():
        with st.container():
            cols = st.columns([3, 2, 2])
            with cols[0]:
                st.markdown(f"### {row['Name']}")
                st.markdown(f"[🔗 LinkedIn Profile]({row['Profile URL']})")
                st.markdown(f"📍 {row['Location']}")
                st.markdown(f"💼 {row['Description']}")
                st.markdown(f"🧠 Skills: {row['Skills']}")
                st.markdown(f"🟢 Open to Work: {row['Open to Work']}")

            with cols[1]:
                image_url = row.get("Image URL")
                if image_url and image_url.startswith("http"):
                    try:
                        st.image(image_url, width=100)
                    except Exception as e:
                        st.warning("Could not load image.")
                else:
                    st.warning("❌ No valid image URL.")

            with cols[2]:
                if st.button(f"💬 Send Message to {row['Name']}", key=f"btn_{index}"):
                    message = f"""Hi {row['Name']}, hope you're doing well!
                    We're hiring a {technology} Developer in Ahmedabad. If you're interested, please fill out this form 👉 {form_link}. Our team will reach out soon!
                    Looking forward to connecting!"""
                    asyncio.run(search_profile.send_connection_request(
                        st.session_state.cookies,
                        row['Profile URL'],
                        message
                    ))


                    st.success(f"✅ Connection request sent to {row['Name']}")

    # --- Download Button ---
    file_path = os.path.join("scraped_files", st.session_state.filename)
    if os.path.exists(file_path):
        with open(file_path, "rb") as file:
            st.download_button(
                label="📥 Download Excel File",
                data=file,
                file_name=st.session_state.filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.error("❌ File not found. Scraping may have failed.")
