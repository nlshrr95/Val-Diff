# Design of Delta Checker

## Requirements 
1. User-defined queries 
2. Fire on two (sets of) publications 
3. See the differences clearly in Excel or similar
4. Single button press (after defining queries )
5. Able to recognize 'changed', 'deleted' and 'new'

## Design option 1: Completely in SPARQL
--> This Design is stopped. It can become too complicated for an end-user.

1. Logic is placed as much as possible in the query 
2. So queries need to be written something like the following
i.e.:
```SPARQL
    FROM <GRAPH_NEW>
    SELECT *_New WHERE
        {PROVIDED QUERY}
        # 
        FILTER NOT EXISTS
            GRAPH <Graph_OLD> 
                {Provided Query}
        
```
3. Still, python script to run all queries on a end-point and collect it in an Excel? 

In other words, this is pretty complicated, where-as the logic could be generalized and be hidden from the consultant. 

## Design option 2: Mostly in Python
1. Queries are created in a single folder 
2. Config file is stored as a YAML
   1. For each query: What are the identifying columns
   2. Endpoint
   3. Credentials 
3. Run Query on both endpoints
4. Check Additions, removals and differences
5. Save Raw and changes as an Excel File
6. Repeat for all queries
\