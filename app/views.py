#!/usr/bin/env python
# encoding: utf-8
from flask import render_template, request
from app import app


@app.route('/')
def index():
    """ Demo function. """
    return "Hello World!"


@app.route('/simple/query3')
def handle_offset_and_limit():
    """ Simple query string function. """
    offset = request.args.get('offset')
    limit = request.args.get('limit')
    return "offset {0}, limit {1}".format(offset, limit)
