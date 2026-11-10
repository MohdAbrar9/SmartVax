"""
vaccine_info.py
---------------
Plain-language information about each vaccine in the schedule. This is
shown on the shared "Vaccine Info" page that parents, ASHA workers and
admins can all open.

Each entry's "match" is a keyword searched for inside vaccine_master's
vaccine_name, so the page can show, for example, all three "OPV - x"
doses under one OPV card. Edit the text here to change what the page
says; no database change is needed.

NOTE: This follows India's Universal Immunization Programme in simplified
form. Always confirm exact doses and timings with the local health
centre / doctor.
"""

VACCINE_GUIDE = [
    {
        "name": "BCG",
        "match": "BCG",
        "protects_against": "Tuberculosis (TB), especially severe forms in young children.",
        "when": "At birth (can be given up to 1 year of age).",
        "how": "Single dose, injected into the skin of the left upper arm.",
        "side_effects": "A small lump or sore at the injection site that heals within weeks and leaves a small scar. This is normal.",
        "see_doctor": "Large abscess, swollen glands under the arm, or a wound that does not heal.",
    },
    {
        "name": "OPV (Oral Polio Vaccine)",
        "match": "OPV",
        "protects_against": "Poliomyelitis (polio), which can cause permanent paralysis.",
        "when": "At birth (OPV-0), then at 6, 10 and 14 weeks.",
        "how": "Drops given by mouth.",
        "side_effects": "Usually none. Very rarely, mild stomach upset.",
        "see_doctor": "Any weakness or floppiness in the limbs after vaccination.",
    },
    {
        "name": "Hepatitis B",
        "match": "Hepatitis B",
        "protects_against": "Hepatitis B, a liver infection that can become long-term.",
        "when": "Within 24 hours of birth (birth dose). Later doses come through the Pentavalent vaccine.",
        "how": "Injection into the muscle of the thigh.",
        "side_effects": "Soreness at the injection site, mild fever.",
        "see_doctor": "High fever, swelling of the face or trouble breathing.",
    },
    {
        "name": "Pentavalent",
        "match": "Pentavalent",
        "protects_against": "Five diseases in one injection: Diphtheria, Pertussis (whooping cough), Tetanus, Hepatitis B and Hib (a cause of pneumonia and meningitis).",
        "when": "At 6, 10 and 14 weeks, with a booster later as listed in this app's schedule.",
        "how": "Injection into the muscle of the thigh.",
        "side_effects": "Fever, pain or swelling where the injection was given, fussiness, sleepiness. Usually gone in 1-2 days.",
        "see_doctor": "Fever lasting more than 2 days, crying non-stop for 3+ hours, seizures, or trouble breathing.",
    },
    {
        "name": "Measles-Rubella (MR)",
        "match": "Measles-Rubella",
        "protects_against": "Measles and Rubella. Measles can cause pneumonia and brain swelling; rubella in pregnancy can harm unborn babies.",
        "when": "First dose at 9-12 months, second dose at 16-24 months.",
        "how": "Injection under the skin of the upper arm.",
        "side_effects": "Mild fever or a light rash 5-12 days after, soreness at the injection site.",
        "see_doctor": "High fever, seizures, or signs of allergic reaction soon after the injection.",
    },
    {
        "name": "Vitamin A",
        "match": "Vitamin A",
        "protects_against": "Vitamin A deficiency, which can cause night blindness and weaken the body against infections.",
        "when": "First dose at 9 months, given along with the first MR dose.",
        "how": "Liquid given by mouth.",
        "side_effects": "Rarely, mild vomiting or headache for a short time.",
        "see_doctor": "Persistent vomiting or a bulging soft spot on the baby's head.",
    },
    {
        "name": "DPT Booster",
        "match": "DPT",
        "protects_against": "Diphtheria, Pertussis (whooping cough) and Tetanus. The booster keeps protection strong as the child grows.",
        "when": "At 16-24 months.",
        "how": "Injection into the muscle of the upper arm or thigh.",
        "side_effects": "Fever, soreness or swelling at the injection site, tiredness.",
        "see_doctor": "Fever lasting more than 2 days, severe swelling of the limb, or seizures.",
    },
]

# General tips shown at the top/bottom of the page.
BEFORE_TIPS = [
    "Carry the child's vaccination card to every visit.",
    "Tell the health worker if the child is unwell, has a high fever, or has had a reaction before.",
    "A mild cold or small fever is usually not a reason to skip a vaccine. Let the health worker decide.",
]

AFTER_TIPS = [
    "Stay at the centre for about 30 minutes after the injection.",
    "Breastfeed or give fluids often. Dress the baby lightly if there is fever.",
    "Do not apply anything (ointment, oil, hot or cold packs) on the injection site unless the doctor advises.",
    "Contact your ASHA worker or doctor if the child seems very unwell.",
]
