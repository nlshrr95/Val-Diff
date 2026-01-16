import streamlit as st
from rdflib import Graph, Namespace
from rdflib.namespace import RDF
from validator import validate_graph
from gis_visualization import display_gis_map
import requests
import pandas as pd
import os
import datetime
from version_comparator import DeltaChecker
from laces_engine import LacesEngine, LacesPDF
import uuid

# --- App Configuration ---
st.set_page_config(page_title="Laces Ontology Explorer", layout="wide")

# --- Global Data & Constants ---
QUERY_DIR = "queries"
# This dictionary defines the available queries the user can select.
QUERY_OPTIONS = {
    "General": {
        "file": os.path.join(QUERY_DIR, "objects.sparql"),
        "columns": ["conceptUri"]
    }
}


# --- UI Styling ---
st.markdown("""
    <style>
        header[data-testid="stHeader"] { visibility: hidden; height: 0%; }
        section.main { background-color: #fbfbfb; padding-top: 75px; }
        .custom-header {
            position: fixed; top: 0; left: 0; width: 100%;
            background-color: #000000; padding: 12px 24px;
            display: flex; justify-content: space-between; align-items: center;
            font-family: 'Segoe UI', sans-serif; border-bottom: 1px solid #e0e0e0;
            z-index: 9999;
        }
        .custom-header .logo-section { display: flex; align-items: center; }
        .custom-header .logo-section img { height: 24px; margin-right: 12px; }
        .custom-header .logo-text { font-size: 22px; font-weight: 600; color: #FFFFFF; }
        div.stButton > button:first-child {
            background-color: #6a0dad; color: white; border-radius: 8px;
            padding: 0.5em 1.5em; border: none; font-weight: 600;
        }
        div.stButton > button:first-child:hover { background-color: #5a059e; color: white; }
        .uploader-title, .section-title { font-weight: 700; font-size: 20px; margin-bottom: 10px; }
    </style>
    <div class="custom-header">
        <div class="logo-section">
            <img src="https://market.laceshub.com/_next/static/media/logo.2f9a686f.svg" alt="LACES Logo">
            <div class="logo-text">Ontology Explorer</div>
        </div>
    </div>
""", unsafe_allow_html=True)


# --- Main Application Tabs ---
validator_tab, compare_tab, docgen_tab = st.tabs(["Ontology Validator", "Changelog Generator", "Document Generator"])

# ==============================================================================
# --- VALIDATOR TAB ---
# ==============================================================================
with validator_tab:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="uploader-title">Upload Ontology file or SPARQL endpoint</div>', unsafe_allow_html=True)
        otl_file = st.file_uploader("Ontology in SHACL format", type=["ttl"], key="shacl_uploader")
        sparql_endpoint = st.text_input("SPARQL Endpoint URL", key="shacl_endpoint")

    with col2:
        st.markdown('<div class="uploader-title">Upload Project Data</div>', unsafe_allow_html=True)
        contractor_file = st.file_uploader("Data in RDF format", type=["ttl"], key="data_uploader")

    if st.button("Validate"):
        if (not otl_file and not sparql_endpoint) or not contractor_file:
            st.warning("Please provide either an Ontology file or a SPARQL endpoint, AND a Project Data file.")
        else:
            with st.spinner("Running validation..."):
                try:
                    shacl_graph = Graph()
                    if otl_file:
                        shacl_graph.parse(otl_file, format="turtle")
                    else:
                        query = "CONSTRUCT {?s ?p ?o} WHERE {?s ?p ?o}"
                        response = requests.post(
                            sparql_endpoint,
                            params={"query": query},
                            headers={"Accept": "text/turtle"}
                        )
                        response.raise_for_status()
                        shacl_graph.parse(data=response.text, format="turtle")

                    data_graph = Graph()
                    data_graph.parse(contractor_file, format="turtle")

                    conforms, results_graph, _ = validate_graph(data_graph, shacl_graph)

                    SH = Namespace("http://www.w3.org/ns/shacl#")
                    report_rows = [{
                        "Object": str(results_graph.value(r, SH.focusNode)),
                        "Error detected on": str(results_graph.value(r, SH.resultPath)),
                        "Message": str(results_graph.value(r, SH.resultMessage)),
                        "Constraint": str(results_graph.value(r, SH.sourceConstraintComponent)).split("#")[-1]
                    } for r in results_graph.subjects(RDF.type, SH.ValidationResult)]

                    violating_nodes = {row['Object'] for row in report_rows}

                    if conforms:
                        st.success("Project data conforms to the Ontology structure.")
                    else:
                        st.error("Project data does NOT conform to the Ontology structure. See details in the tabs below.")

                    map_view_tab, table_view_tab = st.tabs(["Map View", "Table View"])

                    with map_view_tab:
                        display_gis_map(data_graph, violating_nodes)

                    with table_view_tab:
                        if not conforms and report_rows:
                            st.write("Detailed Validation Report")
                            df = pd.DataFrame(report_rows)
                            st.dataframe(df, use_container_width=True)
                            csv = df.to_csv(index=False).encode("utf-8")
                            st.download_button("Download Report", csv, "validation_results.csv", "text/csv")
                        else:
                            st.info("The project data is valid. No errors to display.")
                except Exception as e:
                    st.error(f"An error occurred during validation: {e}")

# ==============================================================================
# --- VERSION COMPARER TAB ---
# ==============================================================================
with compare_tab:
    st.markdown('<div class="section-title">Version Comparison</div>', unsafe_allow_html=True)
    st.write("Provide the SPARQL endpoints for the two OTL versions you want to compare.")

    st.markdown('<h3>1. Provide Endpoints & Select Queries</h3>', unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    with c1:
        old_endpoint_url = st.text_input("Old Version SPARQL Endpoint")
    with c2:
        new_endpoint_url = st.text_input("New Version SPARQL Endpoint")

    selected_queries = st.multiselect(
        "Select the aspects (queries) to compare:",
        options=list(QUERY_OPTIONS.keys()),
        default=list(QUERY_OPTIONS.keys())
    )
    
    st.markdown('<hr style="margin-top:2em; margin-bottom:2em;">', unsafe_allow_html=True)
    st.markdown('<h3>2. Run Comparison</h3>', unsafe_allow_html=True)

    if st.button("Compare Versions"):
        if not old_endpoint_url or not new_endpoint_url:
            st.warning("Please provide both the old and new SPARQL endpoints.")
        elif not selected_queries:
            st.warning("Please select at least one query to run the comparison.")
        else:
            progress_bar = st.progress(0, text="Starting comparison...")
            def update_progress(fraction, text):
                progress_bar.progress(fraction, text=text)

            try:
                # Build a simplified config dictionary with only endpoint URLs
                config = {
                    "endpoints": {
                        "old": {"url": old_endpoint_url},
                        "new": {"url": new_endpoint_url}
                    },
                    "queries": {name: QUERY_OPTIONS[name] for name in selected_queries},
                    "summary": {"query": os.path.join(QUERY_DIR, "summary.sparql")}
                }
                
                checker = DeltaChecker(config)
                excel_data = checker.run(progress_callback=update_progress)
                
                if excel_data:
                    st.session_state['comparison_result'] = excel_data
                    filename = f"changelog_{datetime.date.today()}.xlsx"
                    st.session_state['report_filename'] = filename
                    progress_bar.empty()
                    st.success("Comparison finished! Your report is ready for download below.")
                else:
                    progress_bar.empty()
                    st.error("Comparison finished, but no data was generated. Check endpoint responses.")
            
            except Exception as e:
                progress_bar.empty()
                st.error("An error occurred during comparison:")
                st.code(str(e), language="")
            
    # Display download button if a report has been generated
    if 'comparison_result' in st.session_state and st.session_state['comparison_result']:
        st.download_button(
            label="Download Comparison Report",
            data=st.session_state['comparison_result'],
            file_name=st.session_state.get('report_filename', 'comparison_report.xlsx'),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ==============================================================================
# --- Docgen TAB ---
# ==============================================================================

if "md_report" not in st.session_state:
    st.session_state.md_report = ""

with docgen_tab:
    # --- EXPORT ACTIONS ---
    if st.session_state.md_report:
        st.subheader("Export Options")
        exp_c1, exp_c2, _ = st.columns([1, 1, 2])
        try:
            pdf = LacesPDF()
            pdf.add_page()
            pdf.add_markdown(st.session_state.md_report)
            pdf_out = pdf.output(dest='S').encode('latin-1', 'replace')
            exp_c1.download_button("Download PDF", pdf_out, "report.pdf", "application/pdf", use_container_width=True)
        except Exception as e:
            exp_c1.error(f"PDF Build Error: {e}")
        exp_c2.download_button("Download Markdown", st.session_state.md_report, "report.md", "text/markdown", use_container_width=True)
        st.divider()

    # --- SETTINGS SECTION ---
    st.subheader("Publication configuration")
    

    with st.expander("Configure Connection and Queries", expanded=True):
        sc1, sc2, sc3 = st.columns([2, 1, 1])
        endpoint = sc1.text_input("SPARQL Endpoint", value="https://hub.laces.tech/groups/repo/sparql")
        user = sc2.text_input("Username")
        pwd = sc3.text_input("Password", type="password")
        q_specs = st.text_area("Specifications Query", height=100, value="""PREFIX cm: <http://models.laces.tech/contractmanager/def/>\nPREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX sem:  <http://data.semmtech.com/sem/def/>\nSELECT DISTINCT ?uri ?name ?text\nWHERE {\n    ?uri a cm:IndividualSpecification ;\n        sem:name ?name ;\n        cm:isDescribedIn ?t .\n    ?t sem:value ?text .\n} ORDER BY ?name""")
        q_subs = st.text_area("Subjects Query", height=100, value="""PREFIX cm: <http://models.laces.tech/contractmanager/def/>\nPREFIX sem:  <http://data.semmtech.com/sem/def/>\nSELECT DISTINCT ?uri ?name ?type\nWHERE {\n    ?role sem:roleFor <{spec_uri}> .\n    ?uri cm:shallBeCompliantWith ?role ;\n        sem:classifiedAs ?classifier ;\n        sem:name ?name .\n    ?classifier sem:name ?type .\n} ORDER BY ?name""")
        q_plans = st.text_area("Plans Query", height=100, value="""PREFIX cm: <http://models.laces.tech/contractmanager/def/>\nPREFIX sem:  <http://data.semmtech.com/sem/def/>\nSELECT DISTINCT ?plan ?method ?phase\nWHERE {\n    ?role sem:roleFor <{spec_uri}> ;\n        cm:isVerifiedBy ?p .\n    ?p cm:isASpecializationOf ?m ;\n        sem:name ?plan ;\n        cm:occursWithin ?ph .\n    ?ph sem:name ?phase .\n    ?m sem:name ?method .\n}""")
        gen_btn = st.button("Generate Document", use_container_width=True)

    # --- GENERATION LOGIC ---
    if gen_btn:
        # Template queries remain consistent with frozen logic
        q_sub_template = """PREFIX cm: <http://models.laces.tech/contractmanager/def/>\nPREFIX sem:  <http://data.semmtech.com/sem/def/>\nSELECT DISTINCT ?uri ?name ?type\nWHERE {\n    ?role sem:roleFor <{spec_uri}> .\n    ?uri cm:shallBeCompliantWith ?role ;\n        sem:classifiedAs ?classifier ;\n        sem:name ?name .\n    ?classifier sem:name ?type .\n} ORDER BY ?name"""
        q_plan_template = """PREFIX cm: <http://models.laces.tech/contractmanager/def/>\nPREFIX sem:  <http://data.semmtech.com/sem/def/>\nSELECT DISTINCT ?plan ?method ?phase\nWHERE {\n    ?role sem:roleFor <{spec_uri}> ;\n        cm:isVerifiedBy ?p .\n    ?p cm:isASpecializationOf ?m ;\n        sem:name ?plan ;\n        cm:occursWithin ?ph .\n    ?ph sem:name ?phase .\n    ?m sem:name ?method .\n}"""

        with st.spinner("Generating Report..."):
            specs = LacesEngine.retrieve_objects(endpoint, user, pwd, q_specs, ("uri", "name", "text"))
            if specs:
                md = "# Requirements Report\n\n"
                for spec in specs:
                    subs = LacesEngine.retrieve_objects(endpoint, user, pwd, q_sub_template.replace("{spec_uri}", spec['uri']), ("uri", "name", "type"))
                    plans = LacesEngine.retrieve_objects(endpoint, user, pwd, q_plan_template.replace("{spec_uri}", spec['uri']), ("plan", "method", "phase"))
                    md += f"## {spec['name'].capitalize()}\n**Specification:** {spec['text']}\n\n"
                    if subs:
                        md += "| **Subject Name** | **Type** |\n|:---|:---|\n"
                        for s in subs: md += f"| {s['name']} | {s['type']} |\n"
                        md += "\n"
                    if plans:
                        md += "| **Phase** | **Method** | **Plan** |\n|:---|:---|:---|\n"
                        for p in plans: md += f"| {p['phase']} | {p['method']} | {p['plan']} |\n"
                        md += "\n"
                    md += "---\n\n"
                st.session_state.md_report = md
                st.rerun()

    # --- EDITOR & PREVIEW ---
    if st.session_state.md_report:
        st.divider()
        ed_col, pre_col = st.columns(2)
        with ed_col:
            st.subheader("Markdown Editor")
            st.session_state.md_report = st.text_area("Editor", value=st.session_state.md_report, height=600, label_visibility="collapsed")
        with pre_col:
            st.subheader("Rendered Preview")
            st.markdown(st.session_state.md_report)