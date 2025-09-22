from typing import List, Tuple
import yaml
import pandas as pd
import numpy as np
import click
from io import StringIO
import time
from laces_request import LacesRequest


def convert_response(output) -> str:
    data = output.text
    data = data.replace('\n\n', '\n')
    data = data.replace('\r\n', '\n')
    return data


def compare_results(old_result: pd.DataFrame, new_result: pd.DataFrame, identifying_columns: List[str], ignored_columns: List[str] = None) -> Tuple[pd.DataFrame]:
    if ignored_columns is None:
        ignored_columns = []
    
    # Merge old and new results
    merged = pd.merge(old_result, new_result, on=identifying_columns, how='outer', indicator=True)
    
    # Get new items, old items, and potential changed items
    new_items = merged[merged['_merge'] == 'right_only']
    old_items = merged[merged['_merge'] == 'left_only']
    potential_changed = merged[merged['_merge'] == 'both']

    # Get names
    original_columns, old_columns, new_columns = get_changed_column_names(
        potential_changed.columns, identifying_columns)
    rename_changed, rename_old, rename_new, old_renamed_columns, new_renamed_columns = get_rename_dicts(
        original_columns, old_columns, new_columns)
    new_items = new_items[identifying_columns + new_columns]
    old_items = old_items[identifying_columns + old_columns]

    # Get all the Rows that are the same.
    old_full_index = pd.Index(old_result)
    new_full_index = pd.Index(new_result)
    same = new_result[new_full_index.isin(old_full_index)].drop_duplicates()
    
    # Filter modified columns   
    potential_changed.drop("_merge", axis=1, inplace=True)

    new_columns_to_check = [
        column_name for column_name in identifying_columns + new_columns if column_name[:-2] not in ignored_columns]
    old_columns_to_check = [
        column_name for column_name in identifying_columns + old_columns if column_name[:-2] not in ignored_columns]
    new_same = potential_changed[new_columns_to_check]
    old_same = potential_changed[old_columns_to_check]

    old_I = pd.Index(old_same)
    new_I = pd.Index(new_same)

    changed = potential_changed[~new_I.isin(old_I)].drop_duplicates()

    # Reorder columns with old next to new columns
    paired_columns = []
    for old_name, new_name in zip(old_columns, new_columns): 
        paired_columns.append(old_name)
        paired_columns.append(new_name)
    re_ordered_list = identifying_columns + paired_columns
    changed = changed[re_ordered_list]
    
    # Rename columns
    changed.rename(columns=rename_changed, inplace=True)
    new_items.rename(columns=rename_new, inplace=True)
    old_items.rename(columns=rename_old, inplace=True)

    # Add ChangeStatus
    changed = changed.assign(changeStatus="MODIFIED")

    # Style Modified items.
#    changed = style_differences(
#        changed, old_renamed_columns, new_renamed_columns)

    return new_items, old_items, changed, same, old_renamed_columns, new_renamed_columns, identifying_columns


def get_rename_dicts(original_columns, old_columns, new_columns):
    rename_changed_old = {old: f"{old[:-2]}_old" for old in old_columns}
    rename_changed_new = {new: f"{new[:-2]}_new" for new in new_columns}
    old_rename_dict = {old: original for old,
                       original in zip(old_columns, original_columns)}
    new_rename_dict = {new: original for new,
                       original in zip(new_columns, original_columns)}
    rename_changed = {**rename_changed_old, **rename_changed_new}
    old_renamed_columns = list(rename_changed_old.values())
    new_renamed_columns = list(rename_changed_new.values())
    return rename_changed, old_rename_dict, new_rename_dict, old_renamed_columns, new_renamed_columns

def get_changed_column_names(all_columns, identifying_columns):
    renamed_columns = [
        x for x in all_columns if x not in identifying_columns and x != "_merge"]
    original_columns = list(set([x[:-2] for x in renamed_columns]))
    new_columns = [x + "_y" for x in original_columns]
    old_columns = [x + "_x" for x in original_columns]
    return original_columns, old_columns, new_columns



def style_differences(modified_table: pd.DataFrame):
    # Reseting index to make it unique per row
    modified_table.reset_index(drop=True, inplace=True)

    # CSS styles for different statuses and changes
    styles = {
        "NEW": 'background-color: lightgreen;',
        "DELETED": 'background-color: lightcoral;',
        "UNCHANGED": 'background-color: lightgray;',
        "MODIFIED": 'background-color: lightyellow;',
        "MODIFIED_CELL": 'background-color: yellow;' 
    }


    # Function to style individual rows based on 'changeStatus' column
    def apply_row_style(row: pd.Series):
        # Base style for the whole row
        status = row['changeStatus']
        base_style = styles[status]
        row_styling = [base_style] * len(row)

        # If the row is 'MODIFIED', check for differences between _old and _new columns
        if status == "MODIFIED":
            for old_col in row.index:
                if old_col.endswith('_old'):
                    new_col = old_col.replace('_old', '_new')
                    both_empty = (pd.isna(row[old_col]) and pd.isna(row[new_col]))
                    if row[old_col] != row[new_col] and not both_empty:
                        row_styling[row.index.get_loc(new_col)] = styles['MODIFIED_CELL']
                        row_styling[row.index.get_loc(old_col)] = styles['MODIFIED_CELL']

        return row_styling

    # Apply the style function row-wise
    return modified_table.style.apply(apply_row_style, axis=1)

class DeltaChecker():
    def __init__(self, config_path, username, password, params=None) -> None:
        with open(config_path, "r") as f:
            self.config = yaml.full_load(f)
        self.results = {}
        if username is not None:
            self.config['username'] = username
        if password is not None: 
            self.config['password'] = password
        self.old_handler = LacesRequest(self.config['endpoints']['old'])
        self.new_handler = LacesRequest(self.config['endpoints']['new'])
        self.params = params
        try:
            self.params = self.config['parameters']
        except KeyError:
            pass


    def execute_query(self, query: str, old=True) -> pd.DataFrame:
        handler = self.old_handler if old else self.new_handler
        if self.params:
            for key in self.params: 
                replacement = self.params[key]['old'] if old else self.params[key]['new']
                query = query.replace(f"?{key}", replacement) # Key starts without a question mark but template does have one (to facilitate testing)

        raw = handler.send_request(query)
        if raw.status_code != 200: 
            print("Status code is not 200, but it is:", raw.status_code)
        str_raw = convert_response(raw)
        return pd.read_csv(StringIO(str_raw))

    def delta_query(self, config_query) -> Tuple[pd.DataFrame]:
        query_path = config_query['file']
        with open(query_path, "r") as f:
            query = f.read()
        print("Start Querying")
        old_result = self.execute_query(query, True)
        print(f"Executed {query_path} on the old version")
        new_result = self.execute_query(query, False)
        print(f"Executed {query_path} on the new version")
        
        # If any query returns empty, something is wrong. 
        if old_result.empty or new_result.empty: 
            print("One or both of your queries did not have any result. This is (presumably) not what you intended. Please check your configuration. ")
            raise Exception("EMPTY RESULT ERROR")            

        identifying_columns = config_query['columns']
        if 'ignored_columns' in config_query:
            ignored_columns = config_query['ignored_columns']
        else:
            ignored_columns = []

        return compare_results(old_result, new_result, identifying_columns, ignored_columns)

    def save_results_action(self) -> None: 
        if "dated_output" in self.config: 
            today = time.localtime()

            date_string = f"{today.tm_year}{today.tm_mon : 03d}{today.tm_mday : 03d}"
            path = f"{self.config['output_path'][:-5]}_{date_string}.xlsx"
        else: 
            path = self.config['output_path']
        with pd.ExcelWriter(path) as writer:
            for key, value in self.results.items():
                
                custom_index = True if key == "summary" else False
                custom_header = False if key == "summary" else True
                value.to_excel(writer, sheet_name=key, index=custom_index, header=custom_header)

    def save_results(self) -> None:
        if not self.results:
            return
        try:
            self.save_results_action()
        except PermissionError:
            print("PERMISSION DENIED! Most likely, you have the output file open. Please close the file")
            input("Press Enter to continue...")
            self.save_results_action() # If it fails again, it is on you. You can deal with the Python Error in that case. 

    def generate_summarypage(self) -> pd.DataFrame: 
        with open(self.config['summary']['query'], 'r') as f: 
            query = f.read()
        results_old = self.execute_query(query, old=True)
        results_new = self.execute_query(query, old=False) 
        print(f"Executed the summary queries")

        results = pd.concat([results_old, results_new])
        results.insert(0, "Aspect", ["Old version", "New version"]) 
        # --> A fancy way to add column names on the first row (since we transpose on the next line) 
        # Pandas doesn't let you use any easy way to add rows like that, so this is actually one of the easiest ways. 

        transposed = results.transpose()
        return transposed

    
    def run(self) -> None:
        print(self.config)
        if "summary" in self.config: # By doing this first, we use an undocumented functionality that this ends up as the first tab (as intended) 
            self.results["summary"] = self.generate_summarypage()

        for query, query_config in self.config['queries'].items():
            try:
                new, deleted, modified, same, old_renamed_columns, new_renamed_columns, identifying_columns = self.delta_query(query_config)
            except Exception as e: 
                print(e)
                print(f"An error occured while comparing the \"{query}\" query. Stopping early...")
                break # By breaking, but printing the error, it will try to save the existing results.  
            
            # Chaning column names to have the same names as "modified" 
            for col in new.columns:
                col_name = col + "_new"
                if col_name in new_renamed_columns:
                    new.rename(columns={col:col_name}, inplace=True)

            for col in deleted.columns:
                col_name = col + "_old"
                if col_name in old_renamed_columns:
                    deleted.rename(columns={col:col_name}, inplace=True)

            if self.config.get('include_unchanged') in (None, True):
                for col in same.columns:
                    col_name = col + "_old"
                    if col_name in old_renamed_columns:
                        same.rename(columns={col:col_name}, inplace=True)
            else:
                same = pd.DataFrame()

            # Merging 4 dataframes together
            combined = pd.concat([
                new.assign(changeStatus="NEW"),
                deleted.assign(changeStatus="DELETED"),
                same.assign(changeStatus="UNCHANGED"),
                modified
            ]).drop_duplicates()

            # Reordring the columns of combined dataframe
            paired_columns = []
            for old_name, new_name in zip(old_renamed_columns, new_renamed_columns):
                paired_columns.append(old_name)
                paired_columns.append(new_name)
            re_ordered_list = identifying_columns + paired_columns
            re_ordered_list.append("changeStatus")
            combined = combined[re_ordered_list]

            # Style the dataframe based on changes
            combined = style_differences(combined)

            self.results[query] = combined
        self.save_results()

@click.command()
@click.option('--username', help="The username to use when connecting to LDP")
@click.option('--password', help="The password to use when connecting to LDP")
def start(username, password):
    delta_checker = DeltaChecker("./config.yml", username, password)
    delta_checker.run()


if __name__ == "__main__":
    start()