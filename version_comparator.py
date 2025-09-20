import os
import requests
import logging
import pandas as pd
from io import StringIO, BytesIO
from requests.auth import HTTPBasicAuth
import numpy as np

def _env_default(key, default=""):
    return os.environ.get(key, default)

class LacesRequest():
    def __init__(self, config) -> None:
        url = config.get('url')
        # Default and Named graphs are no longer passed in this simplified version
        default_graphs = config.get('default-graph-uri', [])
        named_graphs = config.get('named-graph-uri', [])

        parameters = {
            "default-graph-uri": default_graphs,
            "named-graph-uri": named_graphs
        }
        username = config.get('username')
        password = config.get('password')
        
        # This allows for backward compatibility if credentials are in the environment
        if not username or not password:
            username, password = _env_default("LDP_USERNAME"), _env_default("LDP_PASSWORD")
            if username:
                logging.info("Username/Password from Environment used.")

        self._request = requests.Request(
            method="POST", url=url, params=parameters, headers={
                'Content-type': 'application/sparql-query',
                'Accept': 'text/csv',
            },
            auth=HTTPBasicAuth(username, password) if username else None
        )

    def run_query(self, query):
        self._request.data = query.encode("UTF-8")
        prepared = self._request.prepare()
        
        param_str = []
        # This part will now typically find empty lists and not add params, which is correct
        for k, v in self._request.params.items():
            if isinstance(v, list):
                for item in v:
                    param_str.append(f"{k}={item}")
            elif v:
                 param_str.append(f"{k}={v}")
        
        correct_url = self._request.url
        if param_str:
            correct_url += '?' + '&'.join(param_str)
        
        prepared.url = correct_url
        
        s = requests.Session()
        return s.send(prepared)

def convert_response(output) -> str:
    return output.text.replace('\n\n', '\n').replace('\r\n', '\n')

def compare_results(old_result, new_result, identifying_columns, ignored_columns=None):
    if ignored_columns is None:
        ignored_columns = []
    
    for df, name in [(old_result, "old"), (new_result, "new")]:
        missing_cols = [col for col in identifying_columns if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Identifying columns {missing_cols} not found in {name} result.")

    merged = pd.merge(old_result, new_result, on=identifying_columns, how='outer', indicator=True, suffixes=('_old', '_new'))
    
    new_items = merged[merged['_merge'] == 'right_only']
    old_items = merged[merged['_merge'] == 'left_only']
    potential_changed = merged[merged['_merge'] == 'both']

    original_columns = sorted(list(set(c.replace('_old', '').replace('_new', '') for c in merged.columns if c.endswith(('_old', '_new')))))
    
    old_suffix_cols = [f"{c}_old" for c in original_columns]
    new_suffix_cols = [f"{c}_new" for c in original_columns]
    
    new_items = new_items[identifying_columns + new_suffix_cols]
    old_items = old_items[identifying_columns + old_suffix_cols]

    all_original_cols = identifying_columns + original_columns
    # Fill NA to ensure 'same' comparison is robust for missing values
    same = pd.merge(old_result.fillna('[NULL]'), new_result.fillna('[NULL]'), on=all_original_cols, how='inner').replace('[NULL]', np.nan)


    changed = pd.DataFrame()
    if not potential_changed.empty:
        # To find changed rows, we compare the non-identifying columns
        compare_cols_orig = [c for c in original_columns if c not in ignored_columns]
        
        # Create temporary dataframes for comparison
        df_old = potential_changed[identifying_columns + [f"{c}_old" for c in compare_cols_orig]].set_index(identifying_columns)
        df_new = potential_changed[identifying_columns + [f"{c}_new" for c in compare_cols_orig]].set_index(identifying_columns)

        # Rename columns to match for a direct comparison
        df_new.columns = df_old.columns

        # Use pandas' built-in comparison, which handles dtypes and NaNs gracefully
        # We fill NA values to ensure that two null values are considered equal
        is_different_mask = ~df_old.fillna('[NULL]').eq(df_new.fillna('[NULL]')).all(axis=1)
        
        changed_indices = is_different_mask[is_different_mask].index
        
        changed = potential_changed.set_index(identifying_columns).loc[changed_indices].reset_index()
        
    return new_items, old_items, changed, same, old_suffix_cols, new_suffix_cols, identifying_columns

def style_differences(df: pd.DataFrame):
    def apply_row_style(row):
        style = [''] * len(row)
        status_colors = {"NEW": 'background-color: #d4edda;', "DELETED": 'background-color: #f8d7da;', "MODIFIED": 'background-color: #fff3cd;', "UNCHANGED": ''}
        style = [status_colors.get(row.get('changeStatus', ''), '')] * len(row)

        if row.get('changeStatus') == 'MODIFIED':
            modified_cell_style = 'background-color: #fbe54e;'
            for new_col in [c for c in row.index if c.endswith('_new')]:
                old_col = new_col.replace('_new', '_old')
                if old_col in row.index:
                    old_val, new_val = row[old_col], row[new_col]
                    if str(old_val) != str(new_val) and not (pd.isna(old_val) and pd.isna(new_val)):
                        style[row.index.get_loc(new_col)] = modified_cell_style
                        style[row.index.get_loc(old_col)] = modified_cell_style
        return style
    return df.style.apply(apply_row_style, axis=1)

class DeltaChecker():
    def __init__(self, config_dict) -> None:
        self.config = config_dict
        self.results = {}
        # Parameters are no longer used in this simplified flow
        self.params = self.config.get('parameters', {})

    def execute_query(self, query: str, old=True) -> pd.DataFrame:
        endpoint_config = self.config['endpoints']['old'] if old else self.config['endpoints']['new']
        handler = LacesRequest(endpoint_config)

        # Since graph URIs are no longer provided, remove the FROM clauses
        # from the SPARQL queries to let them run on the endpoint's default graph.
        query = query.replace("FROM ?DEFAULT_URI", "")
        query = query.replace("FROM NAMED ?NAMED_URI", "")
        
        raw = handler.run_query(query)
        
        if raw.status_code != 200:
            error_message = f"SPARQL endpoint returned status {raw.status_code} for URL: {raw.url}. "
            try:
                error_message += f"\nResponse: {raw.text}"
            except Exception:
                 error_message += "\n(Could not read response text.)"
            raise requests.exceptions.HTTPError(error_message, response=raw)

        str_raw = convert_response(raw)
        return pd.read_csv(StringIO(str_raw)) if str_raw else pd.DataFrame()

    def delta_query(self, config_query):
        with open(config_query['file'], "r", encoding="utf-8") as f:
            query = f.read()
        old_result = self.execute_query(query, True)
        new_result = self.execute_query(query, False)
        if old_result.empty and new_result.empty:
            logging.warning(f"Both queries for {config_query['file']} returned empty results.")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), [], [], config_query['columns']
        return compare_results(old_result, new_result, config_query['columns'], config_query.get('ignored_columns', []))

    def generate_summarypage(self) -> pd.DataFrame:
        if "summary" in self.config and "query" in self.config["summary"]:
            try:
                with open(self.config['summary']['query'], 'r', encoding="utf-8") as f:
                    query = f.read()
                results_old = self.execute_query(query, old=True)
                results_new = self.execute_query(query, old=False)
                results = pd.concat([results_old, results_new])
                results.insert(0, "Aspect", ["Old version", "New version"])
                return results.transpose()
            except Exception as e:
                logging.warning(f"Could not generate summary page: {e}")
                return None
        return None

    def run(self, progress_callback=None):
        summary_df = self.generate_summarypage()
        if summary_df is not None:
            self.results["summary"] = summary_df
        
        queries_to_run = self.config['queries'].items()
        for i, (name, config) in enumerate(queries_to_run):
            if progress_callback: progress_callback(i / len(queries_to_run), f"Processing: {name}")
            try:
                new, deleted, modified, same, _, _, id_cols = self.delta_query(config)
                combined = pd.concat([new.assign(changeStatus="NEW"), deleted.assign(changeStatus="DELETED"), modified.assign(changeStatus="MODIFIED"), same.assign(changeStatus="UNCHANGED")], ignore_index=True)
                if not combined.empty:
                    paired_cols = []
                    orig_cols = sorted(list(set(c.replace('_old','').replace('_new','') for c in combined.columns if c.endswith(('_old', '_new')))))
                    for col in orig_cols:
                        if f"{col}_old" in combined.columns: paired_cols.append(f"{col}_old")
                        if f"{col}_new" in combined.columns: paired_cols.append(f"{col}_new")
                    final_cols = id_cols + paired_cols + ['changeStatus']
                    combined = combined.reindex(columns=final_cols).fillna('')
                self.results[name] = style_differences(combined)
            except Exception as e:
                logging.error(f"An error occurred while comparing the '{name}' query: {e}")
                if progress_callback: progress_callback(i / len(queries_to_run), f"Error on: {name}")
                self.results[name] = pd.DataFrame([{"Error": f"Could not process query: {e}"}]).style
        
        if progress_callback: progress_callback(1.0, "Comparison complete.")
        return self.save_to_memory()

    def save_to_memory(self):
        if not self.results: return None
        output_buffer = BytesIO()
        with pd.ExcelWriter(output_buffer, engine='xlsxwriter') as writer:
            for key, value in self.results.items():
                if isinstance(value, pd.io.formats.style.Styler):
                    value.to_excel(writer, sheet_name=key, index=False)
                else:
                    value.to_excel(writer, sheet_name=key, index=(key=="summary"), header=(key!="summary"))
        output_buffer.seek(0)
        return output_buffer

