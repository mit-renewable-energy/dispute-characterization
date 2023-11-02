import streamlit as st
import pandas as pd
import json

st.set_page_config(layout="wide")

st.title("Dispute Characterization")

queries = pd.read_csv('query_updated.csv')


for i, q in queries.iterrows():
    with st.expander(q['query']):
        for j, result in enumerate(json.loads(q['result'])['organic']):
            f"""
            #### {result['title']}
            {result['display_link']}

            {result['description']}
            """

            st.checkbox("Is this relevant? (i.e. would you click this)", key=f"{i}_{j}")