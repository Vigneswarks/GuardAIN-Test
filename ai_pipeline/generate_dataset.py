from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any

random.seed(2024)

CATEGORIES = {
    "digital_arrest": [
        "digital arrest",
        "cybercrime team",
        "police summons",
        "court case",
        "money laundering",
    ],
    "utility_disconnection": [
        "electricity disconnection",
        "broadband cutoff",
        "gas line security",
        "water supply disconnect",
        "bank account freeze",
    ],
    "upi_collect": [
        "UPI QR collect",
        "scan QR code",
        "payment request",
        "collect payment",
        "quick payment link",
    ],
    "phishing": [
        "click here to secure account",
        "verify bank details",
        "login to update KYC",
        "password reset now",
        "suspicious login alert",
    ],
}
BENIGN_TEMPLATES = [
    "The meeting is confirmed for {time}; please share the agenda when convenient.",
    "Your invoice is attached for review. No payment is required until you approve it.",
    "I will call you after lunch. Have a good day.",
    "The bank branch appointment is booked; bring identification in person.",
]

PEOPLE = [
    "Aarav", "Meera", "Nisha", "Rohit", "Priya", "Vivek", "Ananya", "Karan", "Pooja", "Sahil",
    "Aditi", "Yash", "Neha", "Rakesh", "Ishita", "Dev", "Sakshi", "Harsh", "Bhavna", "Manoj"
]
CITIES = ["Delhi", "Mumbai", "Bengaluru", "Hyderabad", "Lucknow", "Jaipur", "Patna", "Pune", "Ahmedabad", "Kolkata"]
BANKS = ["HDFC", "ICICI", "SBI", "Axis", "Kotak", "Paytm", "Yes Bank", "BOI"]
URLS = ["verify-kyc.in", "secure-bank-update.co.in", "support-login.click", "quickpay-verify.net", "secure-portal.site"]
SAFE_URLS = ["https://www.google.com", "https://www.bing.com", "https://www.thehindu.com",
             "https://www.gov.in", "https://www.nic.in", "https://www.sbi.co.in"]
DEVANAGARI_MESSAGES = [
    "आपका खाता बंद होने वाला है, तुरंत केवाईसी सत्यापित करें।",
    "साइबर क्राइम अधिकारी बोल रहा हूं, डिजिटल गिरफ्तारी से बचने के लिए पैसे भेजें।",
    "कल की बैठक पांच बजे है, कृपया एजेंडा साझा करें।",
]


def generate_phone() -> str:
    return f"+91 {random.randint(6000000000, 9999999999)}"


def generate_account() -> str:
    return str(random.randint(1000000000, 9999999999))


def generate_aadhaar() -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(12))


def generate_upi() -> str:
    return f"{random.choice(PEOPLE).lower()}@{random.choice(BANKS).lower()}"


def make_hinglish_variant(template: str, category: str) -> str:
    replacements = {
        "Aadhaar": "Aadhaar",
        "bank": "bank",
        "UPI": "UPI",
        "QR": "QR",
        "link": "link",
        "verify": "verify",
        "secure": "secure",
        "account": "account",
    }
    for source, target in replacements.items():
        template = template.replace(source, target)
    fillers = [
        " yaar",
        " bhai",
        " aapka account",
        " urgent",
        " asap",
        " please",
        " abhi",
    ]
    if random.random() > 0.5:
        template = template + random.choice(fillers)
    if category == "digital_arrest":
        template = template + " Police officer ne call kiya hai; abhi action lo."
    elif category == "utility_disconnection":
        template = template + " service suspend hone wali hai."
    elif category == "upi_collect":
        template = template + " Pay karna hoga to request accept karo."
    elif category == "phishing":
        template = template + " credentials verify karna mandatory hai."
    return template


def build_sample(category: str, index: int) -> dict[str, Any]:
    person = random.choice(PEOPLE)
    city = random.choice(CITIES)
    bank = random.choice(BANKS)
    domain = random.choice(URLS)
    phone = generate_phone()
    aadhaar = generate_aadhaar()
    account = generate_account()
    vpa = generate_upi()

    templates = {
        "digital_arrest": [
            f"{person}, your digital arrest case is linked to {city}. Immediate action required under cybercrime investigation. If you do not respond, police will act today.",
            f"Aadhaar {aadhaar} is being checked by the investigation team. Do not call anyone. Pay now or your case will be escalated.",
            f"This is from cybercrime cell: your complaint is flagged. Call this number {phone} and follow the instructions immediately.",
        ],
        "utility_disconnection": [
            f"Your electricity and broadband service in {city} is scheduled for disconnection due to unpaid dues. Verify your account {account} now.",
            f"{bank} security alert: your utility payment has failed. Confirm the latest bill to avoid service cutoff.",
            f"Due to a failed verification, your gas and internet line will be disconnected unless you confirm your bank details immediately.",
        ],
        "upi_collect": [
            f"{person}, please scan this QR to collect payment for the invoice. UPI ID: {vpa}. Do not delay; this is time-sensitive.",
            f"Security update: request payment via QR code. Use the collect request and send amount using {vpa} before 6 PM.",
            f"The merchant has sent a QR collect request. Please pay via the payment link and confirm the receipt.",
        ],
        "phishing": [
            f"Urgent security alert for your {bank} account. Click here to reset your login and secure your KYC: https://{domain}/secure",
            f"Login to your bank portal now to verify your credential and prevent fraud. This is a mandatory compliance check.",
            f"Verification needed: your account is at risk. Click the link to confirm your details and avoid suspension.",
        ],
    }

    if category == "benign":
        text = random.choice(BENIGN_TEMPLATES).format(time=random.choice(["5 pm", "tomorrow morning", "next Tuesday"]))
        vpa = f"{random.choice(PEOPLE).lower()}@{random.choice(['okaxis', 'oksbi', 'okhdfcbank'])}"
        return {"id": f"benign-{index:05d}", "category": category, "label": "benign",
                "language": random.choice(["hinglish", "hindi", "english"]), "message": text,
                "phone": "", "aadhaar": "", "bank_account": "", "vpa": vpa, "domain": random.choice(SAFE_URLS),
                "city": city, "person": person, "risk_score": round(random.uniform(0.0, 0.15), 4)}
    base_text = random.choice(templates[category])
    text = make_hinglish_variant(base_text, category)
    if index % 5 == 0 or random.random() < 0.35:
        text = f"{text} {random.choice(DEVANAGARI_MESSAGES[:2])}"
    return {
        "id": f"fraud-{category}-{index:05d}",
        "category": category,
        "label": "fraud",
        "language": random.choice(["hinglish", "hindi", "english", "devanagari"]),
        "message": text,
        "phone": phone,
        "aadhaar": aadhaar,
        "bank_account": account,
        "vpa": vpa,
        "domain": f"https://{domain}/verify",
        "city": city,
        "person": person,
        "risk_score": round(random.uniform(0.7, 0.99), 4),
    }


def write_dataset(samples: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for sample in samples:
            handle.write(json.dumps(sample, ensure_ascii=False) + "\n")


def generate_dataset(target_count: int = 2400) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    category_cycle = ["digital_arrest", "utility_disconnection", "upi_collect", "phishing", "benign"]
    for index in range(target_count):
        category = category_cycle[index % len(category_cycle)]
        samples.append(build_sample(category, index + 1))
    return samples


if __name__ == "__main__":
    output_dir = Path("./data")
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset = generate_dataset(2400)
    write_dataset(dataset, output_dir / "synthetic_fraud_dataset.jsonl")
    summary = {category: sum(1 for item in dataset if item["category"] == category) for category in (*CATEGORIES, "benign")}
    print(json.dumps({"records": len(dataset), "summary": summary, "path": str(output_dir / "synthetic_fraud_dataset.jsonl")}, ensure_ascii=False))
