from flask import Flask, render_template, request, abort, redirect, jsonify, session, g, url_for, flash, current_app
from app import util, config, context
from app.constants import Pairs as P, Decisions as D, USER as U, USER_DECISIONS as UD, Constants as C
from app.metrics import metrics
from os.path import realpath, dirname, join
import logging
from logging.handlers import RotatingFileHandler
from time import sleep

app = Flask(__name__)

here = dirname(realpath(__file__))
app.config.from_object('app.config')


@app.route('/', methods=['GET', 'POST'])
@metrics
def index():
    return render_template('login.html')


@app.route('/past_decisions/<user_email>/<admin_token>')
@metrics
def past_decisions(user_email, admin_token):
    if session.get("email") != user_email and admin_token != config.ADMIN_TOKEN:
        flash('You can only view your own decisions')
        return redirect(url_for('make_decision'))

    user = util.get_user(user_email=user_email)
    if session.get("email") == user_email:
        set_session_data(session, user)

    results = util.get_attempted_titles(user_email=user_email)
    titles = [{"decision": decision['decision'], "title_1": title["title_1"], "title_2": title["title_2"],
               P.FINAL_DECISION: title[P.FINAL_DECISION] if P.FINAL_DECISION in title else ""} for title in results for
              decision in title['decisions'] if decision['email'] == session['email']]

    return render_template('past_decisions.html', titles=titles)


@app.route('/leader_board')
@metrics
def leader_board():
    email = session.get('email')

    leaders = util.get_leader_board()

    if email in leaders:
        session['total_points'] = leaders[email]
    return render_template('leader_board.html', leaders=leaders, type_of_board="Leader Board",
                           total_attempted=session['total_attempted'], email=email)


@app.route('/admin/' + config.ADMIN_TOKEN)
@metrics
def admin():
    stats = {}
    leaders = util.get_admin_board()
    headers = ["Email", "Points", "Correct", "Wrong", "Attempted"]
    inactive = util.get_completed_titles_with_decision(decision=None, size=0)['total']
    stats['unique'] = util.get_completed_titles_with_decision(decision=D.UNIQUE, size=0)['total']
    stats['dupe'] = util.get_completed_titles_with_decision(decision=D.DUPE, size=0)['total']
    stats['similar'] = util.get_completed_titles_with_decision(decision=D.SIMILAR, size=0)['total']
    stats['completed'] = stats['unique'] + stats['dupe'] + stats['similar']
    stats['deactivated'] = inactive - stats['completed']

    return render_template('admin.html', headers=headers, leaders=leaders,
                           total_attempted=session['total_attempted'], stats=stats, email=session.get('email'),
                           token=config.ADMIN_TOKEN)


@app.route('/get_titles', methods=['GET'])
@metrics
def get_titles():
    email = session.get('email')
    if not email:
        return redirect(url_for('login'))

    result = util.get_titles(email)
    result["total_attempted"] = session.get('total_attempted')
    result["total_correct"] = session.get('total_correct')
    result["total_wrong"] = session.get('total_wrong')
    # sleep(1)
    return jsonify(result=result)


@app.route('/make_decision', methods=['GET', 'POST'])
@metrics
def make_decision():

    email = session.get('email')
    if not email:
        return redirect(url_for('login'))
    if request.method == 'POST':

        decision = request.form['decision']
        pair_id = request.form['pair_id']

        context.stats_client.incr('{}.decision.{}'.format(config.METRICS_ENV, decision))

        if decision.lower() == "skip":
            util.skip_title(pair_id, email)
        else:
            util.update_decision(decision=decision, pair_id=pair_id, user=email)
            session['total_attempted'] += 1

        session['session_count'] += 1
        return get_titles()

    if session.get('session_count') % C.DECISION_REFRESH_RATE == 0:
        user = util.get_user(user_email=email)
        set_session_data(session, user)
    titles = util.get_titles(email)
    return render_template('make_decision.html', titles=titles, total_attempted=session['total_attempted'], email=email)


@app.route('/register', methods=['GET', 'POST'])
@metrics
def register():
    app.logger.info("Registration")
    error = None
    if request.method == 'POST':
        user_email = request.form['email'].lower()
        user_name = request.form['name']

        if not util.check_valid_user(user_email):
            util.create_user(user_email, user_name)
            flash('New User created and logged in.')

            set_session_data(session, {U.EMAIL: user_email, U.NAME: user_name})
            return redirect(url_for('make_decision'))
        else:

            error = "User account Already created"

    return render_template('register.html', error=error)


@app.route('/login', methods=['GET', 'POST'])
@metrics
def login():
    app.logger.info("in login")
    error = None
    if request.method == 'POST':

        user_email = request.form['email'].lower()

        if util.check_valid_user(user_email):
            user = util.get_user(user_email=user_email)
            set_session_data(session, user)

            if user[U.FREEZE_ACCOUNT]:
                flash('Account Frozen')
                return redirect(url_for('login'))

            flash('You were logged in')

            return redirect(url_for('make_decision'))
        else:

            flash('User not registered. Please register.')
            return redirect(url_for('register'))

    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('email', None)
    session.pop('admin', None)
    flash('You were logged out')
    return redirect(url_for('login'))


def set_session_data(session, user):
    session['logged_in'] = True
    session['email'] = user[U.EMAIL]
    session['name'] = user[U.NAME]
    session['total_attempted'] = util.get_total_user_decisions_count(user[U.EMAIL])
    session['total_correct'] = util.get_total_user_decisions_count(user[U.EMAIL], decision=True)
    session['total_wrong'] = util.get_total_user_decisions_count(user[U.EMAIL], decision=False)
    session['session_count'] = session.get("session_count") if session.get("session_count") else 0


def is_admin():
    if 'email' in session and session['email'] == config.ADMIN_EMAIL:
        session['admin'] = True
        return True
    return False


if __name__ == '__main__':
    print config.ES_INDEX,"\n\n"
    formatter = logging.Formatter(
        "[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s")
    handler = RotatingFileHandler('logs/decision_tool.log', maxBytes=10000000, backupCount=1)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)
    context.add_logger(app.logger)

    app.config.update(dict(SECRET_KEY=config.SECRET_KEY))
    app.run(debug=True, host='0.0.0.0')
