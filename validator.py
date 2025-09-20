from pyshacl import validate
from rdflib import Graph

def load_graph(file_path_or_str, format='turtle'):
    g = Graph()
    g.parse(file_path_or_str, format=format)
    return g

def validate_graph(data_graph, shacl_graph):
    conforms, results_graph, results_text = validate(
        data_graph=data_graph,
        shacl_graph=shacl_graph,
        inference='rdfs',
        abort_on_error=False,
        meta_shacl=True,
        advanced=True,
        debug=False
    )
    return conforms, results_graph, results_text