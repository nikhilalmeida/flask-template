from app import config, context
from app.constants import Constants as C
from flask import Flask, render_template, request, abort, redirect, jsonify, session, g, url_for, flash, current_app
import unicodedata
import hashlib
import sys


tbl = dict.fromkeys(i for i in xrange(sys.maxunicode)
                    if unicodedata.category(unichr(i)).startswith('P'))


def get_hash(text):
    """
    strip input string of any punctuations, make it lowercase and
    return a sha1 hash of the stripped text.
    """
    if text:
        stripped = " ".join(unicode(text).translate(tbl).lower().split())
        return hashlib.sha1(stripped.encode('utf-8')).hexdigest()
