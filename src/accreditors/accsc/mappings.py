"""ACCSC crosswalk seeds to federal/state requirements."""

ACCSC_CROSSWALK_SEEDS = {
    "VII.A": {
        "federal": ["34 CFR 668.43(a)(5)", "34 CFR 668.43(a)(6)"],
        "common_state": ["refund_policy", "student_grievance"]
    },
    "III.A": {
        "federal": ["34 CFR 668.23"],
        "common_state": ["financial_capacity"]
    },
    "IV.A": {
        "federal": ["34 CFR 668.8"],
        "common_state": ["clock_hour", "credit_hour"]
    }
}
