import streamlit as st

st.set_page_config(page_title = 'Electric Nations EV Site Tool', page_icon='⚡', layout='wide')
st.title('⚡ Electric Nations EV Site Tool')
st.write('Welcome! Please use the sidebar to explore our different EV site tools:')

st.markdown("""
            - **Nearby EV Sites** → Finds charging stations near a chosen location.
            - **EV Sites on Tribal Land** → Finds charging stations located on Tribal Land.
            """)