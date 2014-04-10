from app import config, context
from app.constants import Constants as C
from flask import Flask, render_template, request, abort, redirect, jsonify, session, g, url_for, flash, current_app


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


def import_data(query, doc_types=None, max_results=999999999):
    if doc_types is None:
        doc_types = [config.ES_PAIRS]
    DELTA = 5000
    START = 0
    if max_results < DELTA:
        DELTA = max_results

    while True:

        if START >= max_results:
            break
        query['from'] = START
        query['size'] = DELTA

        results = context.es.search(index=config.ES_INDEX, doc_type=config.ES_PAIRS, body=query)['hits']
        search_results = results['hits']
        if results['total'] < max_results:
            max_results = results['total']

        for result in search_results:
            yield result

        START += DELTA
        if max_results - START <= DELTA and max_results != START:
            DELTA = max_results - START


def create_data_for_bulk(action, data, id_field, doc_type=config.ES_PAIRS):
    """
    Arranges the python iterable in the format needed for bulk elastic search operations.
    :param action:
    :param data:
    :param id_field:
    :return:

    See `ES's bulk API`_ for more detail.

    .. _`ES's bulk API`:
        http://www.elasticsearch.org/guide/reference/api/bulk.html
    """
    body_bits = []

    if not data:
        raise ValueError('No documents provided for bulk indexing!')

    for doc in data:
        action_dict = {action: {'_index': config.ES_INDEX, '_type': doc_type}}

        if doc.get(id_field) is not None:
            action_dict[action]['_id'] = doc[id_field]

        body_bits.append(json.dumps(action_dict))
        body_bits.append(json.dumps({'doc': doc}) if action == 'update' else json.dumps(doc))

    # Need the trailing newline.
    return '\n'.join(body_bits) + '\n'


def check_valid_user(user_email):
    return context.es.exists(index=config.ES_INDEX, doc_type=config.ES_USERS, id=user_email)


def get_user(user_email):
    return context.es.get(index=config.ES_INDEX, doc_type=config.ES_USERS, id=user_email)['_source']


def create_user(user_email, name):
    body = {
        U.EMAIL: user_email,
        U.NAME: name,
        U.CORRECT_DECISION_COUNT: 0,
        U.DECISION_COUNT: 0,
        U.FREEZE_ACCOUNT: False,
    }
    context.es.index(index=config.ES_INDEX, doc_type=config.ES_USERS, body=body, id=user_email)
    current_app.logger.info("Created user {}".format(user_email))


def get_total_user_decisions_count(user_email, decision=None):
    query = {
        "filter": {
            "and": [
                {
                    "term": {"email": user_email}
                }
            ]
        },
        "size": 0
    }
    if type(decision) is bool:
        query['filter']['and'].append({"term": {"correct_decision": decision}})
    if decision and type(decision) is str:
        query['filter']['and'].append({"term": {"decision": decision}})

    return context.es.search(index=config.ES_INDEX, doc_type=config.ES_USER_DECISIONS, body=query)['hits']['total']


def get_users_stats(decision=None):
    query = {
        "query": {
            "match_all": {}
        },
        "facets": {
            "leader_board_facet": {
                "terms": {
                    "field": UD.EMAIL,
                    "all_terms": True,
                    "size": 9999
                }
            }
        }
    }
    if type(decision) is bool:
        query['facets']['leader_board_facet']['facet_filter'] = {"term": {"correct_decision": decision}}

    return context.es.search(index=config.ES_INDEX, doc_type=config.ES_USER_DECISIONS, body=query, size=0)['facets'][
        'leader_board_facet']['terms']


def get_most_attempted():
    return [(stat['term'], stat['count']) for stat in get_users_stats()]


def get_most_correct():
    return [(stat['term'], stat['count']) for stat in get_users_stats(decision=True)]


def get_most_wrong():
    return [(stat['term'], stat['count']) for stat in get_users_stats(decision=False)]


def get_admin_board():
    leaders = {}
    for user, count in get_most_correct():
        leaders[user] = {"points": count, "most_correct": count}
    for user, count in get_most_wrong():
        if user not in leaders:
            leaders[user] = {"points": 0}
        leaders[user]['points'] -= count
        leaders[user]['most_wrong'] = count
    for user, count in get_most_attempted():
        if user not in leaders:
            leaders[user] = {}
        leaders[user]['most_attempted'] = count
    return leaders


def get_leader_board():
    leaders = {}
    for user, count in get_most_correct():
        leaders[user] = count
    for user, count in get_most_wrong():
        leaders[user] -= count

    sorted_x = sorted(leaders.iteritems(), key=operator.itemgetter(1), reverse=True)
    return sorted_x


def freeze_account(user_email, freeze=True):
    body = {
        "script": "ctx._source.{} += {}".format(U.FREEZE_ACCOUNT, freeze)
    }
    context.es.index(index=config.ES_INDEX, doc_type=config.ES_USERS, body=body, id=user_email)


def get_doc_by_titles(title_1, title_2, fields=[P.PID]):
    """returns a document pair using the titles."""
    title_hash_1 = get_hash(title_1)
    title_hash_2 = get_hash(title_2)
    query = {
        "filter": {
            "or": [
                {"term": {P.TH1: title_hash_1}},
                {"term": {P.TH2: title_hash_2}}
            ]
        },
        "fields": fields
    }
    return context.es.search(index=config.ES_INDEX, doc_type=config.ES_PAIRS, body=query)['hits']


def get_all_pairs_having_title(title=None, title_hash=None, fields=[P.PID], size=999999):
    if not title_hash and title:
        title_hash = get_hash(title)
    query = {
        "filter": {
            "or": [
                {"term": {P.TH1: title_hash}},
                {"term": {P.TH2: title_hash}}
            ]
        },
        "fields": fields,
        "size": size
    }
    return context.es.search(index=config.ES_INDEX, doc_type=config.ES_PAIRS, body=query)['hits']


def get_attempted_titles(user_email, fields=[P.PID, P.T1, P.T2, P.DECISIONS, P.FINAL_DECISION]):
    query = {
        "filter": {"term": {'users': user_email}},
        "fields": fields,
        "size": 100

    }

    results = context.es.search(index=config.ES_INDEX, doc_type=config.ES_PAIRS, body=query)['hits']

    return [result['fields'] for result in results['hits']]


def get_titles(user, size=1, fields=[P.PID, P.T1, P.T2]):
    query = {
        "filter": {
            "not": {
                "or": [
                    {"term": {P.SKIP: [user]}},
                    {"term": {P.USERS: [user]}},
                    {"term": {P.AVAILABLE_FOR_SELECTION: 'false'}}
                ]
            }

        },
        "sort": [{P.PRIORITY: {"order": "asc"}}]
    }
    context.es.indices.refresh()
    results = context.es.search(index=config.ES_INDEX, doc_type=config.ES_PAIRS, body=query, size=size)['hits']

    return results['hits'][0]['_source'] if len(results['hits']) > 0 else {}


def get_completed_titles_with_decision(decision=None, size=999999999):
    query = {
        "filter": {
            "and": [
                {"term": {"available_for_selection": "false"}}
            ]
        }
    }
    if decision is not None:
        query["filter"]["and"].append({"term": {"final_decision": decision}})

    results = context.es.search(index=config.ES_INDEX, doc_type=config.ES_PAIRS, body=query, size=size)['hits']

    return results


def get_final_decision(pair_id):
    document = context.es.get(index=config.ES_INDEX, doc_type=config.ES_PAIRS, id=pair_id,
                              fields=[P.USERS, P.DECISIONS])
    return document['fields'][P.DECISION]


def _create_decision(pair_id, decision, email, ip="127.0.0.1"):
    return {UD.DECISION: decision, UD.PAIR_ID: pair_id, UD.EMAIL: email, UD.CREATED_AT: datetime.utcnow().isoformat(),
            UD.IP_ADDRESS: ip}


def _mark_as_dupe(title_2):
    """
    Mark a title as dupe and make all other pairs containing that title not available for selection.
    :param title_2:
    :return:
    """
    result = get_all_pairs_having_title(title_2)

    docs = [hit['fields'] for hit in result['hits']] if result['total'] > 0 else []

    for doc in docs:
        doc['available_for_selection'] = False
    current_app.logger.info("Invalidating %s pairs %s" % (len(docs), [doc['pair_id'] for doc in docs]))
    body = create_data_for_bulk(action='update', data=docs, id_field=P.PID)

    context.es.bulk(body=body, index=config.ES_INDEX, doc_type=config.ES_PAIRS, refresh=True)


def _mark_pair_unavailable(pair_id, decision, decisions):
    body = {
        "script": 'ctx._source.{} = false; ctx._source.{}="{}"'.format(P.AVAILABLE_FOR_SELECTION, P.FINAL_DECISION,
                                                                       decision)
    }
    context.es.update(index=config.ES_INDEX, doc_type=config.ES_PAIRS, id=pair_id, body=body, refresh=True)
    current_app.logger.info("{} is unavailable".format(pair_id))
    # body = [{dec['email']:True} if dec['label'] == decision  else {dec['email']:False } for dec in decisions]
    body = []
    for dec in decisions:
        if not dec['email'] == 'dummy':
            if dec['decision'] == decision:
                body.append({UD.CORRECT_DECISION: True, "_id": "{}:{}".format(pair_id, dec['email'])})
            else:
                body.append({UD.CORRECT_DECISION: False, "_id": "{}:{}".format(pair_id, dec['email'])})
    body = create_data_for_bulk(action='update', data=body, id_field="_id", doc_type=config.ES_USER_DECISIONS)
    context.es.bulk(body=body, index=config.ES_INDEX, doc_type=config.ES_USER_DECISIONS, refresh=True)


def _just_update(pair_id, dec, user):
    body = {
        "script": "ctx._source.decisions += decision_name; ctx._source.users += user_name",
        "params": {
            "decision_name": {"email": user, "decision": dec},
            "user_name": user
        },
        "upsert": {
            "decisions": 1,
            "users": 1
        }
    }
    context.es.update(index=config.ES_INDEX, doc_type=config.ES_PAIRS, id=pair_id, body=body, refresh=True)

    body = _create_decision(pair_id=pair_id, decision=dec, email=user, ip=request.remote_addr)
    context.es.index(index=config.ES_INDEX, doc_type=config.ES_USER_DECISIONS, body=body,
                     id="{}:{}".format(pair_id, user))
    current_app.logger.info("{}:{}->{}".format(pair_id, user, dec))


def update_decision(decision, pair_id, user, title_1=None, title_2=None):
    _just_update(pair_id=pair_id, user=user, dec=decision.lower())

    document = context.es.get(index=config.ES_INDEX, doc_type=config.ES_PAIRS, id=pair_id,
                              fields=[P.USERS, P.DECISIONS, P.T2])

    if document and 'fields' in document and type(document['fields'][P.DECISIONS]) == type([]) and len(
            document['fields'][P.DECISIONS]) >= 2:

        counter = Counter([dec[P.DECISION] for dec in document['fields'][P.DECISIONS]])
        most_common_decision, most_common_decision_count = counter.most_common(1)[0]

        if most_common_decision_count >= 2:
            _mark_pair_unavailable(pair_id, most_common_decision, document['fields'][P.DECISIONS])

            if most_common_decision == D.DUPE:
                _mark_as_dupe(document['fields'][P.T2])


def skip_title(pair_id, user_email):
    body = {
        "script": "ctx._source.skip += user_name",
        "params": {
            "user_name": user_email
        }
    }
    context.es.update(index=config.ES_INDEX, doc_type=config.ES_PAIRS, id=pair_id, body=body, refresh=True)
    current_app.logger.info("{}:{}->{}".format(pair_id, user_email, "skip"))
