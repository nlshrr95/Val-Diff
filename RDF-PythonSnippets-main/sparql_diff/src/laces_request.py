import os
import requests
import logging
from requests.auth import HTTPBasicAuth


def _env_default(key, default=""):
    return os.environ.get(key, default)


# TODO's
# [-] URL-save saving to Excel. --> Very difficult, do not see if we can supress this message.
# [x] Making modified changes more insightful (show new versus old)
# [x] Make it installable.
# [x] Make it possible to include un-checked columns
class LacesRequest():
    def __init__(self, config) -> None:
        url = config['url']
        if 'default_graph_uri' in config: 
            default_graphs = config['default_graph_uri'] 
        else: 
            default_graphs = []
        if 'named_graph_uri' in config: 
            named_graphs = config['named_graph_uri'] 
        else: 
            named_graphs = []

        parameters = {
            "default-graph-uri": default_graphs,
            "named-graph-uri": named_graphs
        }
        if 'username' in config and 'password' in config:
            username, password = config['username'] , config['password']
        else:
            username, password = _env_default("LDP_USERNAME"), _env_default("LDP_PASSWORD") 
            logging.info("Username from Environment used.")

        self._request = requests.Request(
            method="POST", url=url, params=parameters, headers={
                'Content-type': 'application/sparql-query',
                'Accept': 'text/csv',
            },
            auth=HTTPBasicAuth(username, password=password)
        )

    def send_request(self, query: str):
        return self.run_query(query)

    def run_query(self, query):
        self._request.data = query.encode("UTF-8")
        prepared = self._request.prepare()
        correct_url = self._request.url + '?'
        for graph in self._request.params['default-graph-uri']:
            correct_url += f'default-graph-uri={graph}&'
        for graph in self._request.params['named-graph-uri']:
            correct_url += f'named-graph-uri={graph}&'
        correct_url = correct_url[:-1]
        prepared.url = correct_url
        s = requests.Session()
        response = s.send(prepared)
        return response

