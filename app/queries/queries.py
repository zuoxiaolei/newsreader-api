#!/usr/bin/env python
# encoding: utf-8
from __future__ import unicode_literals

import os
import json

from collections import namedtuple
import logging
import requests
import requests_cache

import time


requests_cache.install_cache('requests_cache', expire_after=172800)

SPARQL_URL = 'https://knowledgestore.fbk.eu/nwr/cars-hackathon/sparql'
CRUD_URL = 'https://knowledgestore.fbk.eu/nwr/worldcup-hackathon/{action}'

class QueryException(Exception):
    pass

def convert_raw_json_to_clean(SPARQL_json):
    clean_json = []
    # This handles the describe_uri query
    if "results" not in SPARQL_json.keys():
        return SPARQL_json

    for entry in SPARQL_json['results']['bindings']:
        line = {}
        for key in entry.keys():
            line[key] = entry[key]['value']
        clean_json.append(line)
    return clean_json


class SparqlQuery(object):

    """ Represents a general SPARQL query for the KnowledgeStore. """

    def __init__(self, offset=0, limit=100, uris=None, output='html',
                 datefilter=None, callback=None, id=None,
                 filter=None, **kwargs):

        self.prefix_dict = {
                "dbo": "http://dbpedia.org/ontology/",
                "dbpedia": "http://dbpedia.org/resource/",
                "dct": "http://purl.org/dc/terms/",
                "framenet": "http://www.newsreader-project.eu/framenet/",
                "gaf": "http://groundedannotationframework.org/files/2014/01/",
                "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                "sem": "http://semanticweb.cs.vu.nl/2009/11/sem/"
        }

        self._make_prefix_block()
        
        self.allowed_parameters_block = """
# All allowed parameters:
# output: {output}, offset: {offset}, limit: {limit}, 
# uri.0: {uri_0}, uri.1: {uri_1}
# filter_block: {filter_block}, date_filter_block: {date_filter_block}
# uri_filter_block: {uri_filter_block}
                                        """

        self.offset = offset
        self.limit = limit
        self.query_time = None
        self.count_time = None
        self.filter = str(filter).lower()
        self.datefilter = str(datefilter)
        self.date_filter_block = None
        self.filter_block = None
        self.uri_filter_block = None
        self.original_uris = uris
        self.uris = []

        self._process_input_uris(uris)
        self._make_date_filter_block()
        self._make_filter_block()
        self._make_uri_filter_block()

        self.query_title = None
        self.description = ""
        self.query_template = None
        self.query = None
        self.json_result = None
        self.clean_json = None
        self.output = output
        self.callback = callback
        self.headers = []
        self.result_is_tabular = True
        self.jinja_template = "default.html"

        self.required_parameters = []
        self.optional_parameters = ["output", "offset", "limit"]
        self.number_of_uris_required = 0

        

    def _make_prefix_block(self):
        prefixes = []
        for k,v in self.prefix_dict.iteritems():
            prefixes.append("PREFIX {k}: <{v}>".format(k=k, v=v))
        self.prefix_block = "\n".join(prefixes)

    def _process_input_uris(self, uris):
        if uris is None:
            self.uris = [None, None]
        else:
            # SPARQL queries require URIs wrapped in <,> unless they have
            # PREFIXES
            self.uris = []
            for item in uris:
                if "http" in item.decode('UTF-8'):
                    self.uris.append('<' + item.decode('UTF-8') + '>')
                else:
                    self.uris.append(self.expand_prefix(item))
            if len(self.uris) == 1:
                self.uris.append(None)
            #self.uris = ['<' + item + '>' for item in uris if "http" in item]

    def expand_prefix(self,item):
        # This catches the documentation {uri_0} and {uri_1}
        if item.startswith('{'):
            return item
        parts = item.decode('UTF-8').split(':')
        assert len(parts) == 2
        prefix = parts[0]
        postfix = parts[1]
        try:
            expanded_prefix =self.prefix_dict[prefix]
        except KeyError:
            pass
        expanded_item = '<' + expanded_prefix + postfix + '>'
        return expanded_item

    def _make_date_filter_block(self):
        if self.datefilter != 'None':
            dateparts = self.datefilter.split('-')
            if len(dateparts) >= 1:
                self.date_filter_block = '?d owltime:year "{0}"^^xsd:int . '.format(dateparts[0])
            if len(dateparts) >= 2:
                self.date_filter_block += '?d owltime:month "{0}"^^xsd:int . '.format(dateparts[1])
            if len(dateparts) == 3:
                self.date_filter_block += '?d owltime:day "{0}"^^xsd:int . '.format(dateparts[2])
        else:
            self.date_filter_block = ''
    
    def _make_filter_block(self):
        if self.filter != 'none':
            #self.filter_block = 'FILTER (contains(LCASE(str(?filterfield)), "{filter}")) .'.format(filter=self.filter)
            self.filter_block = '?filterfield bif:contains "{filter}" .'.format(filter=self.filter)
        else:
            self.filter_block = ''    

    def _make_uri_filter_block(self):
        if self.filter != 'none':
            #self.filter_block = 'FILTER (contains(LCASE(str(?filterfield)), "{filter}")) .'.format(filter=self.filter)
            self.uri_filter_block = """ ?filterfield rdfs:label ?_label . ?_label bif:contains "{filter}" .""".format(filter=self.filter)
        else:
            self.uri_filter_block = '' 

    def _check_parameters(self):
        if self.original_uris is None:
            len_uris = 0
        else:
            len_uris =len(self.original_uris)

        if len_uris < self.number_of_uris_required:
            message = "{0} required, {1} supplied".format(
                self.number_of_uris_required, len_uris)
            raise QueryException({"error":"Insufficient_uris_supplied: {0}".format(message)})

    def _build_query(self):
        """ Returns a query string. """
        self._check_parameters()

        full_query = ("#NewsReader Simple API Query: " + self.url + "\n" +
                      self.prefix_block + 
                      self.allowed_parameters_block + 
                      self.query_template)
        query = full_query.format(offset=self.offset,
                                  limit=self.limit,
                                  output=self.output,
                                  filter_block=self.filter_block,
                                  date_filter_block=self.date_filter_block,
                                  uri_filter_block=self.uri_filter_block,
                                  uri_0=self.uris[0],
                                  uri_1=self.uris[1]
                                  )
        return query

    def _build_count_query(self):
        """ Returns a count query string. """
        full_query = ("#NewsReader Simple API Counting Query: " + self.url + "\n" +
                          self.prefix_block + 
                          self.allowed_parameters_block + 
                          self.count_template)
        return full_query.format(offset=self.offset,
                                 limit=self.limit,
                                 output=self.output,
                                 filter_block=self.filter_block,
                                 date_filter_block=self.date_filter_block,
                                 uri_filter_block=self.uri_filter_block,
                                 uri_0=self.uris[0],
                                 uri_1=self.uris[1])

    def submit_query(self,
                     username=os.environ['NEWSREADER_USERNAME'],
                     password=os.environ['NEWSREADER_PASSWORD'],
                     endpoint_url=SPARQL_URL):
        """ Submit query to endpoint; return result. """
        payload = {'query': self.query}
        logging.debug("\n\n**New query**")
        logging.debug(self.query)
        if self.offset >= 10000:
            raise QueryException("OFFSET exceeds 10000, add filter or datefilter to narrow results")
            
        t0 = time.time()
        try:
            response = requests.get(endpoint_url, auth=(username, password),
                                    params=payload)
        except Exception as e:
            print "Query raised an exception"
            print type(e)
            t1 = time.time()
            total = t1-t0
            self.query_time = '{0:.2f}'.format(total)
            print "Time to return from query: {0:.2f} seconds".format(total)
            raise QueryException("Query raised an exception: {0}".format(type(e).__name__))
        else:
            t1 = time.time()
            total = t1-t0
            self.query_time = '{0:.2f}'.format(total)
            print "Time to return from query: {0:.2f} seconds".format(total)
            print "Response code: {0}".format(response.status_code)
            print "From cache: {0}".format(response.from_cache)

            if response and (response.status_code == requests.codes.ok):
                self.json_result = json.loads(response.content)
                self.clean_json = convert_raw_json_to_clean(self.json_result)
                if len(self.clean_json)==0:
                    raise QueryException("Result empty, possibly as a result of paging beyond results")    
            else:
                raise QueryException("Response code not OK: {0}".format(response.status_code))
        

    def get_total_result_count(self):
        """ Returns result count for query. """
        count_query = CountQuery(self._build_count_query())
        count = count_query.get_count()
        self.count_time = count_query.query_time
        return count

    def parse_query_results(self):
        # TODO: nicely parsed needs defining; may depend on query
        """ Returns nicely parsed result of query. """
        QueryResult = namedtuple('QueryResult', ' '.join(self.headers))
        # TODO: consider yielding results instead
        results = []
        for result in self.json_result['results']['bindings']:
            values = []
            for header in self.headers:
                values.append(result.get(header, {}).get('value'))
            next_entry = QueryResult._make(values)
            results.append(next_entry)
        return results


class CountQuery(SparqlQuery):

    """
    Represents a general count SPARQL query for the KnowledgeStore.

    Uses the count_template in a SPARQL query to create appropriate CountQuery.
    """
    # TODO: is *args, **kwargs really needed here?

    def __init__(self, count_query, *args, **kwargs):
        super(CountQuery, self).__init__(*args, **kwargs)
        self.query_title = 'Count query'
        self.query_template = count_query
        self.query = self._build_query()

    def _build_query(self):
        """ Returns a query string. """
        return self.query_template

    # TODO: Should get_count() be the more general parse_query_results()?
    def get_count(self):
        """ Parses and returns result from a count query. """
        try:
            self.submit_query()
        except Exception as e:
            raise QueryException("Count query failed with exception: {0}".format(type(e).__name__))
        
        if self.json_result['results']['bindings'] == []:
            return 0
        else:
            return int(self.json_result['results']['bindings'][0]['count']['value'])

class CRUDQuery(SparqlQuery):

    """
    Represents a general query to the CRUD endpoint for the KnowledgeStore.
    # https://knowledgestore.fbk.eu/nwr/worldcup-hackathon/{action}?id=http://news.bbc.co.uk/sport2/hi/football/gossip_and_transfers/5137822.stm 
    action = resources, mentions or files
    """
    # TODO: is *args, **kwargs really needed here?

    def __init__(self, offset=0, limit=100, uris=None, output='json',
                 datefilter=None, callback=None, id=None,
                 filter=None, **kwargs):
        super(CRUDQuery, self).__init__(**kwargs)
        self.query_title = 'CRUD query'
        self.query_template = "{uri_0}"
        self.original_uris = uris
        self.output = output
        self.callback = callback

        self._process_input_uris(uris)
        self.query = self._build_query()

    def _build_query(self):
        """ Returns a query string. """
        return self.query_template.format(uri_0=self.uris[0])

    def _build_count_query(self):
        """ Returns a count query string. """
        return ""

    # TODO: Should get_count() be the more general parse_query_results()?
    def get_count(self):
        """ Parses and returns result from a count query. """
        return 0

    def submit_query(self, endpoint_url_stub=CRUD_URL):
        """ Submit query to endpoint; return result. """

        username = os.environ['NEWSREADER_USERNAME']
        password = os.environ['NEWSREADER_PASSWORD']
        payload = {'id': self.query}
        
        endpoint_url = endpoint_url_stub.format(action=self.action)
        print "\n\n**New CRUD query**"
        t0 = time.time()
        try:
            response = requests.get(endpoint_url, auth=(username, password),
                                    params=payload)
        except Exception as e:
            print "Query raised an exception"
            print type(e)
            t1 = time.time()
            total = t1-t0
            raise QueryException("Query raised an exception: {0}".format(type(e).__name__))
        else:
            t1 = time.time()
            total = t1-t0
            print "Time to return from query: {0:.2f} seconds".format(total)
            print "Response code: {0}".format(response.status_code)
            print "From cache: {0}".format(response.from_cache)

            #print response.content
            
            if response and (response.status_code == requests.codes.ok):
                self.json_result = json.loads(response.content)
                self.clean_json = convert_raw_json_to_clean(self.json_result)
            else:
                raise QueryException("Response code not OK: {0}".format(response.status_code))

    def _clean_resource_identifier(resource_identifier):
        """Ensure that the resource identifier starts with a <, ends with a > 
        and remove anything after a #"""
        parts = resource_identifier.split('#')
        core = parts[0]
        prefix = ''
        suffix = ''
        if core[0] != '<':
            prefix = '<'
        if core[-1] != '>':
            suffix = '>'
        return prefix + core + suffix
