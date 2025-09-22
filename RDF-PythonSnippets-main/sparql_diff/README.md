# RDF_diff 

This is a small python package to create a changelog that can be customized by Users. 

## Installation 

### From Code 

1. Clone the entire repository (`git clone git@gitlab.com:semmtech-company/python/RDF-PythonSnippets.git`)
2. Go to this folder (`RDF-PythonSnippets\sparql_diff`) with a Commandprompt
3. While you have a [virtual environment](https://docs.python.org/3/library/venv.html) enabled, install this package using `pip install .`

### From PIP 
1. While you have a [virtual environment](https://docs.python.org/3/library/venv.html) enabled, install this package using `pip install "git+https://gitlab.com/semmtech-company/python/RDF-PythonSnippets.git/#subdirectory=sparql_diff"` 

## Usage 
In the folder with your configuration file, run `sparql-diff --username YOUR_USERNAME --password YOUR_PASSWORD`. (Your username and password are for an `approved application`.) This configuration file needs to be called `config.yml`. Username and password can also be stored in a similar way as [https://gitlab.com/semmtech-company/semantics/stylesheets/stylesheet-composer]. i.e. these can be stored as environment variables (LDP_USERNAME, LDP_PASSWORD respectively). 
For an inspiration on the usage, see the [example configuration](Example_folder/config.yml). The configuration has the following items: 
1. `queries`: For each query the file and the columns need to be specified. Based on the columns, the script will see a difference between *modified* and *new/deleted.* If all fields in the specified columns is the same, but some other columns are different, than the entry is *modified*. If one of the specified columns is different, than the entry is recognized as *new* (Or deleted, if the entry is only in the old publication). (If, however, all columns are the same, than the entry is, well, the same). It is necessary that the combination of these columns is unique. If there are multiple records A_1, A_2, ... A_n for a given set of these *identifying columns*, the script will do comparisons between all of them. For example: if you have 3 *unchanged records* A1, A2 and A3 in both your datasets, the script will show 6 changed rows: A1 -> A2, A1 -> A3, A2 -> A1, etcetera. 
Since multiple queries are possible, you can have, for example, one query that checks changed objects, while another checks changed aspects.  
1. `endpoints`: For both the old and the new publication, the url needs to be specified. If the queries are more complicated (i.e. using additional graphs in either the named or default graphs), these can also be specified. If needed, you can supply an endpoint specific username and password. 
2. `output_path`: The name of the output file. 


## Technical working of the script
First, the script reads the configuration file `config.yml` that is stored in the same folder as where you run the script.
It retrieves the location of your query, the endpoints and the configuration for these items. For endpoints, this includes the default-graphs, named-graphs and authentication.  
Then, the script does the following step for each defined query: 
1. Send query to both end-points, and retrieve CSV output. 
2. Match rows based on the specified columns. It is important that the records are unique for a set of these columns. This happens with help of the `pandas` library. 
3. Collect new records (only in the new dataset), deleted records (only in the old dataset), and unchanged records in an Excel sheet (technically: `pd.DataFrame`)
4. Do extra post-processing on the modified records (where the identifying columns are the same, but some others are not, for example the description): 
   1. Show the old and new values next to each-other
   2. Color each value that is changed yellow (row-wise). 
5. Save all Excel-sheets in a single file `output.xlsx`. 

## Contributing 
Please let us know if you have any suggestions! 
