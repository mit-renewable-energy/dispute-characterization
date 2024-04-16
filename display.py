import streamlit as st
import pandas as pd
import json
import gspread
import dotenv
import os
import pandas as pd
from streamlit_js_eval import streamlit_js_eval

st.set_page_config(layout="wide")

df = pd.read_csv('sample_25.csv')

