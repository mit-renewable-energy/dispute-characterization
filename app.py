import streamlit as st
import pandas as pd
import json
import gspread
import dotenv
import os
import pandas as pd
from streamlit_js_eval import streamlit_js_eval


dotenv.load_dotenv()

@st.cache_resource
def get_gc():
    """Get gspread client"""
    with open("gcloud.json", "w") as f:
        f.write(os.getenv("GOOGLE_API_KEY"))
    gc = gspread.service_account(filename="gcloud.json")
    return gc

st.set_page_config(layout="wide")

gc = get_gc()
sh = gc.open_by_url("https://docs.google.com/spreadsheets/d/1NaitOeamRWgkJlj5JCBmyJwwImgC-o2qAeIvlg2w9eI/edit#gid=309366946")


db = pd.DataFrame(sh.sheet1.get_all_records())

st.info("""Here is some info you should keep in mind when scoring:

Anushree info goes here

""")

name = st.text_input("What is your name?")

active_row = db[(db['human'].isna()) | (db['human'] == '')].iloc[0]

st.info(f"These are results from the following search query:\n\n {active_row['query']}")

results = {

}

for j, result in enumerate(json.loads(active_row['result'])):
    f"""
    ====================================================================================================

    **{result['title'] if "title" in result else "No title available"}**
    {result['display_link'] if "display_link" in result else "No description available"}

    {result['description'] if "description" in result else "No description available"}
    """

    results[j] = st.checkbox("Is this relevant? (i.e. would you click this)", key=f"{j}")


if st.button("Submit Results", use_container_width=True):
    if type(name) == str and name != "":
        db.loc[active_row.name, 'human'] = json.dumps({"name": name, "submission": results})
        sh.sheet1.update([db.columns.values.tolist()] + db.values.tolist())
        streamlit_js_eval(js_expressions="parent.window.location.reload()")
    else:
        st.error("Please enter your name and submit again.")
