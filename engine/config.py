"""LeapLoop filter + watch-list config.
Ported from Resume/automation june 2/config.py (locked 2026-06-02), plus A/B/C tiers.
Single source of truth for the sourcing + cleaning stage. Editable anytime.
"""

COUNTRY_ONLY = "India"  # international DROPPED (visa). Any mode: hybrid/remote/in-office.

# Location strings that count as India (lowercased substring match).
INDIA_LOCATION_HINTS = [
    "india", "bengaluru", "bangalore", "mumbai", "gurugram", "gurgaon",
    "hyderabad", "delhi", "new delhi", "noida", "pune", "chennai",
    "kolkata", "ahmedabad", "remote - india", "remote, india", "remote india",
]

ROLE_PRIMARY = [
    "product manager", "pm", "associate product manager", "apm",
    "senior product manager", "platform product", "technical product",
    "growth product", "consumer product",
]
ROLE_SECONDARY = ["ai product", "ai pm", "ai prototyping", "ai builder"]
ROLE_FUNCTION_OUT = ["product operations", "product ops", "chief of staff"]

LEVELS_IN = ["apm", "associate", "pm", "pm i", "pm ii", "product manager", "senior product manager"]
LEVELS_OUT = ["lead", "principal", "group product", "director", "vp", "head of"]

EXCLUDE_KEYWORDS = [
    "intern", "internship", "trainee", "contract", "temporary", "temp", "c2h",
    "product marketing", "growth marketing", "program manager", "project manager",
]

# Drop a role if its JD clearly requires MORE than this many years of experience.
# Vardhan = ~4 yrs work + MBA ≈ 6 max. Roles with no stated requirement are kept (can't tell).
# Only applies to roles that HAVE a JD (ATS); LinkedIn alert roles have no JD to parse. Tunable.
MAX_YEARS_EXPERIENCE = 6

# Don't let one employer flood Triage. Show at most this many roles per company in the queue
# (newest first); the rest surface as you clear them. Stops the "50 Amazon roles" problem. Tunable.
MAX_PER_COMPANY_TRIAGE = 6

# Third-party staffing / recruiter listings (not the real employer). Light-touch: flagged on the
# card as "via recruiter" so the user knows the company shown is an agency, not the hiring company.
RECRUITER_PATTERNS = [
    "staffing", "recruit", "manpower", "placement", "hr solutions", "hr services",
    "consultancy", "consultants", "talent leads", "headhunt", "rpo", "outsourc",
]

# Wikidata employee count at/above which an uncurated company tiers B (else C). Used by tiering.py.
WIKIDATA_MIN_EMPLOYEES_B = 1000
# A snoozed role stays hidden from Triage for this many hours, then resurfaces.
SNOOZE_HOURS = 12
PDF_OUTPUT_NAME = "Sai_Vardhan_Palli_Product_Manager_IIMB_CV.pdf"

# --- watch-list / tiers ---
# Tier A = instant Telegram push. Tier B = pull/batched. Tier C = legit but lesser.
# Unknown broad-net companies resolve to "U" (unverified) until Wikidata says otherwise.
TIER_A = [
    "Meesho", "Mastercard", "CarTrade", "OLX", "Amazon", "Google", "American Express",
    "IDFC FIRST Bank", "JPMorgan Chase", "Razorpay", "HDFC", "PhonePe", "Goldman Sachs",
    "Aditya Birla Capital", "Policybazaar", "Microsoft", "Walmart Global Tech", "Lenskart", "Cult.fit",
    # Added 2026-06-24 (iter-1): seen via LinkedIn, elite/global brands. "JPMorganChase" is the
    # no-space LinkedIn spelling that the spaced "JPMorgan Chase" above was missing.
    "JPMorganChase", "Wells Fargo", "HSBC", "UBS", "eBay", "PepsiCo", "McKinsey",
]
TIER_B = [
    "Flipkart", "Swiggy", "Zomato", "Uber", "Stripe", "Adobe", "Atlassian",
    "Salesforce", "Standard Chartered", "Citi", "Barclays",
    # India PM employers that were landing as "U" — curated to improve tier coverage.
    "Airtel", "Bharti Airtel", "Airtel Payments Bank", "Deloitte", "Accenture", "PwC", "KPMG",
    "EY", "Ernst & Young", "Jio", "Reliance Jio", "Tata", "Infosys", "Wipro", "TCS", "Cognizant",
    "Myntra", "Nykaa", "Dream11", "MakeMyTrip", "Ola", "Navi", "Groww", "Zepto", "PharmEasy",
    "Cred", "ShareChat", "Unacademy", "BrowserStack", "Postman", "Freshworks", "Zoho",
    "EazyDiner", "Urban Company", "BigBasket", "Blinkit", "PayU", "Pine Labs", "BharatPe",
    "Yes Bank", "Axis Bank", "ICICI", "Kotak", "DBS", "Visa", "PayPal", "Intuit", "SAP",
    # Added 2026-06-24 (iter-1): real employers seen via LinkedIn that were landing as "U".
    # Short canonical tokens (word-aware match in tiering._matches): "Siemens" covers
    # Siemens Healthineers/Energy, "Ford" covers Ford Motor Company, etc.
    "Siemens", "Ford", "Tesco", "Target", "Philips", "Optum", "LSEG", "LTIMindtree", "HCLTech",
    "Capgemini", "Delhivery", "IndusInd", "Paisabazaar", "Times Internet", "Sony Pictures",
    "Nielsen", "Docusign", "ZoomInfo", "Chevron", "Lam Research", "Epsilon", "Nexthink", "Entain",
    "boAt Lifestyle", "Hitachi", "Deutsche Telekom", "Eltropy", "Xoxoday", "super.money",
    # Newly-wired ATS feeds (iter-1) whose companies weren't pinned yet.
    "Atlan", "Slice", "Observe.ai", "Stable",
]
# Tier C = curated "legit but lesser / personal-reputation downgrade". Pinned here so a
# company that Wikidata would size into B can be held at C by judgment (e.g. Paytm).
# Checked AFTER A/B, BEFORE the Wikidata fallback. Edit anytime (also via Settings).
TIER_C = [
    "Paytm",
]

POLL_INTERVAL_MIN = 30
