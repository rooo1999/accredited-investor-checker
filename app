import streamlit as st
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# ----------------------------
# Page Config
# ----------------------------
st.set_page_config(page_title="Accredited Investor Eligibility Check", layout="centered")

LAKH = 100000  # 1 Lakh = ₹1,00,000
CRORE = 10000000  # 1 Crore = ₹1,00,00,000

# ----------------------------
# Google Sheets connection
# ----------------------------
@st.cache_resource
def get_worksheet():
    """
    Connects to Google Sheets using a service account.
    Requires st.secrets["gcp_service_account"] and st.secrets["sheet_url"]
    to be set (see setup instructions).
    """
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scopes
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_url(st.secrets["sheet_url"])
    worksheet = sheet.sheet1

    # Add header row if the sheet is empty
    if not worksheet.get_all_values():
        worksheet.append_row([
            "Timestamp", "Name", "Email", "Phone", "PAN",
            "Annual Income", "Total Financial Assets", "Total Non-Financial Assets",
            "Total Liabilities", "Net Worth",
            "Option 1 Met", "Option 2 Met", "Option 3 Met", "Eligible"
        ])
    return worksheet


def save_lead(row_data):
    """Appends a row to the Google Sheet. Fails silently (with a warning) if not configured."""
    try:
        worksheet = get_worksheet()
        worksheet.append_row(row_data)
        return True
    except Exception as e:
        st.warning(f"Could not save your submission to our records (form still worked fine). Error: {e}")
        return False


# ----------------------------
# Helper: format rupees nicely
# ----------------------------
def format_inr(amount):
    if amount >= CRORE:
        return f"₹{amount / CRORE:.2f} Cr"
    elif amount >= LAKH:
        return f"₹{amount / LAKH:.2f} L"
    else:
        return f"₹{amount:,.0f}"

# ----------------------------
# Header
# ----------------------------
st.title("🏦 Accredited Investor Eligibility Checker")
st.caption("Check whether you qualify as an Accredited Investor under SEBI's framework")

st.markdown("---")

# ----------------------------
# Personal Information
# ----------------------------
st.subheader("👤 Personal Information")

col1, col2 = st.columns(2)
with col1:
    name = st.text_input("Full Name")
    email = st.text_input("Email Address")
with col2:
    phone = st.text_input("Phone Number (with country code)", placeholder="+91 XXXXXXXXXX")
    pan = st.text_input("PAN (optional)")

st.markdown("---")

# ----------------------------
# Annual Income
# ----------------------------
st.subheader("💰 Annual Income")
annual_income_lakh = st.number_input(
    "Annual Income (₹ in Lakhs)",
    min_value=0.0, step=1.0, format="%.2f"
)
annual_income = annual_income_lakh * LAKH

st.markdown("---")

# ----------------------------
# Financial Assets
# ----------------------------
st.subheader("📈 Financial Assets")
st.caption("Liquid/investible assets — excludes your primary residence")

fa_col1, fa_col2 = st.columns(2)

with fa_col1:
    stocks = st.number_input("Stocks / Equity Shares (₹ Lakhs)", min_value=0.0, step=1.0)
    mutual_funds = st.number_input("Mutual Funds (₹ Lakhs)", min_value=0.0, step=1.0)
    rsu_esop = st.number_input("RSUs / ESOPs (vested, current value) (₹ Lakhs)", min_value=0.0, step=1.0)
    bonds = st.number_input("Bonds / Debentures / NCDs (₹ Lakhs)", min_value=0.0, step=1.0)
    unlisted_shares = st.number_input("Unlisted / Pre-IPO Shares (₹ Lakhs)", min_value=0.0, step=1.0)

with fa_col2:
    fixed_deposits = st.number_input("Fixed Deposits (₹ Lakhs)", min_value=0.0, step=1.0)
    ppf_epf_nps = st.number_input("PPF / EPF / NPS (₹ Lakhs)", min_value=0.0, step=1.0)
    gold = st.number_input("Gold (ETF / SGB / Physical - investment grade) (₹ Lakhs)", min_value=0.0, step=1.0)
    aif_pms = st.number_input("AIF / PMS Investments (₹ Lakhs)", min_value=0.0, step=1.0)
    other_financial = st.number_input("Other Financial Assets (₹ Lakhs)", min_value=0.0, step=1.0)

total_financial_assets = (
    stocks + mutual_funds + rsu_esop + bonds + unlisted_shares +
    fixed_deposits + ppf_epf_nps + gold + aif_pms + other_financial
) * LAKH

st.markdown("---")

# ----------------------------
# Non-Financial Assets
# ----------------------------
st.subheader("🏠 Non-Financial Assets")

nfa_col1, nfa_col2 = st.columns(2)

with nfa_col1:
    primary_residence = st.number_input("Primary Residence (market value) (₹ Lakhs)", min_value=0.0, step=1.0)
    other_real_estate = st.number_input("Other Real Estate (₹ Lakhs)", min_value=0.0, step=1.0)

with nfa_col2:
    vehicles = st.number_input("Vehicles (₹ Lakhs)", min_value=0.0, step=1.0)
    other_non_financial = st.number_input("Other Non-Financial Assets (₹ Lakhs)", min_value=0.0, step=1.0)

total_non_financial_assets = (
    primary_residence + other_real_estate + vehicles + other_non_financial
) * LAKH

st.markdown("---")

# ----------------------------
# Liabilities
# ----------------------------
st.subheader("📉 Liabilities")
liabilities_lakh = st.number_input(
    "Total Outstanding Loans / Liabilities (₹ Lakhs)",
    min_value=0.0, step=1.0
)
total_liabilities = liabilities_lakh * LAKH

st.markdown("---")

# ----------------------------
# Calculations
# ----------------------------
total_assets = total_financial_assets + total_non_financial_assets
net_worth = total_assets - total_liabilities

# ----------------------------
# Eligibility Logic
# ----------------------------
def check_accredited_investor(net_worth, total_financial_assets, annual_income):
    option1 = net_worth > 7.5 * CRORE and total_financial_assets >= 3.75 * CRORE
    option2 = annual_income > 2 * CRORE
    option3 = (
        net_worth > 5 * CRORE and
        annual_income > 1 * CRORE and
        total_financial_assets >= 2.5 * CRORE
    )
    return option1, option2, option3

# ----------------------------
# Analyze Button
# ----------------------------
st.markdown("## ")
analyze = st.button("🔍 Analyze Eligibility", type="primary", use_container_width=True)

if analyze:
    st.markdown("---")
    st.subheader("📊 Summary")

    s1, s2, s3 = st.columns(3)
    s1.metric("Net Worth", format_inr(net_worth))
    s2.metric("Financial Assets", format_inr(total_financial_assets))
    s3.metric("Annual Income", format_inr(annual_income))

    option1, option2, option3 = check_accredited_investor(
        net_worth, total_financial_assets, annual_income
    )

    is_eligible = option1 or option2 or option3

    st.markdown("---")

    with st.expander("See which criteria you meet"):
        st.write(f"**Option 1** (Net worth > ₹7.5 Cr, with ≥ ₹3.75 Cr in financial assets): "
                 f"{'✅ Met' if option1 else '❌ Not met'}")
        st.write(f"**Option 2** (Annual income > ₹2 Cr): "
                 f"{'✅ Met' if option2 else '❌ Not met'}")
        st.write(f"**Option 3** (Net worth > ₹5 Cr + income > ₹1 Cr, with ≥ ₹2.5 Cr in financial assets): "
                 f"{'✅ Met' if option3 else '❌ Not met'}")

    # Save the lead to Google Sheets
    save_lead([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        name, email, phone, pan,
        annual_income, total_financial_assets, total_non_financial_assets,
        total_liabilities, net_worth,
        option1, option2, option3, is_eligible
    ])

    if is_eligible:
        st.success(f"🎉 Congratulations {name if name else ''}! You may qualify as an **Accredited Investor**.")
        st.markdown(
            """
            <a href="https://wa.me/91XXXXXXXXXX?text=Hi%2C%20I%20checked%20my%20Accredited%20Investor%20eligibility%20and%20would%20like%20to%20know%20more."
            target="_blank">
                <button style="
                    background-color:#25D366;
                    color:white;
                    padding:12px 24px;
                    border:none;
                    border-radius:8px;
                    font-size:16px;
                    cursor:pointer;
                    width:100%;">
                    💬 Chat with us on WhatsApp
                </button>
            </a>
            """,
            unsafe_allow_html=True
        )
    else:
        st.error("Based on the information provided, you do not currently meet any of the Accredited Investor criteria.")
        st.info("Note: This is an indicative self-assessment, not a formal certification. Actual accreditation requires documentary verification as per SEBI norms.")
