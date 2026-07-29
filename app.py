import re
import streamlit as st
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# ----------------------------
# Page Config
# ----------------------------
st.set_page_config(page_title="MIRA Wealth | Accredited Investor Eligibility Check", layout="centered")

LAKH = 100000       # 1 Lakh = ₹1,00,000
CRORE = 10000000    # 1 Crore = ₹1,00,00,000

# ----------------------------
# Premium theme: fonts + CSS
# ----------------------------
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Playfair+Display:wght@600;700&display=swap" rel="stylesheet">
<style>
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* Card-style container for the whole form (covers multiple Streamlit DOM versions) */
    .main .block-container,
    [data-testid="stAppViewContainer"] .block-container,
    [data-testid="stMainBlockContainer"] {
        max-width: 720px !important;
        padding: 3rem 2.5rem 4rem !important;
        background: #12151c;
        border: 1px solid rgba(197, 160, 89, 0.10);
        border-radius: 6px;
        box-shadow: 0 30px 60px rgba(0,0,0,0.45);
        margin: 2rem auto !important;
    }

    /* Section headers (st.subheader) styled as premium section titles */
    h3 {
        font-size: 0.78rem !important;
        color: #9aa2b1 !important;
        text-transform: uppercase;
        letter-spacing: 2.5px;
        font-weight: 600 !important;
        margin: 2.2rem 0 1.2rem !important;
        padding-bottom: 0.6rem;
        border-bottom: 1px solid rgba(197, 160, 89, 0.18);
        text-align: left !important;
    }

    /* Widget labels */
    [data-testid="stWidgetLabel"] p {
        font-size: 0.72rem !important;
        color: #8e95a2 !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 600 !important;
    }

    /* Text / number inputs — visible boxed style (multiple selectors for
       compatibility across Streamlit versions) */
    .stTextInput input,
    .stNumberInput input,
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input,
    [data-testid="stTextInputRootElement"],
    div[data-baseweb="input"],
    div[data-baseweb="base-input"] {
        background: #1a1e27 !important;
        border: 1px solid #3a4150 !important;
        border-radius: 4px !important;
    }
    .stTextInput input,
    .stNumberInput input,
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input {
        color: #ffffff !important;
        font-size: 1.0rem !important;
        padding: 10px 12px !important;
        background: #1a1e27 !important;
    }
    .stTextInput input:focus,
    .stNumberInput input:focus,
    [data-testid="stTextInput"] input:focus,
    [data-testid="stNumberInput"] input:focus {
        border-color: #c5a059 !important;
        box-shadow: 0 0 0 1px #c5a059 !important;
    }

    /* Hide the "Press Enter to apply" instruction hint under inputs */
    [data-testid="InputInstructions"] { display: none !important; }

    /* Divider lines */
    hr { border-color: rgba(197, 160, 89, 0.15) !important; }

    /* Metrics */
    [data-testid="stMetricLabel"] {
        text-transform: uppercase;
        letter-spacing: 1px;
        font-size: 0.7rem !important;
        color: #8e95a2 !important;
    }
    [data-testid="stMetricValue"] {
        color: #c5a059 !important;
        font-family: 'Playfair Display', serif;
    }

    /* Buttons */
    .stButton > button {
        text-transform: uppercase;
        letter-spacing: 3px;
        font-weight: 600;
        border-radius: 2px !important;
        padding: 0.9rem !important;
        border: none !important;
        transition: 0.25s;
    }
    .stButton > button:hover {
        letter-spacing: 3.5px;
    }

    /* Criteria table */
    .criteria-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 0.5rem;
        font-size: 0.88rem;
    }
    .criteria-table th {
        text-align: left;
        color: #8e95a2;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-size: 0.65rem;
        font-weight: 600;
        padding: 10px 12px;
        border-bottom: 1px solid rgba(197, 160, 89, 0.25);
    }
    .criteria-table td {
        padding: 12px;
        border-bottom: 1px solid rgba(197, 160, 89, 0.10);
        color: #ffffff;
        vertical-align: top;
    }
    .criteria-table tr:last-child td { border-bottom: none; }
    .status-met { color: #6fcf97; font-weight: 600; white-space: nowrap; }
    .status-not-met { color: #6b7280; font-weight: 600; white-space: nowrap; }
</style>
""", unsafe_allow_html=True)

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

    expected_headers = [
        "Timestamp", "Name", "Email", "Phone",
        "Annual Income",
        "Stocks / Equity Shares", "Mutual Funds", "RSUs / ESOPs",
        "Bonds / Debentures / NCDs",
        "Fixed Deposits", "PPF / EPF / NPS", "Gold",
        "AIF / PMS Investments", "Other Financial Assets",
        "Total Financial Assets",
        "Primary Residence", "Other Real Estate",
        "Total Non-Financial Assets",
        "Net Worth (excl. Primary Residence, used for eligibility)",
        "Option 1 Met", "Option 2 Met", "Option 3 Met", "Eligible"
    ]

    # Insert header row if it's missing or doesn't match, regardless of
    # whether other data already exists in the sheet
    existing_first_row = worksheet.row_values(1)
    if existing_first_row != expected_headers:
        worksheet.insert_row(expected_headers, index=1)

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
# Helpers: rupee formatting
# ----------------------------
def format_inr(amount):
    """Used for displaying summary totals in Cr / L (unrelated to input formatting)."""
    if amount >= CRORE:
        return f"₹{amount / CRORE:.2f} Cr"
    elif amount >= LAKH:
        return f"₹{amount / LAKH:.2f} L"
    else:
        return f"₹{amount:,.0f}"


def indian_comma_format(digits: str) -> str:
    """Formats a plain digit string into Indian comma grouping, e.g. 1234567 -> 12,34,567"""
    if not digits:
        return ""
    n = str(int(digits))  # strips leading zeros
    if len(n) <= 3:
        return n
    last3 = n[-3:]
    rest = n[:-3]
    parts = []
    while len(rest) > 2:
        parts.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        parts.insert(0, rest)
    return ",".join(parts) + "," + last3


def currency_input(label, key):
    """
    Renders a text input for entering a full rupee amount, with Indian-style
    comma grouping applied automatically as the person types.
    Returns the entered amount as an integer (in plain rupees).
    """
    def _reformat():
        raw = st.session_state.get(key, "")
        digits = re.sub(r"[^0-9]", "", raw)
        st.session_state[key] = indian_comma_format(digits) if digits else ""

    st.text_input(label, key=key, on_change=_reformat)

    raw_value = st.session_state.get(key, "")
    digits = re.sub(r"[^0-9]", "", raw_value)
    return int(digits) if digits else 0


# One-time JS injection: formats currency inputs with commas live, as the
# person types, instead of waiting for blur/Enter. This is a client-side
# visual enhancement only — the Python-side reformatting above (on blur)
# remains as the source of truth, so calculations stay correct even if
# this script doesn't run in some environment.
import streamlit.components.v1 as components
components.html("""
<script>
(function() {
    function formatIndian(digits) {
        if (!digits) return "";
        let n = String(parseInt(digits, 10));
        if (n.length <= 3) return n;
        let last3 = n.slice(-3);
        let rest = n.slice(0, -3);
        let parts = [];
        while (rest.length > 2) {
            parts.unshift(rest.slice(-2));
            rest = rest.slice(0, -2);
        }
        if (rest) parts.unshift(rest);
        return parts.join(",") + "," + last3;
    }

    function attach() {
        const doc = window.parent.document;
        const inputs = doc.querySelectorAll('input[aria-label*="₹"]');
        inputs.forEach(function(input) {
            if (input.dataset.liveFormatAttached) return;
            input.dataset.liveFormatAttached = "true";
            input.addEventListener('input', function() {
                const digits = input.value.replace(/[^0-9]/g, '');
                const formatted = formatIndian(digits);
                if (formatted !== input.value) {
                    const setter = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value'
                    ).set;
                    setter.call(input, formatted);
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                }
            });
        });
    }

    setInterval(attach, 400);
})();
</script>
""", height=0)


# ----------------------------
# Header
# ----------------------------
st.markdown("""
<div style="text-align:left; margin-bottom: 6px;">
    <h1 style="font-family:'Playfair Display', serif; font-weight:600; font-size:1.9rem; margin:0 0 4px; letter-spacing:-0.3px; color:#c5a059; line-height:1.25;">
        MIRA Wealth
    </h1>
    <h1 style="font-family:'Playfair Display', serif; font-weight:600; font-size:1.9rem; margin:0; letter-spacing:-0.3px; color:#ffffff; line-height:1.25;">
        Accredited Investor Eligibility Checker
    </h1>
</div>
""", unsafe_allow_html=True)

st.caption("Check whether you qualify as an Accredited Investor under SEBI's framework")

st.markdown("---")

# ----------------------------
# Personal Information
# ----------------------------
st.subheader("Personal Information")

col1, col2 = st.columns(2)
with col1:
    name = st.text_input("Full Name *")
    email = st.text_input("Email Address (optional)")
with col2:
    phone = st.text_input("Phone Number * (10 digits)", placeholder="10-digit mobile number", max_chars=10)

st.caption("* Required fields")

st.markdown("---")

# ----------------------------
# Annual Income
# ----------------------------
st.subheader("Annual Income")
annual_income = currency_input("Annual Income (As per Latest ITR)", "annual_income")

st.markdown("---")

# ----------------------------
# Financial Assets
# ----------------------------
st.subheader("Financial Assets")
st.caption("Liquid/investible assets — excludes your real estate investments")

fa_col1, fa_col2 = st.columns(2)

with fa_col1:
    stocks = currency_input("Stocks / Equity Shares (₹)", "stocks")
    mutual_funds = currency_input("Mutual Funds (₹)", "mutual_funds")
    rsu_esop = currency_input("RSUs / ESOPs — vested, current value (₹)", "rsu_esop")
    bonds = currency_input("Bonds / Debentures / NCDs (₹)", "bonds")

with fa_col2:
    fixed_deposits = currency_input("Fixed Deposits (₹)", "fixed_deposits")
    ppf_epf_nps = currency_input("PPF / EPF / NPS (₹)", "ppf_epf_nps")
    gold = currency_input("Gold — ETF / SGB / Physical, investment grade (₹)", "gold")
    aif_pms = currency_input("AIF / PMS Investments (₹)", "aif_pms")
    other_financial = currency_input("Other Financial Assets (₹)", "other_financial")

total_financial_assets = (
    stocks + mutual_funds + rsu_esop + bonds +
    fixed_deposits + ppf_epf_nps + gold + aif_pms + other_financial
)

st.markdown("---")

# ----------------------------
# Non-Financial Assets
# ----------------------------
st.subheader("Non-Financial Assets")

nfa_col1, nfa_col2 = st.columns(2)

with nfa_col1:
    primary_residence = currency_input("Primary Residence — market value (₹)", "primary_residence")

with nfa_col2:
    other_real_estate = currency_input("Other Real Estate (₹)", "other_real_estate")

total_non_financial_assets = primary_residence + other_real_estate

st.markdown("---")

# ----------------------------
# Calculations
# ----------------------------
total_assets = total_financial_assets + total_non_financial_assets

# Primary residence is captured for records but excluded from net worth
# used in the eligibility assessment, per SEBI's definition
net_worth = total_assets - primary_residence

# ----------------------------
# Eligibility Logic
# ----------------------------
def check_accredited_investor(net_worth, total_financial_assets, annual_income):
    option1 = net_worth >= 7.5 * CRORE and total_financial_assets >= 3.75 * CRORE
    option2 = annual_income >= 2 * CRORE
    option3 = (
        net_worth >= 5 * CRORE and
        annual_income >= 1 * CRORE and
        total_financial_assets >= 2.5 * CRORE
    )
    return option1, option2, option3

# ----------------------------
# Analyze Button
# ----------------------------
st.markdown("## ")
analyze = st.button("Analyze Eligibility", type="primary", use_container_width=True)

if analyze:
    if not name.strip() or not phone.strip():
        st.error("Please enter your **Name** and **Phone Number** before analyzing.")
        st.stop()

    if not phone.strip().isdigit() or len(phone.strip()) != 10:
        st.error("Please enter a valid **10-digit** phone number (numbers only).")
        st.stop()

    st.markdown("---")

    st.markdown(
        "<p style='text-align:left; color:#c5a059; font-weight:600; letter-spacing:1.5px; "
        "text-transform:uppercase; font-size:0.8rem; margin-bottom:1.5rem;'>✓ Analysis Complete — Results Below</p>",
        unsafe_allow_html=True
    )

    st.subheader("Summary")

    s1, s2, s3 = st.columns(3)
    s1.metric("Net Worth (excl. primary residence)", format_inr(net_worth))
    s2.metric("Financial Assets", format_inr(total_financial_assets))
    s3.metric("Annual Income", format_inr(annual_income))

    option1, option2, option3 = check_accredited_investor(
        net_worth, total_financial_assets, annual_income
    )

    is_eligible = option1 or option2 or option3

    st.markdown("---")

    st.subheader("Eligibility Criteria")

    def status_html(met):
        return '<span class="status-met">✓ Met</span>' if met else '<span class="status-not-met">Not met</span>'

    criteria_table = f"""
    <table class="criteria-table">
        <tr>
            <th style="width:16%;">Option</th>
            <th style="width:64%;">Requirement</th>
            <th style="width:20%;">Status</th>
        </tr>
        <tr>
            <td>Option 1</td>
            <td>Net worth (excl. primary residence) ≥ ₹7.5 Cr, with ≥ ₹3.75 Cr in financial assets</td>
            <td>{status_html(option1)}</td>
        </tr>
        <tr>
            <td>Option 2</td>
            <td>Annual income ≥ ₹2 Cr</td>
            <td>{status_html(option2)}</td>
        </tr>
        <tr>
            <td>Option 3</td>
            <td>Net worth (excl. primary residence) ≥ ₹5 Cr + annual income ≥ ₹1 Cr, with ≥ ₹2.5 Cr in financial assets</td>
            <td>{status_html(option3)}</td>
        </tr>
    </table>
    """
    st.markdown(criteria_table, unsafe_allow_html=True)

    # Save the lead to Google Sheets
    save_lead([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        name, email, phone,
        annual_income,
        stocks, mutual_funds, rsu_esop, bonds,
        fixed_deposits, ppf_epf_nps, gold, aif_pms, other_financial,
        total_financial_assets,
        primary_residence, other_real_estate,
        total_non_financial_assets,
        net_worth,
        option1, option2, option3, is_eligible
    ])

    if is_eligible:
        st.success(f"Congratulations {name if name else ''}! You qualify as an **Accredited Investor**.")
        st.markdown(
            """
            <a href="https://wa.me/916364942933?text=Hi%2C%20I%20checked%20my%20Accredited%20Investor%20eligibility%20and%20would%20like%20to%20know%20more."
            target="_blank" style="text-decoration:none;">
                <button style="
                    background-color:transparent;
                    color:#c5a059;
                    padding:16px 24px;
                    border:1px solid #c5a059;
                    border-radius:2px;
                    font-size:0.8rem;
                    text-transform:uppercase;
                    letter-spacing:2px;
                    font-weight:600;
                    cursor:pointer;
                    width:100%;
                    transition:0.25s;">
                    Chat with us on WhatsApp
                </button>
            </a>
            """,
            unsafe_allow_html=True
        )
    else:
        st.error("Based on the information provided, you do not currently meet any of the Accredited Investor criteria.")
        st.info("Note: This is an indicative self-assessment, not a formal certification. Actual accreditation requires documentary verification as per SEBI norms.")
