"""TravelMate server. Run: python add.py"""
import json
import secrets
from datetime import date
from pathlib import Path

from flask import Flask, flash, jsonify, redirect, render_template_string, request, session, url_for
from markupsafe import Markup, escape
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__, static_folder=".", static_url_path="")
app.secret_key = secrets.token_hex(32)
DATA = Path(__file__).with_name("travel_data.json")
MODES = ("Flight", "Train", "Car", "Bus", "Ship")

def read_data():
    return json.loads(DATA.read_text()) if DATA.exists() else {"users": []}

def write_data(data):
    DATA.write_text(json.dumps(data, indent=2))

def user():
    email = session.get("email")
    return next((u for u in read_data()["users"] if u["email"] == email), None)

def login_required():
    return user() or None

def trip_svg(trip):
    icons = {"Flight":"✈️", "Train":"🚆", "Car":"🚗", "Bus":"🚌", "Ship":"🚢"}
    legs = trip["legs"]
    places = [legs[0]["from"], *[leg["to"] for leg in legs]]
    width, padding = 560, 35
    step = (width - 70) / max(1, len(places) - 1)
    nodes = [(padding + i * step, 110 if i in (0, len(places)-1) else 62, name) for i, name in enumerate(places)]
    path = f"M {nodes[0][0]} {nodes[0][1]}" + "".join(f" Q {(nodes[i][0]+n[0])/2} {22 if i%2==0 else 145} {n[0]} {n[1]}" for i, n in enumerate(nodes[1:]))
    out = [f'<svg viewBox="0 0 560 160" aria-hidden="true"><path class="route-curve" d="{path}"/>']
    for i, (x, y, name) in enumerate(nodes):
        kind = "start" if i == 0 else "end" if i == len(nodes)-1 else "stop"
        out.append(f'<circle class="route-node {kind}" cx="{x}" cy="{y}" r="7"/><text class="route-label" x="{x}" y="{y-14 if y<80 else y+27}" text-anchor="middle">{escape(name)}</text>')
    for i, leg in enumerate(legs):
        x = (nodes[i][0] + nodes[i+1][0]) / 2
        y = (nodes[i][1] + nodes[i+1][1]) / 2 + (-25 if i % 2 == 0 else 24)
        out.append(f'<text class="route-icon" x="{x}" y="{y}" text-anchor="middle">{icons[leg["transport"]]}</text>')
    return Markup("".join(out) + "</svg>")

def make_trip(old=None):
    origin, destination = request.form["origin"].strip(), request.form["destination"].strip()
    start, end = request.form["start_date"], request.form["end_date"]
    status, route = request.form["status"], request.form["route"]
    budget = request.form.get("budget", "").strip()
    people = request.form.get("people", "").strip()
    interests = request.form.get("interests", "").strip()
    stops = [s.strip() for s in request.form.get("stops", "").replace(",", "\n").splitlines() if s.strip()]
    now = date.today().isoformat()
    if not origin or not destination or start > end: raise ValueError("Enter valid locations and dates.")
    if status == "upcoming" and start < now: raise ValueError("Upcoming trips cannot use past dates.")
    if status == "completed" and end > now: raise ValueError("Completed trips cannot use future dates.")
    if status == "upcoming":
        if not budget or not people or not interests:
            raise ValueError("Add your budget, number of people, and interests for an upcoming trip.")
        try:
            budget = float(budget)
            people = int(people)
        except ValueError:
            raise ValueError("Budget and number of people must be valid numbers.")
        if budget < 0 or people < 1:
            raise ValueError("Budget cannot be negative and at least one person must travel.")
    if route == "stops" and not stops: raise ValueError("Add at least one stop.")
    places = [origin, *stops, destination]
    modes = request.form.getlist("leg_transport") if route == "stops" else [request.form.get("transport", "Flight")]
    if any(mode not in MODES for mode in modes): raise ValueError("Invalid travel method.")
    return {"id": old["id"] if old else secrets.token_hex(6), "origin": origin, "destination": destination, "start_date": start, "end_date": end, "status": status, "route": route, "stops": stops, "budget": budget if status == "upcoming" else "", "people": people if status == "upcoming" else "", "interests": interests if status == "upcoming" else "", "legs": [{"from": places[i], "to": places[i+1], "transport": modes[i] if i < len(modes) else "Flight"} for i in range(len(places)-1)]}

def suggest_itinerary(trip):
    """Create a personalised, practical itinerary from a trip's saved preferences."""
    days = (date.fromisoformat(trip["end_date"]) - date.fromisoformat(trip["start_date"])).days + 1
    budget, people = float(trip["budget"]), int(trip["people"])
    interests = [item.strip() for item in trip["interests"].split(",") if item.strip()]
    themes = {
        "food": "Visit a well-reviewed local food market and choose a regional speciality.",
        "beach": "Spend the afternoon at a beach or waterfront, with time for a sunset walk.",
        "museum": "Book a museum or heritage-site visit and leave time to explore the surrounding area.",
        "history": "Take a guided heritage walk through the city's historic district.",
        "art": "Explore a local gallery, creative neighbourhood, or public-art trail.",
        "nature": "Plan a park, garden, or scenic day trip with a relaxed outdoor lunch.",
        "adventure": "Choose one active experience, such as a hike, bike tour, or water activity.",
        "shopping": "Browse a local market or shopping street and set a spending limit before you go.",
        "nightlife": "Keep the evening open for live music, a neighbourhood bar, or a cultural show.",
    }
    activities = [text for keyword, text in themes.items() if any(keyword in interest.lower() for interest in interests)]
    if not activities:
        activities = ["Explore a walkable neighbourhood, sample local food, and save time for an unplanned discovery."]
    plan = []
    for index in range(days):
        if index == 0:
            activity = "Arrive, check in, and take an easy orientation walk near your stay."
            title = "Arrival and neighbourhood discovery"
        elif index == days - 1:
            activity = "Enjoy a relaxed breakfast, revisit a favourite spot, and leave plenty of time for departure."
            title = "Easy finale and departure"
        else:
            activity = activities[(index - 1) % len(activities)]
            title = f"{interests[(index - 1) % len(interests)] if interests else 'Local'} day"
        plan.append({"day": index + 1, "title": title, "activity": activity})
    return {
        "days": plan,
        "trip_days": days,
        "budget": f"{budget:,.0f}",
        "per_person": f"{budget / people:,.0f}",
        "daily_budget": f"{budget / days:,.0f}",
        "people": people,
        "interests": ", ".join(interests),
    }

def trip_days(trip):
    return (date.fromisoformat(trip["end_date"]) - date.fromisoformat(trip["start_date"])).days + 1

def travel_budget(trips):
    total = 0.0
    for trip in trips:
        try:
            total += float(trip.get("budget") or 0)
        except (TypeError, ValueError):
            pass
    return total

@app.route("/", methods=["GET", "POST"])
def login():
    if user(): return redirect("/dashboard")
    if request.method == "POST":
        account = next((u for u in read_data()["users"] if u["email"] == request.form.get("email", "").lower()), None)
        if account and check_password_hash(account["password"], request.form.get("password", "")):
            session["email"] = account["email"]
            return redirect("/dashboard")
        flash("Invalid email or password.")
    return render_template_string(AUTH, register=False)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name, email, password = request.form.get("name", "").strip(), request.form.get("email", "").lower(), request.form.get("password", "")
        data = read_data()
        if not name or not email or len(password) < 6: flash("Enter a name, email, and password of at least 6 characters.")
        elif password != request.form.get("confirm_password"): flash("Passwords do not match.")
        elif any(u["email"] == email for u in data["users"]): flash("This email is already registered.")
        else:
            data["users"].append({"name": name, "email": email, "password": generate_password_hash(password), "trips": []})
            write_data(data); flash("Registration successful. Please log in.")
            return redirect("/")
    return render_template_string(AUTH, register=True)

@app.get("/dashboard")
def dashboard():
    account = login_required()
    if not account: return redirect("/")
    edit = next((t for t in account["trips"] if t["id"] == request.args.get("edit")), None)
    upcoming = [trip for trip in account["trips"] if trip["status"] == "upcoming"]
    view = request.args.get("view")
    if view not in ("new", "history", "upcoming"):
        view = "upcoming" if upcoming else "history"
    if edit: view = "new"
    return render_template_string(DASH, user=account, trips=account["trips"], upcoming=upcoming, edit=edit, view=view, svg=trip_svg, days=trip_days, estimated_budget=travel_budget(upcoming))

@app.post("/trip")
@app.post("/trip/<trip_id>")
def save_trip(trip_id=None):
    account = login_required()
    if not account: return redirect("/")
    data = read_data(); account = next(u for u in data["users"] if u["email"] == account["email"])
    old = next((t for t in account["trips"] if t["id"] == trip_id), None)
    try: trip = make_trip(old)
    except ValueError as error:
        flash(str(error)); return redirect(url_for("dashboard", edit=trip_id) if old else "/dashboard")
    if old: account["trips"][account["trips"].index(old)] = trip
    else: account["trips"].insert(0, trip)
    write_data(data); return redirect("/dashboard")

@app.get("/trip/<trip_id>/itinerary")
def itinerary(trip_id):
    account = login_required()
    if not account: return jsonify({"error": "Please log in to view an itinerary."}), 401
    trip = next((item for item in account["trips"] if item["id"] == trip_id), None)
    if not trip or trip["status"] != "upcoming": return jsonify({"error": "This upcoming trip was not found."}), 404
    if not trip.get("budget") or not trip.get("people") or not trip.get("interests"):
        return jsonify({"error": "Add budget, people, and interests to generate an itinerary."}), 400
    return jsonify(suggest_itinerary(trip))

@app.post("/trip/<trip_id>/delete")
def delete_trip(trip_id):
    account = login_required()
    if not account: return redirect("/")
    data = read_data(); account = next(u for u in data["users"] if u["email"] == account["email"])
    account["trips"] = [t for t in account["trips"] if t["id"] != trip_id]
    write_data(data); return redirect("/dashboard")

@app.get("/logout")
def logout():
    session.clear(); return redirect("/")

AUTH = """<!doctype html><link rel='stylesheet' href='/styles.css'><div class='auth-shell'><div class='auth-card'><div class='brand-wrap'><span class='brand-badge'>T</span><h1>TravelMate</h1></div><h2>{{ 'Create account' if register else 'Login' }}</h2>{% for m in get_flashed_messages() %}<p class='message'>{{m}}</p>{% endfor %}<form method='post' class='auth-form'>{% if register %}<label>Full name<input name='name' required></label>{% endif %}<label>Email<input name='email' type='email' required></label><label>Password<input name='password' type='password' required></label>{% if register %}<label>Confirm password<input name='confirm_password' type='password' required></label>{% endif %}<button class='primary-btn'>{{ 'Register' if register else 'Login' }}</button></form><p class='switch-link'>{% if register %}<a href='/'>Login</a>{% else %}<a href='/register'>Register</a>{% endif %}</p></div></div>"""

DASH = """<!doctype html><link rel='stylesheet' href='/styles.css'><body class='dashboard-body'><main class='dashboard-content'><header class='topbar'><div><p class='eyebrow'>Dashboard</p><h2>Welcome, {{user.name}}</h2></div><a class='secondary-btn' href='/logout'>Logout</a></header>{% for m in get_flashed_messages() %}<p class='message'>{{m}}</p>{% endfor %}<section class='stats-grid'><article class='stat-card accent-blue'><span>Total trips</span><strong>{{trips|length}}</strong></article><article class='stat-card accent-green'><span>Completed</span><strong>{{trips|selectattr('status','equalto','completed')|list|length}}</strong></article><article class='stat-card accent-orange'><span>Upcoming</span><strong>{{trips|selectattr('status','equalto','upcoming')|list|length}}</strong></article></section><section class='panel trip-form-panel'><h3>{{'Edit trip' if edit else 'Plan a new trip'}}</h3><form method='post' class='trip-form' action='{{"/trip/" + edit.id if edit else "/trip"}}'><label>Starting from<input id='origin' name='origin' value='{{edit.origin if edit else ""}}' required></label><label>Destination<input id='destination' name='destination' value='{{edit.destination if edit else ""}}' required></label><label>Start date<input id='startDate' name='start_date' type='date' value='{{edit.start_date if edit else ""}}' required></label><label>End date<input id='endDate' name='end_date' type='date' value='{{edit.end_date if edit else ""}}' required></label><label>Status<select id='status' name='status'><option value='upcoming' {%if not edit or edit.status=='upcoming'%}selected{%endif%}>Upcoming</option><option value='completed' {%if edit and edit.status=='completed'%}selected{%endif%}>Completed</option></select></label><label>Route<select id='route' name='route'><option value='direct' {%if not edit or edit.route=='direct'%}selected{%endif%}>Direct</option><option value='stops' {%if edit and edit.route=='stops'%}selected{%endif%}>Has stops</option></select></label><label id='transportField'>Travelling by<select name='transport'>{%for m in ['Flight','Train','Car','Bus','Ship']%}<option {%if edit and edit.legs[0].transport==m%}selected{%endif%}>{{m}}</option>{%endfor%}</select></label><label id='stopsField' hidden>Stops<textarea id='stops' name='stops'>{{edit.stops|join('\n') if edit else ''}}</textarea></label><div id='legMethods' class='trip-legs' hidden></div><button class='primary-btn small'>Save trip</button></form></section><section class='panel'><h3>Trip history</h3>{%for t in trips%}<div class='trip-item'><div class='trip-details'><strong>{{t.destination}}</strong><div class='route-visual'>{{svg(t)}}</div><small>{%for l in t.legs%}{{l.from}} → {{l.to}} ({{l.transport}}){%if not loop.last%} · {%endif%}{%endfor%}</small></div><div class='trip-actions'><a class='trip-action' href='/dashboard?edit={{t.id}}'>Edit</a><form method='post' action='/trip/{{t.id}}/delete'><button class='trip-action delete'>Delete</button></form></div></div>{%else%}<p class='empty-state'>No trips yet.</p>{%endfor%}</section></main><script src='/script.js'></script></body>"""

DASH = """{% macro trip_card(trip) -%}
<article class='trip-item'><div class='trip-details'><strong>{{ trip.destination }}</strong><div class='route-visual' role='img' aria-label='Trip route'>{{ svg(trip) }}</div><small>{% for leg in trip.legs %}{{ leg.from }} → {{ leg.to }} ({{ leg.transport }}){% if not loop.last %} · {% endif %}{% endfor %}</small><small>{{ trip.start_date }} to {{ trip.end_date }} · {{ trip.status }}</small>{% if trip.status == 'upcoming' and trip.budget %}<small class='trip-preferences'>Budget: {{ trip.budget }} · {{ trip.people }} {{ 'person' if trip.people|int == 1 else 'people' }} · Interests: {{ trip.interests }}</small><button class='trip-action itinerary-btn' type='button' data-itinerary='{{ trip.id }}'>Generate itinerary</button><div class='itinerary-result' id='itinerary-{{ trip.id }}' hidden aria-live='polite'></div>{% endif %}</div><div class='trip-actions'><a class='trip-action' href='/dashboard?edit={{ trip.id }}'>Edit</a><form method='post' action='/trip/{{ trip.id }}/delete'><button class='trip-action delete'>Delete</button></form></div></article>
{%- endmacro %}
<!doctype html>
<html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>TravelMate | Dashboard</title><link rel='stylesheet' href='/styles.css'></head>
<body class='dashboard-body'><div class='dashboard-shell'>
  <aside class='sidebar'><div class='brand-wrap sidebar-brand'><span class='brand-badge'>T</span><h1>TravelMate</h1></div>
    <nav class='nav-links'>
      <a href='/dashboard?view=upcoming' class='{% if view == "upcoming" %}active{% endif %}'>Upcoming trips</a>
      <a href='/dashboard?view=new' class='{% if view == "new" %}active{% endif %}'>Add new trip</a>
      <a href='/dashboard?view=history' class='{% if view == "history" %}active{% endif %}'>Trip history</a>
    </nav><a class='secondary-btn' href='/logout'>Logout</a>
  </aside>
  <main class='dashboard-content'><header class='topbar'><div><p class='eyebrow'>Dashboard</p><h2>Welcome, {{ user.name }}</h2></div></header>
  {% for message in get_flashed_messages() %}<p class='message'>{{ message }}</p>{% endfor %}
  <section class='stats-grid'><article class='stat-card accent-blue'><span>Total trips</span><strong>{{ trips|length }}</strong></article><article class='stat-card accent-green'><span>Completed</span><strong>{{ trips|selectattr('status','equalto','completed')|list|length }}</strong></article><article class='stat-card accent-orange'><span>Upcoming</span><strong>{{ upcoming|length }}</strong></article></section>
  {% if view == 'new' %}
  <section class='panel trip-form-panel'><div class='panel-header'><h3>{{ 'Edit trip' if edit else 'Add new trip' }}</h3>{% if edit %}<a href='/dashboard?view=history'>Cancel</a>{% endif %}</div>
    <form method='post' class='trip-form' action='{{ "/trip/" + edit.id if edit else "/trip" }}'>
      <label>Starting from<input id='origin' name='origin' value='{{ edit.origin if edit else "" }}' required></label><label>Destination<input id='destination' name='destination' value='{{ edit.destination if edit else "" }}' required></label>
      <label>Start date<input id='startDate' name='start_date' type='date' value='{{ edit.start_date if edit else "" }}' required></label><label>End date<input id='endDate' name='end_date' type='date' value='{{ edit.end_date if edit else "" }}' required></label>
      <label>Status<select id='status' name='status'><option value='upcoming' {% if not edit or edit.status == 'upcoming' %}selected{% endif %}>Upcoming</option><option value='completed' {% if edit and edit.status == 'completed' %}selected{% endif %}>Completed</option></select></label>
      <div id='upcomingFields' class='trip-preferences-fields'><label>Budget<input id='budget' name='budget' type='number' min='0' step='0.01' value='{{ edit.budget if edit else "" }}' placeholder='e.g. 50000'></label><label>Number of people<input id='people' name='people' type='number' min='1' step='1' value='{{ edit.people if edit else "" }}' placeholder='e.g. 2'></label><label class='full-width'>Interests<input id='interests' name='interests' value='{{ edit.interests if edit else "" }}' placeholder='e.g. food, beaches, museums'></label></div>
      <label>Route<select id='route' name='route'><option value='direct' {% if not edit or edit.route == 'direct' %}selected{% endif %}>Direct</option><option value='stops' {% if edit and edit.route == 'stops' %}selected{% endif %}>Has stops</option></select></label>
      <label id='transportField'>Travelling by<select name='transport'>{% for method in ['Flight','Train','Car','Bus','Ship'] %}<option {% if edit and edit.legs[0].transport == method %}selected{% endif %}>{{ method }}</option>{% endfor %}</select></label>
      <label id='stopsField' hidden>Stops<textarea id='stops' name='stops' rows='3' placeholder='One stop per line'>{{ edit.stops|join('\n') if edit else '' }}</textarea></label><div id='legMethods' class='trip-legs' hidden></div><button class='primary-btn small'>Save trip</button>
    </form>
  </section>
  {% elif view == 'upcoming' and upcoming %}
  <section class='panel'><div class='panel-header'><h3>Upcoming trips</h3><a href='/dashboard?view=new'>Add new trip</a></div><div class='trip-history-list'>{% for trip in upcoming %}{{ trip_card(trip) }}{% endfor %}</div></section>
  {% else %}
  <section class='panel'><div class='panel-header'><h3>Trip history</h3><a href='/dashboard?view=new'>Add new trip</a></div>{% if trips %}<div class='trip-history-list'>{% for trip in trips %}{{ trip_card(trip) }}{% endfor %}</div>{% else %}<p class='empty-state'>No upcoming trips yet. Add your first trip to start planning.</p>{% endif %}</section>
  {% endif %}
  </main></div><script src='/script.js'></script></body></html>
"""

DASH = """{% macro budget_row(label, amount, portion) -%}
<div class='budget-row'><span>{{ label }}</span><div class='budget-meter'><i style='--portion: {{ portion }}%'></i></div><strong>{{ '%.0f'|format(amount) }}</strong></div>
{%- endmacro %}
{% macro trip_card(trip) -%}
<article class='destination-card' data-trip-card>
  <div class='destination-image'><img src='https://loremflickr.com/1000/650/{{ trip.destination|urlencode }},travel/all' alt='Travel scene for {{ trip.destination }}'><span class='trip-status'>{{ trip.status }}</span></div>
  <div class='trip-summary'>
    <div><p class='overline'>Next adventure</p><h3>{{ trip.destination }}</h3><p class='trip-date'>{{ trip.start_date }} — {{ trip.end_date }} · {{ days(trip) }} days</p></div>
    <div class='trip-facts'><span><b>From</b>{{ trip.origin }}</span><span><b>Travelers</b>{{ trip.people }}</span><span><b>Budget</b>{{ '%.0f'|format(trip.budget|float) }}</span><span><b>Interests</b>{{ trip.interests }}</span></div>
    <div class='trip-actions-card'><button class='primary-btn small' type='button' data-itinerary='{{ trip.id }}'>View itinerary</button><a class='secondary-btn icon-btn' href='/dashboard?edit={{ trip.id }}'>Customize</a><a class='map-link edit-link' href='/dashboard?edit={{ trip.id }}'>Edit</a><form method='post' action='/trip/{{ trip.id }}/delete'><button class='text-danger' aria-label='Delete {{ trip.destination }}'>Delete</button></form></div>
  </div>
  <details class='map-panel'><summary>Route & interactive map</summary><div class='map-grid'><div><p><b>{{ trip.origin }}</b> to <b>{{ trip.destination }}</b></p><p class='muted'>{% for leg in trip.legs %}{{ leg.from }} → {{ leg.to }} by {{ leg.transport }}{% if not loop.last %} · {% endif %}{% endfor %}</p><a class='map-link' target='_blank' rel='noopener' href='https://www.google.com/maps/dir/?api=1&origin={{ trip.origin|urlencode }}&destination={{ trip.destination|urlencode }}'>Open directions ↗</a></div><iframe title='Map for {{ trip.destination }}' loading='lazy' src='https://www.google.com/maps?q={{ trip.destination|urlencode }}&output=embed'></iframe></div></details>
  <section class='itinerary-result itinerary-drawer' id='itinerary-{{ trip.id }}' hidden aria-live='polite'></section>
  <div class='trip-utility-grid'>
    <section class='utility-card budget-card'><div class='section-kicker'>Budget breakdown</div><h4>Estimated allocation</h4><p class='muted'>Based on your saved total budget of {{ '%.0f'|format(trip.budget|float) }}. Adjust as you book.</p>{{ budget_row('Accommodation', trip.budget|float * 0.35, 35) }}{{ budget_row('Transportation', trip.budget|float * 0.20, 20) }}{{ budget_row('Food', trip.budget|float * 0.18, 18) }}{{ budget_row('Activities', trip.budget|float * 0.15, 15) }}{{ budget_row('Shopping & misc.', trip.budget|float * 0.12, 12) }}<div class='budget-total'><span>Total estimated</span><strong>{{ '%.0f'|format(trip.budget|float) }}</strong></div></section>
    <section class='utility-card'><div class='section-kicker'>Weather</div><h4>Plan with the forecast</h4><p class='muted'>Live weather is not connected to this trip yet. Check it before packing.</p><a class='map-link' target='_blank' rel='noopener' href='https://www.google.com/search?q={{ trip.destination|urlencode }}+weather'>View live weather ↗</a></section>
    <section class='utility-card'><div class='section-kicker'>Packing suggestions</div><h4>Build your checklist</h4><p class='muted'>For {{ days(trip) }} days focused on {{ trip.interests }}, start with comfortable walking shoes, weather-appropriate layers, chargers, and any activity-specific essentials.</p></section>
    <section class='utility-card'><div class='section-kicker'>Travel tips</div><h4>Before you go</h4><p class='muted'>Keep key reservations offline, confirm local entry requirements, and leave room in the plan for transfers and rest.</p></section>
  </div>
</article>
{%- endmacro %}
<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>TravelMate | Your trips</title><link rel='stylesheet' href='/styles.css'></head><body class='dashboard-body'><div class='dashboard-shell'>
<aside class='sidebar'><a class='brand-wrap sidebar-brand' href='/dashboard?view=upcoming'><span class='brand-badge'>✦</span><span>TravelMate</span></a><nav class='nav-links' aria-label='Main navigation'><a href='/dashboard?view=upcoming' class='{% if view == "upcoming" %}active{% endif %}'>⌂ Dashboard</a><a href='/dashboard?view=upcoming'>✦ Upcoming trips</a><a href='#explore'>⌕ Explore</a><a href='/dashboard?view=history' class='{% if view == "history" %}active{% endif %}'>◷ Trip history</a><a href='#profile'>⚙ Profile & settings</a></nav><div class='sidebar-bottom' id='profile'><div class='mini-profile'><span>{{ user.name[:1]|upper }}</span><div><b>{{ user.name }}</b><small>{{ user.email }}</small></div></div><a class='logout-link' href='/logout'>↪ Logout</a></div></aside>
<main class='dashboard-content'><header class='topbar'><div><p class='eyebrow'>Your travel space</p><h1>Welcome back, {{ user.name.split(' ')[0] }}</h1><p class='header-copy'>Everything for your next journey, thoughtfully in one place.</p></div><div class='top-actions'><label class='destination-search'>⌕<input type='search' placeholder='Search your trips' data-trip-search aria-label='Search your trips'></label><a class='primary-btn plan-btn' href='/dashboard?view=new'>+ Plan new trip</a></div></header>
{% for message in get_flashed_messages() %}<p class='message'>{{ message }}</p>{% endfor %}
<section class='stats-grid'><article class='stat-card'><span class='stat-icon blue'>✦</span><div><small>Total trips</small><strong>{{ trips|length }}</strong></div></article><article class='stat-card'><span class='stat-icon purple'>↗</span><div><small>Upcoming</small><strong>{{ upcoming|length }}</strong></div></article><article class='stat-card'><span class='stat-icon green'>✓</span><div><small>Completed</small><strong>{{ trips|selectattr('status','equalto','completed')|list|length }}</strong></div></article><article class='stat-card'><span class='stat-icon orange'>¤</span><div><small>Estimated travel budget</small><strong>{{ '%.0f'|format(estimated_budget) }}</strong></div></article></section>
{% if view == 'new' %}<section class='panel trip-form-panel'><div class='panel-header'><div><p class='section-kicker'>Trip details</p><h2>{{ 'Edit your trip' if edit else 'Plan a new trip' }}</h2></div>{% if edit %}<a class='map-link' href='/dashboard?view=upcoming'>Cancel</a>{% endif %}</div><form method='post' class='trip-form' action='{{ "/trip/" + edit.id if edit else "/trip" }}'><label>Starting from<input id='origin' name='origin' value='{{ edit.origin if edit else "" }}' required></label><label>Destination<input id='destination' name='destination' value='{{ edit.destination if edit else "" }}' required></label><label>Start date<input id='startDate' name='start_date' type='date' value='{{ edit.start_date if edit else "" }}' required></label><label>End date<input id='endDate' name='end_date' type='date' value='{{ edit.end_date if edit else "" }}' required></label><label>Status<select id='status' name='status'><option value='upcoming' {% if not edit or edit.status == 'upcoming' %}selected{% endif %}>Upcoming</option><option value='completed' {% if edit and edit.status == 'completed' %}selected{% endif %}>Completed</option></select></label><div id='upcomingFields' class='trip-preferences-fields'><label>Budget<input id='budget' name='budget' type='number' min='0' step='0.01' value='{{ edit.budget if edit else "" }}' required></label><label>Number of people<input id='people' name='people' type='number' min='1' step='1' value='{{ edit.people if edit else "" }}' required></label><label class='full-width'>Interests<input id='interests' name='interests' value='{{ edit.interests if edit else "" }}' placeholder='Food, culture, beaches…' required></label></div><label>Route<select id='route' name='route'><option value='direct' {% if not edit or edit.route == 'direct' %}selected{% endif %}>Direct</option><option value='stops' {% if edit and edit.route == 'stops' %}selected{% endif %}>Has stops</option></select></label><label id='transportField'>Travelling by<select name='transport'>{% for method in ['Flight','Train','Car','Bus','Ship'] %}<option {% if edit and edit.legs[0].transport == method %}selected{% endif %}>{{ method }}</option>{% endfor %}</select></label><label id='stopsField' hidden>Stops<textarea id='stops' name='stops' rows='3' placeholder='One stop per line'>{{ edit.stops|join('\n') if edit else '' }}</textarea></label><div id='legMethods' class='trip-legs' hidden></div><button class='primary-btn small'>Save trip</button></form></section>
{% elif view == 'history' %}<section class='content-heading'><p class='section-kicker'>Your journeys</p><h2>Trip history</h2></section><div class='trip-history-list'>{% for trip in trips %}{% if trip.status == 'upcoming' and trip.budget %}{{ trip_card(trip) }}{% else %}<article class='history-row'><div><b>{{ trip.destination }}</b><span>{{ trip.start_date }} — {{ trip.end_date }}</span></div><a class='map-link' href='/dashboard?edit={{ trip.id }}'>View trip</a></article>{% endif %}{% else %}<p class='empty-state'>No trips yet. Plan your first journey to begin.</p>{% endfor %}</div>
{% else %}<section class='content-heading' id='explore'><div><p class='section-kicker'>Upcoming trips</p><h2>Your next adventures</h2></div><a class='map-link' href='/dashboard?view=new'>View all trips →</a></section><div class='trip-history-list'>{% for trip in upcoming %}{% if trip.budget and trip.people and trip.interests %}{{ trip_card(trip) }}{% else %}<article class='history-row'><div><b>{{ trip.destination }}</b><span>Add budget, people, and interests to unlock planning tools.</span></div><a class='primary-btn small' href='/dashboard?edit={{ trip.id }}'>Complete trip</a></article>{% endif %}{% else %}<section class='empty-hero'><p class='section-kicker'>Your next story starts here</p><h2>No upcoming trips</h2><p>Build your next itinerary, route, and budget in a few simple steps.</p><a class='primary-btn' href='/dashboard?view=new'>Plan new trip</a></section>{% endfor %}</div>{% endif %}
</main></div><script src='/script.js'></script></body></html>"""

if __name__ == "__main__": app.run(port=8000, debug=True)
