#!/usr/bin/env python
# encoding: utf-8
from __future__ import unicode_literals

from queries import SparqlQuery

class summary_of_events_with_eso(SparqlQuery):

    """ Get events containing a specified eso value
    """

    def __init__(self, *args, **kwargs):
        super(summary_of_events_with_eso, self).__init__(*args, **kwargs)
        self.query_title = 'Get events with a specific eso value'
        self.description = 'eso is an ontology which encompases various semantic framing schemes which give an indication as to the character of an event'
        self.url = 'summary_of_events_with_eso'
        self.world_cup_example = 'summary_of_events_with_eso?uris.0=eso:Renting'
        self.cars_example = 'summary_of_events_with_eso?uris.0=eso:Renting'
        self.ft_example = 'summary_of_events_with_eso?uris.0=eso:QuantityChange&datefilter=2010'
        self.query_template = ("""
SELECT ?event (COUNT(*) AS ?event_size) ?datetime (?filterfield as ?event_label)
WHERE {{
  {{
    SELECT DISTINCT ?event ?datetime ?filterfield
    WHERE {{
      ?event a sem:Event .
      ?event rdfs:label ?filterfield .
      ?event rdf:type {uri_0} .
      {uri_filter_block}
      ?event sem:hasTime ?t .
      ?t owltime:inDateTime ?d .
      {date_filter_block}
      ?d rdfs:label ?datetime .
    }}
    ORDER BY ?datetime
    OFFSET {offset}
    LIMIT {limit}
  }}
  ?event ?p ?o .
}}
GROUP BY ?event ?datetime ?filterfield
ORDER BY ?datetime
                               """)

        self.count_template = ("""
SELECT (COUNT(DISTINCT ?event) AS ?count)
WHERE {{
  ?event a sem:Event .
  ?event rdfs:label ?filterfield .
  ?event rdf:type {uri_0} .
  {uri_filter_block}
  ?event sem:hasTime ?t .
  ?t owltime:inDateTime ?d .
  {date_filter_block}
  ?d rdfs:label ?datetime .
}}
                               """)

        self.jinja_template = 'table.html'
        self.headers = ['event', 'datetime', 'event_label', 'event_size']

        self.required_parameters = ["uris"]
        self.optional_parameters = ["output", "datefilter", "filter"]
        self.number_of_uris_required = 1

        self.query = self._build_query()

    def _make_uri_filter_block(self):
        if self.filter != 'none':
            #self.filter_block = 'FILTER (contains(LCASE(str(?filterfield)), "{filter}")) .'.format(filter=self.filter)
            self.uri_filter_block = """ ?filterfield bif:contains "{filter}" .""".format(filter=self.filter)
        else:
            self.uri_filter_block = ''
