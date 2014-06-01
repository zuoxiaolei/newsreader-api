#!/usr/bin/env python
# encoding: utf-8
from __future__ import unicode_literals
import queries

def make_documentation(root_url):
    function_list = {"description":["NewsReader Simple API: Endpoints available at this location",
                                    "",
                                    "Queries are of the form:",
                                    root_url + "{page/[n]/}query_name?param1=[string]&param2=[string]",
                                    "Where page is an option component with default /page/1",
                                    "",
                                    ""
                        ],
                     "parameters":["output = {json|html|csv}",
                                   "limit",
                                   "offset",
                                   "filter",
                                   "uris.[n]",
                                   "timefilter - YYYY, YYYY-MM or YYYY-MM-DD"],
                     "prefixes":["dbo - types of things - i.e. dbo:SoccerPlayer", 
                                 "dbpedia - instances of things - i.e. dbpedia:David_Beckham"], 
                     "queries":[]}

    query_long_list = dir(queries)
    reject_list = ['__all__', '__builtins__', '__doc__', '__file__', '__name__',
                   '__package__', '__path__', 'queries']

    for query in query_long_list:
        if query in reject_list:
            continue
        query_name = getattr(queries, query)
        query_object = query_name()
        function_list['queries'].append({
                                   "title": query_object.query_title,
                                   "url": query_object.url,
                                   "required_parameters":query_object.required_parameters,
                                   "optional_parameters":query_object.optional_parameters,
                                   "output_columns":query_object.headers,
                                   "example":root_url + '/' + query_object.example})

        print query_object.query_title
    return function_list