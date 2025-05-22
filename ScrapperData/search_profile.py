# File: Scrapr_Data/search_profiles.py

import pickle
import os
import time
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import asyncio
import pandas as pd
from playwright.async_api import async_playwright
import random
load_dotenv()

COOKIE_PATH = "linkedin_cookies.pkl"
USERNAME = os.getenv("username")
PASSWORD = os.getenv("password")

# --------- Save cookies with Selenium ----------
def selenium_login():
    options = Options()
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)

    driver.get("https://www.linkedin.com/login")
    time.sleep(2)

    driver.find_element(By.ID, "username").send_keys(USERNAME)
    driver.find_element(By.ID, "password").send_keys(PASSWORD)
    driver.find_element(By.XPATH, '//button[@type="submit"]').click()

    time.sleep(5)  # Wait for login

    # Save cookies
    with open(COOKIE_PATH, "wb") as f:
        pickle.dump(driver.get_cookies(), f)

    print("[✓] Cookies saved successfully")
    return driver

# --------- Load cookies ----------
def load_cookies():
    if os.path.exists(COOKIE_PATH):
        with open(COOKIE_PATH, "rb") as f:
            return pickle.load(f)
    return None


# Extract experience section
async def extract_experience_info(page):
    experience_data = []
    try:
        await page.wait_for_selector('[data-field="experience_company_logo"]', timeout=10000)
        job_blocks = await page.query_selector_all('[data-field="experience_company_logo"]')

        for block in job_blocks:
            try:
                href = await block.get_attribute('href')

                # Job title
                title_el = await block.query_selector('.t-bold')
                title = await title_el.inner_text() if title_el else None

                # Fix duplicated job titles like "Python Developer Python Developer"
                if title:
                    words = title.strip().split()
                    half = len(words) // 2
                    if words[:half] == words[half:]:
                        title = ' '.join(words[:half])

                # Company, Duration, Location
                spans = await block.query_selector_all('span.t-14.t-normal')
                company_type_raw = await spans[0].inner_text() if len(spans) > 0 else ""
                duration_raw = await spans[1].inner_text() if len(spans) > 1 else ""
                location_raw = await spans[2].inner_text() if len(spans) > 2 else ""

                # Clean company (split by dot if exists)
                company_parts = company_type_raw.replace('\n', ' ').split('·')
                company = company_parts[0].strip() if company_parts else company_type_raw.strip()

                # Clean duration & location (remove duplicate words)
                duration_clean = duration_raw.replace('\n', ' ').split('·')[0].strip()
                duration = ' '.join(dict.fromkeys(duration_clean.split()))

                location = ' '.join(dict.fromkeys(location_raw.replace('\n', ' ').split()))

                if not title or not company:
                    continue

                experience_data.append({
                    "position": title.strip(),
                    "company": company,
                    "duration": duration,
                    "location": location,
                    "company_url": href or ""
                })
            except Exception as e:
                print("Failed to parse one job block:", e)
                continue
    except Exception as e:
        print("Error during experience extraction:", e)

    return experience_data

# Extract education section
async def extract_education_info(page):
    education_data = []
    try:
        await page.wait_for_selector('#education', timeout=10000,state="attached")

        anchor = await page.query_selector('#education')
        section = await anchor.evaluate_handle('node => node.closest("section")')

        if not section:
            next_sibling = await anchor.evaluate_handle('node => { let n = node.nextElementSibling; while(n && n.tagName !== "SECTION") n = n.nextElementSibling; return n; }')
            section = next_sibling

        if not section:
            return []

        blocks = await section.query_selector_all('li')

        for block in blocks:
            try:
                school_el = await block.query_selector('span[aria-hidden="true"]')
                school = await school_el.inner_text() if school_el else ""

                degree_el = await block.query_selector('.t-14.t-normal')
                degree = await degree_el.inner_text() if degree_el else ""

                if degree:
                    words = degree.strip().split()
                    half = len(words) // 2
                    if words[:half] == words[half:]:
                        degree = ' '.join(words[:half])


                dates_el = await block.query_selector('.t-black--light')
                dates_raw = await dates_el.inner_text() if dates_el else ""
                duration = ' '.join(dict.fromkeys(dates_raw.replace('\n', ' ').split()))

                if not school or not degree:
                    continue

                education_data.append({
                    "university": school.strip(),
                    "degree": degree.strip(),
                    "duration": duration,
                })
            except Exception as e:
                print("Error parsing one education block:", e)
                continue

    except Exception as e:
        print("Error during education extraction:", e)

    return education_data

# --------- Use Playwright to scrape profiles ----------
async def scrape_with_playwright(cookies, url, filename , retry=False):

    data = []
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()

            # Set cookies
            await context.add_cookies([
                {
                    "name": cookie["name"],
                    "value": cookie["value"],
                    "domain": ".linkedin.com",
                    "path": "/",
                    "secure": cookie.get("secure", False),
                    "httpOnly": cookie.get("httpOnly", False),
                    "sameSite": "Lax"
                }
                for cookie in cookies
            ])

            page = await context.new_page()
            await page.goto(url, timeout=60000)
            await page.wait_for_timeout(5000)

            # 🔐 Check if login expired
            if "login" in page.url or "signin" in page.url.lower():
                print("🔒 Redirected to login page. Login expired.")
                if not retry:
                    # Use Selenium to re-login and save cookies
                    driver = selenium_login()
                    driver.quit()
                    cookies = load_cookies()
                    await browser.close()
                    return await scrape_with_playwright(cookies, url, filename, retry=True)
                else:
                    print("❌ Retry already attempted. Aborting.")
                    return "Login failed after retry."
            

            for _ in range(1):  # Scrape 1 pages (adjust as needed)
                await page.wait_for_timeout(3000)

                profiles = await page.query_selector_all("div.linked-area")


                for profile in profiles:
                    try:
                        # Profile URL
                        anchor_el = await profile.query_selector('a[href*="linkedin.com/in/"]')
                        href = await anchor_el.get_attribute("href") if anchor_el else None

                        # Name
                        name_el = await profile.query_selector("span[aria-hidden='true']")
                        name = await name_el.inner_text() if name_el else None

                        # Find the closest container element for the profile
                        container = await profile.evaluate_handle('node => node.closest("div")')

                        # Image URL
                        img_el = await container.query_selector("img")
                        image_url = await img_el.get_attribute("src") if img_el else None


                        alt_text = await img_el.get_attribute("alt") if img_el else ""
                        open_to_work = "Yes" if "is open to work" in alt_text.lower() else "No"

                        # Description (e.g., job title or about)
                        desc_el = await container.query_selector("div.t-14.t-black.t-normal")
                        description = await desc_el.inner_text() if desc_el else None

                        # Location
                        loc_els = await container.query_selector_all("div.t-14.t-normal")
                        location = await loc_els[1].inner_text() if len(loc_els) > 1 else None


                        # Skills (optional if available in result summary)
                        skills_el = await container.query_selector("p.entity-result__summary--2-lines")
                        skills = await skills_el.inner_text() if skills_el else None
                        if skills:
                            skills = skills.replace("Skills:", "").strip()

                        # Visit profile page to fetch education and experience
                        experience = []
                        try:
                            profile_page = await context.new_page()
                            await profile_page.goto(href, timeout=90000)
                            await profile_page.wait_for_load_state("domcontentloaded")

                            # Scroll until experience section is loaded
                            for _ in range(3):
                                await profile_page.evaluate('window.scrollBy(0, window.innerHeight)')
                                await profile_page.wait_for_timeout(4000)
                                if await profile_page.query_selector('section[id*="experience"] li'):
                                    break

                            experience = await extract_experience_info(profile_page)
                            education = await extract_education_info(profile_page)
                            await profile_page.close()
                        except Exception as e:
                            print(f"Error extracting experience for {href}:", e)
                            try:
                                await profile_page.close()
                            except:
                                pass
                        data.append({
                            "Name": name,
                            "Profile URL": href,
                            "Image URL": image_url,
                            "Opentowork":open_to_work,
                            "Location": location,
                            "Description": description,
                            "Skills": skills,
                            "Education": education,
                            "Experience": experience,
                        })


                    except Exception as e:
                        print("Error extracting name:", e)
                        continue


                    # try:
                    #     # Step 1: Click the "Connect" button inside the profile
                    #     connect_btn = await profile.query_selector("button:has-text('Connect')")
                    #     if connect_btn:
                    #         await page.wait_for_timeout(3000)
                    #         await connect_btn.click()
                    #         await page.wait_for_timeout(5000)
                    #         # Short wait for dialog to appear

                    #         # Step 2: Click the "Add a note" button in the dialog
                    #         add_note_btn = await page.query_selector("button:has-text('Add a note')")
                    #         if add_note_btn:
                    #             await add_note_btn.click()

                    #             # Wait 8–10 seconds before filling the message
                    #             await page.wait_for_timeout(random.randint(8000, 10000))

                    #             # Step 3: Fill the note message
                    #             note_text = "Hi, I came across your profile and it looks great. Are you open to connect and explore potential opportunities?"
                    #             await page.fill("textarea[name='message']", note_text)

                    #             # Wait 5 seconds before sending
                    #             await page.wait_for_timeout(6000)

                    #             # Step 4: Click the "Send" button
                    #             send_btn = await page.query_selector("button:has-text('Send')")
                    #             if send_btn:
                    #                 await send_btn.click()

                    #                 # Wait 5–7 seconds before continuing to the next profile
                    #                 await page.wait_for_timeout(random.randint(5000, 7000))

                    #                 # ✅ Print success message
                    #                 print(f"✅ Connection request sent successfully to {name}")

                    #             else:
                    #                 print(f"❌ Send button not found for {name}")

                    # except Exception as e:
                    #     print(f"⚠️ Error sending connection request for {name} - {href}: {e}")
                    #     # Optional: Close the dialog if something breaks
                    #     try:
                    #         dismiss_btn = await page.query_selector("button[aria-label='Dismiss']")
                    #         if dismiss_btn:
                    #             await dismiss_btn.click()
                    #     except:
                    #         pass

                                        
                    # Next page
                next_btn = await page.query_selector('button[aria-label="Next"]')
                if next_btn:
                    await next_btn.click()
                    await page.wait_for_timeout(3000)  # wait for page to load
                else:
                    break
            # Clean and flatten experience and education
            cleaned_data = []
            for profile in data:
                base = {
                    "Name": profile.get("Name", ""),
                    "Profile URL": profile.get("Profile URL", ""),
                    "Image URL": profile.get("Image URL", ""),
                    "Location": profile.get("Location", ""),
                    "Description": profile.get("Description", ""),
                    "Skills": profile.get("Skills", ""),
                    "Open to Work": profile.get("Opentowork", "")
                }

                # Flatten top 3 experiences
                experiences = profile.get("Experience", [])[:3]
                for i, exp in enumerate(experiences, start=1):
                    base[f"Job {i} Title"] = exp.get("position", "").replace("\n", " ").strip()
                    base[f"Job {i} Company"] = exp.get("company", "").replace("\n", " ").strip()
                    base[f"Job {i} Duration"] = exp.get("duration", "").replace("\n", " ").strip()
                    base[f"Job {i} Location"] = exp.get("location", "").replace("\n", " ").strip()

                # Flatten top 3 education entries
                educations = profile.get("Education", [])[:2]
                for i, edu in enumerate(educations, start=1):
                    base[f"Edu {i} University"] = edu.get("university", "").replace("\n", " ").strip()
                    base[f"Edu {i} Degree"] = edu.get("degree", "").replace("\n", " ").strip()
                    base[f"Edu {i} Duration"] = edu.get("duration", "").replace("\n", " ").strip()

                cleaned_data.append(base)

            df = pd.DataFrame(cleaned_data)
            df.to_excel(filename, index=False)
            print(f"[✓] Saved {len(df)} cleaned and flattened profiles to {filename}")
            await browser.close()
        except Exception as e:
            print(f"An error occurred: {e}")
            return f"An error occurred: Error {e}"
        finally:
            #await browser.close()
            return "Done"

async def send_connection_request(cookies,profile_url: str, message: str,retry=False):

    page=None
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            print('after context')
            # Set cookies
            await context.add_cookies([
                {
                    "name": cookie["name"],
                    "value": cookie["value"],
                    "domain": ".linkedin.com",
                    "path": "/",
                    "secure": cookie.get("secure", False),
                    "httpOnly": cookie.get("httpOnly", False),
                    "sameSite": "Lax"
                }
                for cookie in cookies
            ])
            print('before page')
            page = await context.new_page()
           
            await page.goto(profile_url, timeout=60000)
            await page.wait_for_timeout(5000)

            # 🔐 Check if login expired
            if "login" in page.url or "signin" in page.url.lower():
                print("🔒 Redirected to login page. Login expired.")
                if not retry:
                    # Use Selenium to re-login and save cookies
                    driver = selenium_login()
                    driver.quit()
                    cookies = load_cookies()
                    await browser.close()
                    return await send_connection_request(cookies, url, filename, retry=True)
                else:
                    print("❌ Retry already attempted. Aborting.")
                    return "Login failed after retry."
            




            # page = await context.new_page()
            # await page.goto(profile_url, timeout=90000)
            # Scroll to bottom to reveal buttons
                
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)

            # Try finding the connect button directly
            connect_btn = await page.query_selector("button:has-text('Connect')")

            # If not found, try clicking the 'More' button to expand dropdown
            if not connect_btn:
                print("🔍 'Connect' button not visible, trying dropdown...")
                more_btn = await page.query_selector("button:has-text('More')")
                if more_btn:
                    await more_btn.click()
                    await page.wait_for_timeout(1000)
                    connect_btn = await page.query_selector("div[role='menu'] button:has-text('Connect')")

            if not connect_btn:
                print( f"❌ 'Connect' button not found even in dropdown for {profile_url}")

            # Try to click it if visible
            if await connect_btn.is_visible():
                await connect_btn.click()
                await page.wait_for_timeout(5000)
            else:
                print( f"❌ 'Connect' button found but not visible or clickable on {profile_url}")


            # Click the "Add a note" button
            add_note_btn = await page.query_selector("button:has-text('Add a note')")
            if not add_note_btn:
                print( f"❌ 'Add a note' button not found for {profile_url}")
            
            await add_note_btn.click()
            await page.wait_for_timeout(8000)

            # Fill the message textarea
            await page.fill("textarea[name='message']", message)
            await page.wait_for_timeout(9000)

            # Click the "Send" button
            send_btn = await page.query_selector("button:has-text('Send')")
            if send_btn:
                await send_btn.click()
                await page.wait_for_timeout(2000)
                print( f"✅ Connection request sent to {profile_url}")
            else:
                print( f"❌ Send button not found for {profile_url}")

        except Exception as e:
            print(f" Exception: {e}")
            return f" Error sending request to {profile_url}: {e}"

        finally:
            try:
                await page.close()
            except:
                pass

if __name__ == "__main__":
   
    cookies = load_cookies()
    if cookies is None:
            print("No valid cookies found, logging in...")
            driver = selenium_login()
            driver.quit()
            cookies =load_cookies()
            print("✅ Cookies saved successfully!")
    else:
            print("✅ Using stored cookies for scraping.")

    url = "https://www.linkedin.com/search/results/people/?keywords=aiml"
    filename = "linkedin_profiles.xlsx"

    asyncio.run(send_connection_request(cookies,"https://www.linkedin.com/in/het-thakkar-392526257/","Hii !!"))
    