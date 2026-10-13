from typing import List, Dict, Any, Optional

VERIFIED_SCHEMES = [
    {
        "id": "SCHEME-01",
        "name": "PM-KISAN + Namo Shetkari Mahasanman Nidhi",
        "type": "Direct Income Support",
        "benefit_amount": "₹12,000 / year (₹6,000 Central + ₹6,000 Maharashtra State)",
        "frequency": "₹2,000 every 4 months via DBT",
        "eligibility": "Small and marginal farmers owning cultivable land verified in 7/12 extract; Aadhaar-linked active bank account; completed e-KYC.",
        "exclusions": "Institutional landholders, income tax payees in previous assessment year, serving/retired government employees, constitutional post holders.",
        "required_documents": [
            "Aadhaar Card",
            "Updated 7/12 (Saat Baara) and 8A Land Records",
            "Bank Passbook (Aadhaar NPCI mapped)",
            "Active Mobile Number linked to Aadhaar for OTP"
        ],
        "application_mode": "Online via pmkisan.gov.in or CSC (Common Service Center) / Maha e-Seva Kendra",
        "official_portal": "https://pmkisan.gov.in",
        "state_portal": "https://nsmn.mahashetkari.in",
        "helpline": "155261 / 011-24300606"
    },
    {
        "id": "SCHEME-02",
        "name": "Pradhan Mantri Fasal Bima Yojana (PMFBY @ ₹1 Scheme)",
        "type": "Crop Insurance Protection",
        "benefit_amount": "Comprehensive insurance coverage against non-preventable natural risks; Farmers pay only ₹1 token premium per application in Maharashtra.",
        "frequency": "Seasonal (Kharif & Rabi)",
        "eligibility": "All farmers including sharecroppers and tenant farmers growing notified crops in notified areas. Non-loanee and loanee farmers both eligible.",
        "exclusions": "Losses due to war, nuclear risks, malicious damage, or preventable pest negligence.",
        "required_documents": [
            "Aadhaar Card",
            "7/12 Extract with crop sowing entry (Pik Pahani / ई-पीक पाहणी app)",
            "Bank Passbook with IFSC code",
            "Sowing Certificate or Self-Declaration"
        ],
        "application_mode": "Online through pmfby.gov.in or Aaple Sarkar / Bank branch before cutoff deadline",
        "official_portal": "https://pmfby.gov.in",
        "state_portal": "https://krishi.maharashtra.gov.in",
        "helpline": "14447 (National Toll-free) / Crop Insurance App"
    },
    {
        "id": "SCHEME-03",
        "name": "MahaDBT Farmer Machinery & Micro-Irrigation Subsidy",
        "type": "Capital Subsidy for Farm Equipment",
        "benefit_amount": "40% to 50% subsidy on Tractors, Rotavators, Power Tillers; 55% subsidy on Drip and Sprinkler sets.",
        "frequency": "One-time per asset type",
        "eligibility": "Individual farmers residing in Maharashtra with land records; selection via centralized computerized lottery.",
        "exclusions": "Farmers who have already availed subsidy for the same equipment category within the last 7 years.",
        "required_documents": [
            "Aadhaar Card & 7/12 Extract",
            "8A Khata Utara",
            "Caste Certificate (if applying for SC/ST higher subsidy)",
            "Quotation from authorized dealer with GST registration"
        ],
        "application_mode": "MahaDBT Farmer Login (mahadbt.maharashtra.gov.in)",
        "official_portal": "https://mahadbt.maharashtra.gov.in",
        "state_portal": "https://krishi.maharashtra.gov.in",
        "helpline": "022-49150800"
    },
    {
        "id": "SCHEME-04",
        "name": "Kisan Credit Card (KCC)",
        "type": "Subsidized Agricultural Working Capital Loan",
        "benefit_amount": "Short-term crop loan up to ₹3,00,000 at effective interest rate of 4% per annum (with prompt repayment incentive).",
        "frequency": "Revolving credit facility valid for 5 years",
        "eligibility": "All farmers, individual/joint cultivators, tenant farmers, Self-Help Groups (SHGs).",
        "exclusions": "Wilful bank loan defaulters.",
        "required_documents": [
            "Duly filled KCC Application Form",
            "Aadhaar Card and PAN Card (or Form 60)",
            "Land title verification certificate from Talathi / 7/12 extract",
            "No Dues Certificate from adjacent cooperative or nationalized banks"
        ],
        "application_mode": "Any Rural / Commercial Bank, Primary Agricultural Credit Society (PACS), or PM-KISAN portal KCC link",
        "official_portal": "https://www.myscheme.gov.in/schemes/kcc",
        "state_portal": "https://agricoop.nic.in",
        "helpline": "1800-180-1551"
    }
]

class SchemeService:
    @staticmethod
    def get_all_schemes() -> List[Dict[str, Any]]:
        return VERIFIED_SCHEMES

    @staticmethod
    def check_eligibility(
        land_acres: float,
        is_taxpayer: bool,
        ekyc_completed: bool,
        has_saatbaara: bool
    ) -> Dict[str, Any]:
        """
        Evaluates farmer eligibility for major schemes transparently.
        Never guarantees final disbursement.
        """
        results = []

        # PM-KISAN + Namo Shetkari
        if not is_taxpayer and has_saatbaara:
            if ekyc_completed:
                pm_status = "Likely Eligible"
                pm_reason = "You meet basic criteria: registered landowner, non-taxpayer, and e-KYC confirmed. Final benefit depends on district land verification."
            else:
                pm_status = "Action Required"
                pm_reason = "Eligible, but you MUST complete biometric or OTP e-KYC on pmkisan.gov.in to receive pending installments."
        else:
            pm_status = "Likely Ineligible"
            pm_reason = "Income-tax payers and non-landholding families are excluded from PM-KISAN guidelines."

        results.append({
            "scheme_name": "PM-KISAN + Namo Shetkari",
            "status": pm_status,
            "explanation": pm_reason,
            "next_step": "Visit pmkisan.gov.in > Farmers Corner > 'Know Your Status' to check Aadhaar seeding."
        })

        # PMFBY Crop Insurance
        if has_saatbaara:
            pmfby_status = "Eligible"
            pmfby_reason = "All landholding and tenant farmers can insure their notified crops for ₹1 premium in Maharashtra."
        else:
            pmfby_status = "Documentation Needed"
            pmfby_reason = "Tenant declaration or sowing agreement required if land record is not in your name."

        results.append({
            "scheme_name": "PM Fasal Bima Yojana (₹1 Insurance)",
            "status": pmfby_status,
            "explanation": pmfby_reason,
            "next_step": "Submit Pik Pahani on e-Pik Pahani mobile app, then apply on pmfby.gov.in before seasonal cutoff."
        })

        return {
            "disclaimer": "This assessment is an advisory guideline based on official scheme rules. Final qualification and disbursement are subject to government verification.",
            "schemes_evaluated": results
        }
