# GuardAIN fraud-triage test cases

These are safe, fictional exhibition tests. They use no real bank account,
VPA, OTP, payment link, credential, or victim data. Replace only the text in
the PWA or open only the local URLs listed below.

## How to execute

1. Start the API with `./start.ps1` and open `http://127.0.0.1:8080/health`.
   Expected: `database: true`, `redis: true`, and `model_loaded: true`.
2. Open `http://127.0.0.1:8080/pwa/` and confirm **Central server connected**.
3. For message cases, paste the input into **Message scam check** and select
   **Analyse message**.
4. For VPA cases, use **UPI/VPA check**. For URL cases, use **URL reputation**
   or open the listed local page with the GuardAIN extension enabled.
5. For every case marked **Central report: Yes**, refresh the administrator
   portal (`http://127.0.0.1:8080/`) and confirm an incident with source
   `pwa-triage` or `extension` appears.

The exact model score can vary after retraining. Verify the risk band and
action, not an exact decimal score. The current local MuRIL model is an ONNX
demonstration model trained on synthetic data; these cases demonstrate system
behaviour and are not a clinical/production accuracy claim.

## A. MuRIL multilingual high-risk message cases

| ID | Language | Safe fictional input | Expected label / risk | Expected central report | What it checks |
|---|---|---|---|---|---|
| M-01 | English | `CBI digital arrest notice. Share your OTP and UPI PIN now or your account will be frozen.` | Fraud / High | Yes | Authority impersonation + urgency + OTP/UPI credential request |
| M-02 | Hinglish | `Sir RBI verification ke liye abhi OTP aur UPI PIN bhejo, warna account block ho jayega.` | Fraud / High | Yes | Hinglish phishing language and financial-pressure indicators |
| M-03 | Hindi | `आपको डिजिटल गिरफ्तारी नोटिस है। खाता बंद होने से बचाने के लिए अभी OTP और UPI PIN बताइए।` | Fraud / High | Yes | Hindi digital-arrest and secret-request detection |
| M-04 | Manglish | `Bank officer aanu. Account freeze avoid cheyyan ippol thanne OTP um UPI PIN um send cheyyu.` | Fraud / High | Yes | Malayalam-English transliteration and credential request |
| M-05 | Tamil-English | `RBI case irukku. Account block aagum, immediate ah OTP and UPI PIN share pannunga.` | Fraud / High | Yes | Tamil-English transliteration and urgency pattern |
| M-06 | Telugu-English | `Cyber cell nundi call. Verification kosam ippude OTP and UPI PIN cheppandi.` | Fraud / High | Yes | Telugu-English transliteration and impersonation |
| M-07 | English | `You won a reward. Pay a small processing fee through UPI immediately to claim it.` | Fraud / Review or High | Yes | Prize lure + advance-fee payment demand |
| M-08 | Hinglish | `Courier parcel hold par hai. Delivery release ke liye is unknown link par payment karo.` | Fraud / Review or High | Yes | Delivery-lure plus external-payment signal |
| M-09 | Hindi | `आपके नाम पर लोन स्वीकृत हुआ है। रद्द करने के लिए स्क्रीन शेयर करें और OTP बताएं।` | Fraud / High | Yes | Loan scam + remote-access/OTP request |
| M-10 | English | `Your KYC will expire today. Install our support app and share the verification code.` | Fraud / High | Yes | KYC urgency + risky app/code request |

## B. MuRIL false-positive control cases

| ID | Input | Expected label / risk | Central report | What it proves |
|---|---|---|---|---|
| M-11 | `The college seminar discusses digital arrest fraud awareness. Never share OTP or UPI PIN.` | Benign / Low | No | Fraud words alone must not cause a block |
| M-12 | `I paid my electricity bill using the official provider app.` | Benign / Low | No | Normal UPI/payment discussion is not fraud |
| M-13 | `Your bank states that it will never ask for an OTP over a call.` | Benign / Low | No | Prevents safety advice being marked as a scam |
| M-14 | `Please review the RBI consumer-awareness poster for online fraud prevention.` | Benign / Low | No | Government/bank references alone are not evidence |

## C. UPI/VPA test cases

Use the PWA **UPI/VPA check** field. These are fabricated identifiers; do not
attempt a payment or lookup outside GuardAIN.

| ID | Test VPA / linked statement | Expected outcome | Central report | What it checks |
|---|---|---|---|---|
| U-01 | `claim.reward@unknown-pay` with message `Pay ₹1 to unlock your prize.` | Review or High risk | Yes | Unknown handle + advance-fee lure |
| U-02 | `verify.kyc@pay-test` with message `Send money to verify KYC.` | High risk | Yes | Payment-to-verify-KYC fraud pattern |
| U-03 | `refund.desk@pay-test` with message `Enter UPI PIN to receive your refund.` | High risk | Yes | Refund deception and PIN misuse |
| U-04 | `legal.notice@pay-test` with message `Pay now to stop digital arrest.` | High risk | Yes | Authority threat + UPI demand |
| U-05 | `merchant.demo@upi` with message `Payment for a known local demo merchant.` | Unknown/Low; no automatic block | No | VPA syntax alone must not label a merchant fraudulent |
| U-06 | `not a valid vpa` | Input validation error | No | Invalid VPA is rejected safely, not treated as a fraud conviction |

## D. High-risk URL and extension test cases

Load/reload the extension before these tests. The local pages are purposely
crafted training fixtures; they do not transmit data or imitate a real bank.

| ID | URL / action | Expected extension decision | Expected central report | What it checks |
|---|---|---|---|---|
| U-URL-01 | `http://127.0.0.1:8080/demo/extension-test` | Block warning followed by timed close | Yes, `extension` | Corroborated credential phishing signals |
| U-URL-02 | `http://127.0.0.1:8080/demo/upi-payment` | Block warning followed by timed close | Yes, `extension` | Urgent payment/UPI scam page signals |
| U-URL-03 | `http://127.0.0.1:8080/demo/review-only` | Review warning only; do not auto-close | Optional/Yes depending score | Suspicious signals below hard-block threshold |
| U-URL-04 | `http://127.0.0.1:8080/demo/awareness` | Allow; no overlay or close | No | Scam-awareness content is not blocked by keywords |
| U-URL-05 | `http://127.0.0.1:8080/demo/normal-login` | Allow; no overlay or close | No | Normal same-origin login should not be classified as phishing |
| U-URL-06 | In PWA URL reputation, enter `https://secure-update.example.invalid/login` | Review/unknown until corroborating page signals or analyst review | Report only if Review/High | A suspicious-looking URL alone is not an automatic conviction |
| U-URL-07 | In PWA URL reputation, enter `https://www.google.com/` | Safe-domain bypass / Allow | No | Approved safe domains are strictly bypassed |

## Acceptance criteria

| Area | Pass condition |
|---|---|
| MuRIL inference | M-01 through M-10 show a fraud-oriented result and explanation; M-11 through M-14 remain low risk. |
| Privacy | Low-risk PWA checks show no central incident delivery card claiming a queued report. |
| Central integration | Every High/Review PWA case marked Yes creates a portal incident containing `source: pwa-triage`, score, analysis, and browser metadata. |
| Extension circuit breaker | U-URL-01 and U-URL-02 display the warning and close after the configured timeout unless the user explicitly chooses the override. |
| Safe-domain control | U-URL-07 remains allowed and is never blocked based on message keywords alone. |
| VPA validation | U-06 fails as a validation issue without any payment action, external lookup, or domain conviction. |

## Evidence to capture for the final report

For M-01, U-03, U-URL-01, and U-URL-04 capture one screenshot each showing:

1. The input and visible risk result.
2. The PWA/extension delivery or protection status.
3. The corresponding central portal incident for a high-risk case.
4. The absence of an incident or block for the awareness/safe control.

Do not display real customer messages, OTPs, account numbers, UPI PINs, or
personally identifiable data in the project demonstration.
