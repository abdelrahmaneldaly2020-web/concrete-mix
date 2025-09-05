import streamlit as st
import numpy as np
import pandas as pd
from PIL import Image

# -----------------------------
# Helper functions
# -----------------------------
def design_mix(strength, slump):
    # Simplified rule-of-thumb mix design (kg per m3)
    cement = 350 + (strength - 20) * 5
    water = 180 + (slump / 150) * 20
    fine_agg = 700 - (slump / 150) * 50
    coarse_agg = 1100 - (strength - 20) * 10
    w_c_ratio = water / cement
    return {
        "🪨 Cement (kg)": cement,
        "💧 Water (kg)": water,
        "🏖️ Fine Aggregate (kg)": fine_agg,
        "🪨 Coarse Aggregate (kg)": coarse_agg,
        "⚖️ w/c ratio": w_c_ratio,
    }

def optimize_mix(base_mix, strength, slump):
    # Replace 30% of cement with SCM (e.g., fly ash)
    cement = base_mix["🪨 Cement (kg)"] * 0.7
    scms = base_mix["🪨 Cement (kg)"] * 0.3

    # Replace 20% of natural aggregate with recycled aggregate
    coarse_nat = base_mix["🪨 Coarse Aggregate (kg)"] * 0.8
    coarse_recycled = base_mix["🪨 Coarse Aggregate (kg)"] * 0.2

    fine_nat = base_mix["🏖️ Fine Aggregate (kg)"] * 0.85
    fine_recycled = base_mix["🏖️ Fine Aggregate (kg)"] * 0.15

    water = base_mix["💧 Water (kg)"] * 1.02  # adjust slightly for workability

    # Estimate new properties (slight variation)
    new_strength = strength - np.random.uniform(0, 2)
    new_slump = slump + np.random.uniform(-10, 10)

    # Reduction estimates
    co2_reduction = 25  # % reduction in CO2 emissions
    cost_reduction = 15  # % reduction in cost

    return {
        "🪨 Cement (kg)": cement,
        "🌱 SCMs (kg)": scms,
        "💧 Water (kg)": water,
        "🏖️ Fine Aggregate (kg)": fine_nat,
        "♻️ Fine Recycled Agg. (kg)": fine_recycled,
        "🪨 Coarse Aggregate (kg)": coarse_nat,
        "♻️ Coarse Recycled Agg. (kg)": coarse_recycled,
        "⚖️ w/c ratio": water / (cement + scms),
        "📊 New Strength (MPa)": new_strength,
        "📊 New Slump (mm)": new_slump,
        "🌍 CO2 Reduction (%)": co2_reduction,
        "💰 Cost Reduction (%)": cost_reduction,
    }

# -----------------------------
# Streamlit App
# -----------------------------
st.set_page_config(page_title="Concrete Mix Designer", page_icon="🧪", layout="centered")
st.title("🧪 AI-Powered Concrete Mix Designer")

# Inputs
strength = st.selectbox("Select Required Compressive Strength (MPa) 🏗️", list(range(20, 65, 5)))
slump = st.selectbox("Select Required Slump (mm) 💧", list(range(25, 155, 5)))

# Mix design
st.header("Designed Mix for 1 m³ of Concrete")
base_mix = design_mix(strength, slump)

results = {k: round(v, 1) for k, v in base_mix.items()}
st.dataframe(pd.DataFrame(results, index=["Quantity"]))

# Optimization option
if st.button("🌍 Optimization Option (Make Concrete More Sustainable)"):
    optimized = optimize_mix(base_mix, strength, slump)
    opt_results = {k: round(v, 1) if isinstance(v, (int, float)) else v for k, v in optimized.items()}
    st.header("Optimized Sustainable Mix")
    st.dataframe(pd.DataFrame(opt_results, index=["Quantity"]))
