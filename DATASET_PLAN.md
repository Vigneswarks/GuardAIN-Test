# MuRIL data and validation plan

There is currently no independently labeled financial-fraud dataset in this
project. The generated JSONL is synthetic development data. Its random split
shares templates across training and validation, so its accuracy is not a
valid real-world fraud benchmark.

Start with the UCI SMS Spam Collection as a public English spam baseline:
https://archive.ics.uci.edu/dataset/228/sms+spam+collection
UCI lists CC BY 4.0 licensing; preserve attribution when using it. Spam is not
the same label as financial fraud, and this corpus does not establish Hindi,
Hinglish, digital-arrest or UPI detection quality. Do not rename all spam as
fraud in the existing trainer.

Build a separate consented/redacted financial-fraud corpus with labels for
fraud, legitimate, educational/news discussion and ambiguous cases. Include
digital arrest, KYC/OTP phishing, fake investments, advance-fee jobs, UPI
collect scams and genuine banking/payment notifications. Each item should
record language, source, reviewer label and campaign/template grouping.
Never include real passwords, OTPs, full cards, account numbers or screenshots
in training data without appropriate permission and redaction.

Use independently reviewed labels and hold out whole sources/campaigns and
templates before training. Deduplicate near-identical messages. Report per-
language and per-scenario precision, recall, false-positive rate and calibration
on the untouched test set, including a large educational/news challenge set.
Select thresholds on validation data only. Compare MuRIL-only predictions
with the fallback baseline; page blocking remains a separate policy decision.

Do not mark the deployment ready for financial or government use based on
training accuracy, synthetic examples or a model filename. The current
training/export commands are development tooling and remain unexecuted here.
