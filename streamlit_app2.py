"""
Streamlit AI-ish Concrete Mix Designer & Optimizer
Author: ChatGPT (assistant)
Description: Professional single-file Streamlit app that:
 - Asks user for target compressive strength (20-60 MPa, 5 MPa steps)
 - Asks user for target slump (25-150 mm, 5 mm steps)
 - Computes an initial (baseline) mix design for 1 m^3 (heuristic absolute-volume method)
 - Provides an "Optimization Option (make concrete more sustainable)" that searches
   candidate mixes with SCMs (Fly Ash, GGBS/Slag) and recycled aggregate replacements
   to find mixes with properties close to the requested ones while reducing CO2 and cost.

IMPORTANT: This app uses simple, demonstrative heuristic models for strength/workability
prediction and for CO2/cost reductions. For production use you MUST replace the surrogate
models with calibrated predictive models (lab or literature data) or add a dataset and
train ML regressors.

How to run:
  pip install streamlit pandas numpy scipy Pillow
  streamlit run streamlit_concrete_app.py

"""

import streamlit as st
import pandas as pd
import numpy as np
from math import isclose
from PIL import Image

st.set_page_config(page_title="Concrete Mix Designer 🏗️🌱", layout="wide")

# ----------------------------- Helper predictive heuristics -----------------------------
# NOTE: these are simplified surrogate models intended for demonstration only.
# Replace or calibrate them with real experiments or a trained ML model.

def estimate_wcr_from_strength(fc_target):
    """Estimate water/cement ratio from target compressive strength (MPa).
    Mapping: 20 MPa -> 0.60, 60 MPa -> 0.30 (linear approximation)."""
    return 0.6 - (fc_target - 20) * (0.3 / 40)


def estimate_water_content_from_slump(slump_mm):
    """Estimate water content (kg/m3) from slump (mm) using a linear mapping
    25 mm -> 160 kg/m3, 150 mm -> 210 kg/m3."""
    base = 160.0
    slope = (210.0 - 160.0) / (150.0 - 25.0)
    return base + slope * (slump_mm - 25.0)


def predict_strength_modifier(scm_pct, scm_type, ra_pct):
    """Predict multiplicative strength modifier (baseline) based on SCM and recycled agg.
    Returns factor f where predicted_strength = baseline_strength * f.

    These are heuristic approximate effects: - SCM may reduce early strength but later
    can contribute to strength. We use simple sign & magnitude assumptions:
      - Fly Ash (FA) tends to slightly reduce early-age strength per % replacement
      - GGBS/Slag tends to keep/boost strength slightly or have small penalty
    Recycled aggregate (RA) typically reduces strength as replacement increases.
    """
    # base factors per 1% replacement
    if scm_type == 'None':
        scm_effect_perc = 0.0
    elif scm_type == 'Fly Ash':
        scm_effect_perc = -0.0020  # -0.2% strength per 1% FA (approx early-age)
    elif scm_type == 'GGBS (Slag)':
        scm_effect_perc = -0.0005  # small penalty or near-neutral early on
    else:
        scm_effect_perc = 0.0

    ra_effect_perc = -0.0035  # -0.35% strength per 1% recycled agg replacement (heuristic)

    factor = 1.0 + scm_effect_perc * scm_pct + ra_effect_perc * ra_pct
    # prevent negative
    return max(0.5, factor)


def predict_slump_modifier(scm_pct, scm_type, ra_pct):
    """Predict slump/workability modifier (multiplicative) -- SCMs often increase workability
    (esp. fly ash) while recycled aggregates tend to reduce it (more angular, absorbent).
    """
    if scm_type == 'Fly Ash':
        scm_w_effect = 1.0 + 0.0025 * scm_pct  # increases slump a bit per %
    elif scm_type == 'GGBS (Slag)':
        scm_w_effect = 1.0 + 0.0010 * scm_pct
    else:
        scm_w_effect = 1.0

    ra_w_effect = 1.0 - 0.0018 * ra_pct  # decreases slump by ~0.18% per 1% RA
    return max(0.6, scm_w_effect * ra_w_effect)

# CO2 & cost factors per kg (typical placeholders; adjust per local data)
CO2_FACTORS = {
    'cement': 0.85,        # kg CO2 per kg cement (typical global average — adjust)
    'fly_ash': 0.02,       # negligible embodied CO2 for industrial by-product
    'ggbs': 0.05,
    'water': 0.0003,
    'fine_agg': 0.005,
    'coarse_agg': 0.005,
}
COST_FACTORS = {
    'cement': 0.10,   # currency unit per kg
    'fly_ash': 0.02,
    'ggbs': 0.03,
    'water': 0.001,
    'fine_agg': 0.01,
    'coarse_agg': 0.01,
}

# ----------------------------- Baseline mix design (absolute volume simple) -----------------------------
# Assumptions for densities (kg/m3 bulk densities)
RHO = {
    'cement': 1440.0,
    'water': 1000.0,
    'fine_agg': 1600.0,
    'coarse_agg': 1500.0,
    'fly_ash': 2200.0,  # particle density
    'ggbs': 3100.0,
}


def baseline_mix_design(fc_target, slump_target, fine_to_total=0.40):
    """Compute a heuristic baseline mix design for 1 m3 of concrete.

    Steps (simplified):
      1. estimate w/c from strength
      2. estimate water content from slump
      3. compute cement = water / (w/c)
      4. compute total volume of paste+water+aggregates = 1 m3 - air (2%)
      5. split aggregates into fine and coarse by fine_to_total ratio
    Returns dict of masses (kg/m3) and unit CO2/cost etc.
    """
    air_voids = 0.02  # 2% air
    wcr = estimate_wcr_from_strength(fc_target)
    water = estimate_water_content_from_slump(slump_target)
    cement = water / wcr

    # compute volumes (m3) of cement, water
    vol_cement = cement / RHO['cement']
    vol_water = water / RHO['water']

    # remaining volume for aggregates
    remaining_vol = 1.0 - air_voids - vol_cement - vol_water
    if remaining_vol <= 0:
        # fallback to safe values
        remaining_vol = 0.5

    vol_fine = remaining_vol * fine_to_total
    vol_coarse = remaining_vol * (1.0 - fine_to_total)

    fine_mass = vol_fine * RHO['fine_agg']
    coarse_mass = vol_coarse * RHO['coarse_agg']

    mix = {
        'cement_kg': round(cement, 1),
        'water_kg': round(water, 1),
        'fine_agg_kg': round(fine_mass, 1),
        'coarse_agg_kg': round(coarse_mass, 1),
        'air_percent': air_voids * 100.0,
        'wcr': round(wcr, 3),
        'estimated_baseline_strength': fc_target,  # assume calibrated to target for baseline
    }

    # environmental and cost metrics
    co2 = (mix['cement_kg'] * CO2_FACTORS['cement'] +
           mix['water_kg'] * CO2_FACTORS['water'] +
           mix['fine_agg_kg'] * CO2_FACTORS['fine_agg'] +
           mix['coarse_agg_kg'] * CO2_FACTORS['coarse_agg'])

    cost = (mix['cement_kg'] * COST_FACTORS['cement'] +
            mix['water_kg'] * COST_FACTORS['water'] +
            mix['fine_agg_kg'] * COST_FACTORS['fine_agg'] +
            mix['coarse_agg_kg'] * COST_FACTORS['coarse_agg'])

    mix['co2_kg_per_m3'] = round(co2, 2)
    mix['cost_unit_per_m3'] = round(cost, 2)
    return mix

# ----------------------------- Optimization search -----------------------------

def search_sustainable_mix(baseline_mix, fc_target, slump_target, tolerance_strength=1.5, tolerance_slump=10):
    """Grid search candidate mixes with SCM types/ratios and recycled aggregate replacements.
    For each candidate compute predicted strength and slump using surrogate models and
    compute CO2 & cost. Return top candidates that meet the tolerances and maximize CO2 reduction.
    """
    candidates = []
    # candidate parameters
    scm_types = ['None', 'Fly Ash', 'GGBS (Slag)']
    scm_pcts = list(range(0, 51, 5))  # 0% to 50% replacement of cement
    ra_pcts = list(range(0, 101, 10))  # 0% to 100% replacement of natural coarse agg by RA

    base_strength = fc_target  # assume baseline meets target
    base_slump = slump_target

    for scm in scm_types:
        for scm_pct in scm_pcts:
            for ra_pct in ra_pcts:
                # build candidate mix
                cement_kg = baseline_mix['cement_kg'] * (1.0 - scm_pct / 100.0)
                if scm == 'None':
                    scm_kg = 0.0
                elif scm == 'Fly Ash':
                    scm_kg = baseline_mix['cement_kg'] * scm_pct / 100.0
                    # treat fly ash density approximated via RHO
                elif scm == 'GGBS (Slag)':
                    scm_kg = baseline_mix['cement_kg'] * scm_pct / 100.0
                else:
                    scm_kg = 0.0

                # recycled aggregate replaces part of coarse aggregate mass
                coarse_mass = baseline_mix['coarse_agg_kg']
                ra_mass = coarse_mass * ra_pct / 100.0
                nat_coarse_mass = coarse_mass - ra_mass

                # predict properties using surrogate models
                strength_factor = predict_strength_modifier(scm_pct, scm, ra_pct)
                pred_strength = base_strength * strength_factor

                slump_factor = predict_slump_modifier(scm_pct, scm, ra_pct)
                pred_slump = base_slump * slump_factor

                # compute CO2 & cost for candidate
                # choose CO2 factor for SCM
                if scm == 'Fly Ash':
                    scm_co2_factor = CO2_FACTORS['fly_ash']
                    scm_cost_factor = COST_FACTORS['fly_ash']
                elif scm == 'GGBS (Slag)':
                    scm_co2_factor = CO2_FACTORS['ggbs']
                    scm_cost_factor = COST_FACTORS['ggbs']
                else:
                    scm_co2_factor = 0.0
                    scm_cost_factor = 0.0

                co2 = (cement_kg * CO2_FACTORS['cement'] +
                       scm_kg * scm_co2_factor +
                       baseline_mix['water_kg'] * CO2_FACTORS['water'] +
                       baseline_mix['fine_agg_kg'] * CO2_FACTORS['fine_agg'] +
                       nat_coarse_mass * CO2_FACTORS['coarse_agg'] +
                       ra_mass * CO2_FACTORS['coarse_agg'])

                cost = (cement_kg * COST_FACTORS['cement'] +
                        scm_kg * scm_cost_factor +
                        baseline_mix['water_kg'] * COST_FACTORS['water'] +
                        baseline_mix['fine_agg_kg'] * COST_FACTORS['fine_agg'] +
                        nat_coarse_mass * COST_FACTORS['coarse_agg'] +
                        ra_mass * COST_FACTORS['coarse_agg'])

                co2_reduction_pct = 100.0 * (baseline_mix['co2_kg_per_m3'] - co2) / baseline_mix['co2_kg_per_m3']
                cost_reduction_pct = 100.0 * (baseline_mix['cost_unit_per_m3'] - cost) / baseline_mix['cost_unit_per_m3']

                candidate = {
                    'scm': scm,
                    'scm_pct': scm_pct,
                    'ra_pct': ra_pct,
                    'pred_strength': round(pred_strength, 2),
                    'pred_slump': round(pred_slump, 1),
                    'cement_kg': round(cement_kg, 1),
                    'scm_kg': round(scm_kg, 1),
                    'nat_coarse_kg': round(nat_coarse_mass, 1),
                    'ra_kg': round(ra_mass, 1),
                    'co2_kg_per_m3': round(co2, 2),
                    'cost_unit_per_m3': round(cost, 2),
                    'co2_reduction_pct': round(co2_reduction_pct, 2),
                    'cost_reduction_pct': round(cost_reduction_pct, 2),
                }

                # check tolerances
                if (abs(pred_strength - fc_target) <= tolerance_strength) and (abs(pred_slump - slump_target) <= tolerance_slump):
                    candidates.append(candidate)

    # sort candidates by descending CO2 reduction then cost reduction
    candidates_sorted = sorted(candidates, key=lambda x: (x['co2_reduction_pct'], x['cost_reduction_pct']), reverse=True)
    return candidates_sorted

# ----------------------------- Streamlit UI -----------------------------

st.title("Concrete Mix Designer & Sustainability Optimizer 🏗️🌱")
st.markdown("""
This app creates a baseline mix design for **1 m³** of concrete based on the required compressive strength and slump, then offers an **Optimization Option** to search for more sustainable mixes using SCMs and recycled aggregates.

> ⚠️ **Important**: The calculations use simplified heuristics for demonstration. For accurate, production-ready designs you must calibrate and validate models against laboratory data or use national mix design standards (ACI, EN, BS) and local material properties.
""")

col1, col2 = st.columns([1, 1])
with col1:
    fc = st.selectbox("Select required compressive strength (MPa)", options=[i for i in range(20, 61, 5)], index=0)
with col2:
    slump = st.selectbox("Select required slump (mm)", options=[i for i in range(25, 151, 5)], index=0)

if st.button("Design Mix ▶️"):
    with st.spinner('Designing baseline mix...'):
        baseline = baseline_mix_design(fc, slump)

    st.subheader("Baseline Mix for 1 m³ 🧱")

    df = pd.DataFrame([{
        'Cement (kg)': baseline['cement_kg'],
        'Water (kg)': baseline['water_kg'],
        'Fine aggregate (kg)': baseline['fine_agg_kg'],
        'Coarse aggregate (kg)': baseline['coarse_agg_kg'],
        'Air (%)': baseline['air_percent'],
        'w/c ratio': baseline['wcr'],
        'Estimated CO2 (kg/m³)': baseline['co2_kg_per_m3'],
        'Estimated Cost (unit/m³)': baseline['cost_unit_per_m3'],
    }])

    st.table(df)

    st.caption("This baseline is generated with simplified engineering heuristics — calibrate before use.")

    # Optimization button
    if st.button("Optimization Option (make concrete more sustainable) 🌿"):
        with st.spinner('Searching sustainable candidates...'):
            candidates = search_sustainable_mix(baseline, fc, slump)

        if len(candidates) == 0:
            st.warning("No candidate found within tolerance. Try increasing tolerance or accept small deviation from target properties.")
        else:
            st.success(f"Found {len(candidates)} candidate(s). Showing top 10 by CO2 reduction.")
            top = candidates[:10]
            dfc = pd.DataFrame(top)
            # present compact view
            display_cols = ['scm','scm_pct','ra_pct','pred_strength','pred_slump','cement_kg','scm_kg','ra_kg','co2_kg_per_m3','co2_reduction_pct','cost_reduction_pct']
            st.dataframe(dfc[display_cols].rename(columns={
                'scm':'SCM Type','scm_pct':'SCM %','ra_pct':'RA %','pred_strength':'Pred Strength (MPa)',
                'pred_slump':'Pred Slump (mm)','cement_kg':'Cement (kg)','scm_kg':'SCM (kg)','ra_kg':'RA (kg)',
                'co2_kg_per_m3':'CO2 (kg/m³)','co2_reduction_pct':'CO2 Red. (%)','cost_reduction_pct':'Cost Red. (%)'
            }))

            st.markdown("---")
            st.subheader("Selected top candidate 🏆")
            best = top[0]
            st.metric("CO2 reduction", f"{best['co2_reduction_pct']}%")
            st.metric("Cost reduction", f"{best['cost_reduction_pct']}%")

            st.write("**Final sustainable mix (per 1 m³)**")
            st.write(f"SCM: {best['scm']} ({best['scm_pct']}% of cement replaced)")
            st.write(f"Recycled coarse aggregate: {best['ra_pct']}% of coarse aggregate replaced ({best['ra_kg']} kg)")
            st.write(f"Predicted compressive strength: {best['pred_strength']} MPa")
            st.write(f"Predicted slump: {best['pred_slump']} mm")
            st.write(f"Cement: {best['cement_kg']} kg | SCM: {best['scm_kg']} kg")
            st.write(f"Coarse NAT: {best['nat_coarse_kg']} kg | Coarse RA: {best['ra_kg']} kg")
            st.write(f"Estimated CO2: {best['co2_kg_per_m3']} kg/m³ ({best['co2_reduction_pct']}% reduction)")
            st.write(f"Estimated cost: {best['cost_unit_per_m3']} unit/m³ ({best['cost_reduction_pct']}% reduction)")

            st.info("Remember: lab verification of workability and strength is mandatory before construction use.")

# Footer / help
st.markdown("---")
with st.expander("How this optimization works (short)"):
    st.write("""
    • The app generates a simple baseline mix using an absolute-volume-like heuristic.
    • The optimization performs a grid search over SCM types & replacement ratios and recycled aggregate replacements.
    • Predicted strength/slump use simple surrogate functions (see code). Candidates meeting tolerances are ranked by CO2 reduction.

    For production use:
    1. Replace surrogate models with calibrated regression/ML models trained on your lab data.
    2. Use local material unit weights, CO2 emission factors and costs.
    3. Add checks for durability, bleeding, segregation, alkali-aggregate reactivity, and acceptance tests.
    """)

st.markdown("Made with ❤️ — replace surrogate models with lab-calibrated models before using for real designs.")
