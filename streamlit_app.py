import streamlit as st

st.set_page_config(page_title="تصميم الخلطة الخرسانية", layout="centered")

st.title("🧱 تطبيق تصميم الخلطة الخرسانية")

st.markdown("""
أدخل القيم التالية لحساب كميات المواد لكل 1 متر مكعب من الخرسانة.
""")

# مدخلات المستخدم
fc = st.number_input("مقاومة الضغط المطلوبة (MPa)", value=30)
w_c_ratio = st.number_input("نسبة الماء إلى الأسمنت", min_value=0.3, max_value=0.7, value=0.5)
fine_ratio = st.slider("نسبة الركام الناعم", min_value=0.3, max_value=0.6, value=0.4)

# ثوابت المواد
SG_cement = 3.15
SG_fine = 2.65
SG_coarse = 2.70
SG_water = 1.00

# حساب الكميات
cement_content = 400  # كجم/م3 كقيمة مبدئية
water_content = cement_content * w_c_ratio

volume_cement = cement_content / (SG_cement * 1000)
volume_water = water_content / (SG_water * 1000)
volume_aggregates = 1 - (volume_cement + volume_water)

coarse_ratio = 1 - fine_ratio
fine_agg_mass = volume_aggregates * fine_ratio * SG_fine * 1000
coarse_agg_mass = volume_aggregates * coarse_ratio * SG_coarse * 1000

# عرض النتائج
st.markdown("### 💡 نتائج الخلطة:")
st.success(f"""
- الأسمنت: {cement_content:.1f} كجم  
- الماء: {water_content:.1f} كجم  
- الرمل (الركام الناعم): {fine_agg_mass:.1f} كجم  
- الزلط (الركام الخشن): {coarse_agg_mass:.1f} كجم  
""")
