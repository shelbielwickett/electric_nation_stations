import streamlit as st

st.set_page_config(page_title = 'Electric Nations EV Site Tool', page_icon='⚡', layout='wide')

# Header with logo
with open("images/logo_base64.txt") as f:
    logo_base64 = f.read()

col1, col2 = st.columns([6, 1])
with col1:
    st.title("⚡ Electric Nations EV Site Tool")
with col2:
    st.markdown(
        f"""
        <div style="text-align: right; padding-top: 0.5rem;">
            <div style = "display: inline-block; background-color: white; padding 10px; border-radius: 6px;">
                <img src="data:image/png;base64,{logo_base64}" width="120">
            </div>
        </div.
        """,
        unsafe_allow_html=True
    )

#st.title('⚡ Electric Nations EV Site Tool')
st.write('Welcome! Please use the sidebar to explore our different EV site tools:')

st.markdown("""
            - **Nearby EV Sites** → Finds charging stations near a chosen location.
            - **EV Sites on Tribal Land** → Finds charging stations located on Tribal Land.
            """)