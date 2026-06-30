"""Lakeport Sports & Esports Hub — live scores, standings, and player stats.

Covers NFL, NBA, MLB, MLS, Premier League, and a local esports league.
Data files live under data_sources/sports-esports/ and are reset from
.pristine/ between evaluation runs via the data overlay system.
"""
import json
import pathlib

from flask import (
    Blueprint, abort, jsonify, redirect, render_template, request,
    session, url_for,
)
from app import db

SITE = "sports-esports"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "sports-esports",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_leagues():
    return db.query(SITE, "leagues")

def _load_teams():
    return db.query(SITE, "teams")

def _load_matches():
    return db.query(SITE, "matches")

def _load_players():
    return db.query(SITE, "players")

def _load_users():
    return db.query(SITE, "users")

def _load_favorites():
    return db.query(SITE, "favorites")

def _save_favorites(data):
    db.save_collection(SITE, "favorites", data)

def _load_comments():
    return db.query(SITE, "comments")

def _save_comments(data):
    db.save_collection(SITE, "comments", data)

def _load_subscriptions():
    return db.query(SITE, "subscriptions")

def _save_subscriptions(data):
    db.save_collection(SITE, "subscriptions", data)

def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)

def _get_current_user():
    if "user_id" in session:
        return _get_user(session["user_id"])
    return None

def _get_browsing_user():
    user = _get_current_user()
    if user:
        return user, True
    return _get_user(1), False

def _team_by_id(team_id, teams=None):
    if teams is None:
        return db.get_item(SITE, "teams", team_id)
    return next((t for t in teams if t["id"] == team_id), None)

def _league_by_id(league_id, leagues=None):
    if leagues is None:
        return db.get_item(SITE, "leagues", league_id)
    return next((l for l in leagues if l["id"] == league_id), None)

def _enrich_match(match, teams=None, leagues=None):
    """Attach team names and league info to a match dict (for display)."""
    if teams is None:
        teams = _load_teams()
    if leagues is None:
        leagues = _load_leagues()
    m = dict(match)
    home = _team_by_id(m["home_team_id"], teams)
    away = _team_by_id(m["away_team_id"], teams)
    league = _league_by_id(m["league_id"], leagues)
    m["home_team"] = home or {"name": "Unknown", "abbreviation": "???", "logo_color": "#999"}
    m["away_team"] = away or {"name": "Unknown", "abbreviation": "???", "logo_color": "#999"}
    m["league"] = league or {"name": "Unknown", "abbreviation": "???"}
    return m


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    leagues = _load_leagues()
    teams = _load_teams()
    matches = _load_matches()

    live_matches = [_enrich_match(m, teams, leagues) for m in matches if m["status"] == "live"]
    recent_final = sorted(
        [_enrich_match(m, teams, leagues) for m in matches if m["status"] == "final"],
        key=lambda m: m["date"], reverse=True
    )[:6]
    upcoming = sorted(
        [_enrich_match(m, teams, leagues) for m in matches if m["status"] == "scheduled"],
        key=lambda m: (m["date"], m["time"])
    )[:6]

    return render_template("sports-esports/index.html",
                           leagues=leagues, live_matches=live_matches,
                           recent_matches=recent_final, upcoming_matches=upcoming)


@blueprint.route("/league/<int:league_id>")
def league_detail(league_id):
    leagues = _load_leagues()
    league = _league_by_id(league_id, leagues)
    if not league:
        abort(404)
    teams = sorted(
        [t for t in _load_teams() if t["league_id"] == league_id],
        key=lambda t: t["standing"]
    )
    all_teams = _load_teams()
    matches = [_enrich_match(m, all_teams, leagues)
               for m in _load_matches() if m["league_id"] == league_id]
    matches.sort(key=lambda m: m["date"], reverse=True)
    return render_template("sports-esports/league.html",
                           league=league, teams=teams, matches=matches)


@blueprint.route("/team/<int:team_id>")
def team_detail(team_id):
    teams = _load_teams()
    team = _team_by_id(team_id, teams)
    if not team:
        abort(404)
    leagues = _load_leagues()
    league = _league_by_id(team["league_id"], leagues)
    players = [p for p in _load_players() if p["team_id"] == team_id]
    matches = [_enrich_match(m, teams, leagues)
               for m in _load_matches()
               if m["home_team_id"] == team_id or m["away_team_id"] == team_id]
    matches.sort(key=lambda m: m["date"], reverse=True)
    return render_template("sports-esports/team.html",
                           team=team, league=league, players=players, matches=matches)


@blueprint.route("/match/<int:match_id>")
def match_detail(match_id):
    matches = _load_matches()
    match = next((m for m in matches if m["id"] == match_id), None)
    if not match:
        abort(404)
    teams = _load_teams()
    leagues = _load_leagues()
    enriched = _enrich_match(match, teams, leagues)
    home_players = [p for p in _load_players() if p["team_id"] == match["home_team_id"]]
    away_players = [p for p in _load_players() if p["team_id"] == match["away_team_id"]]
    return render_template("sports-esports/match.html",
                           match=enriched, home_players=home_players,
                           away_players=away_players)


@blueprint.route("/players")
def players_page():
    players = _load_players()
    teams = _load_teams()
    leagues = _load_leagues()
    q = request.args.get("q", "").strip()
    league_id = request.args.get("league_id", type=int)
    team_id = request.args.get("team_id", type=int)

    enriched = []
    for p in players:
        pe = dict(p)
        team = _team_by_id(p["team_id"], teams)
        pe["team"] = team or {"name": "Unknown", "abbreviation": "???"}
        if team:
            pe["league"] = _league_by_id(team["league_id"], leagues) or {"name": "Unknown"}
        else:
            pe["league"] = {"name": "Unknown"}
        enriched.append(pe)

    if q:
        ql = q.lower()
        enriched = [p for p in enriched if ql in p["name"].lower()
                    or ql in p["position"].lower()
                    or ql in p["team"]["name"].lower()]
    if league_id:
        enriched = [p for p in enriched if p.get("league", {}).get("id") == league_id]
    if team_id:
        enriched = [p for p in enriched if p["team_id"] == team_id]

    return render_template("sports-esports/players.html",
                           players=enriched, leagues=leagues, teams=teams,
                           q=q, league_id=league_id, team_id=team_id)


@blueprint.route("/player/<int:player_id>")
def player_detail(player_id):
    players = _load_players()
    player = next((p for p in players if p["id"] == player_id), None)
    if not player:
        abort(404)
    teams = _load_teams()
    team = _team_by_id(player["team_id"], teams)
    leagues = _load_leagues()
    league = _league_by_id(team["league_id"], leagues) if team else None
    return render_template("sports-esports/player.html",
                           player=player, team=team, league=league)


@blueprint.route("/standings")
def standings_page():
    leagues = _load_leagues()
    teams = _load_teams()
    standings = {}
    for league in leagues:
        league_teams = sorted(
            [t for t in teams if t["league_id"] == league["id"]],
            key=lambda t: t["standing"]
        )
        standings[league["id"]] = league_teams
    return render_template("sports-esports/standings.html",
                           leagues=leagues, standings=standings)


@blueprint.route("/favorites")
def favorites_page():
    user, logged_in = _get_browsing_user()
    favorites = _load_favorites()
    fav = next((f for f in favorites if f["user_id"] == user["id"]), None)
    if not fav:
        fav = {"user_id": user["id"], "team_ids": [], "player_ids": []}

    teams = _load_teams()
    players = _load_players()
    leagues = _load_leagues()

    fav_teams = [_team_by_id(tid, teams) for tid in fav.get("team_ids", [])]
    fav_teams = [t for t in fav_teams if t]
    fav_players = []
    for pid in fav.get("player_ids", []):
        p = next((p for p in players if p["id"] == pid), None)
        if p:
            pe = dict(p)
            pe["team"] = _team_by_id(p["team_id"], teams) or {"name": "Unknown"}
            fav_players.append(pe)

    # Get matches for favorite teams
    fav_team_ids = set(fav.get("team_ids", []))
    all_matches = _load_matches()
    fav_matches = [
        _enrich_match(m, teams, leagues)
        for m in all_matches
        if m["home_team_id"] in fav_team_ids or m["away_team_id"] in fav_team_ids
    ]
    fav_matches.sort(key=lambda m: m["date"], reverse=True)

    return render_template("sports-esports/favorites.html",
                           user=user, logged_in=logged_in,
                           fav_teams=fav_teams, fav_players=fav_players,
                           fav_matches=fav_matches[:10], fav=fav,
                           all_teams=teams, all_players=players)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("sports-esports/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("sports-esports/login.html",
                               error="Invalid username or password")
    session["user_id"] = user["id"]
    return redirect(url_for("sports-esports.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("sports-esports.index"))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/leagues")
def api_leagues():
    return jsonify(_load_leagues())


@blueprint.route("/api/teams")
def api_teams():
    teams = _load_teams()
    league_id = request.args.get("league_id", type=int)
    city = request.args.get("city", "").strip()
    q = request.args.get("q", "").strip()
    if league_id:
        teams = [t for t in teams if t["league_id"] == league_id]
    if city:
        teams = [t for t in teams if t["city"].lower() == city.lower()]
    if q:
        ql = q.lower()
        teams = [t for t in teams if ql in t["name"].lower() or ql in t["city"].lower()
                 or ql in t["abbreviation"].lower()]
    sort = request.args.get("sort", "").strip()
    if sort == "wins":
        teams.sort(key=lambda t: t["wins"], reverse=True)
    elif sort == "losses":
        teams.sort(key=lambda t: t["losses"], reverse=True)
    elif sort == "standing":
        teams.sort(key=lambda t: t["standing"])
    elif sort == "name":
        teams.sort(key=lambda t: t["name"].lower())
    return jsonify(teams)


@blueprint.route("/api/teams/<int:team_id>")
def api_team(team_id):
    team = _team_by_id(team_id)
    if not team:
        abort(404)
    return jsonify(team)


@blueprint.route("/api/matches")
def api_matches():
    matches = _load_matches()
    league_id = request.args.get("league_id", type=int)
    date = request.args.get("date", "").strip()
    status = request.args.get("status", "").strip()
    team_id = request.args.get("team_id", type=int)
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    limit = request.args.get("limit", type=int)

    if league_id:
        matches = [m for m in matches if m["league_id"] == league_id]
    if date:
        matches = [m for m in matches if m["date"] == date]
    if status:
        matches = [m for m in matches if m["status"] == status]
    if team_id:
        matches = [m for m in matches if m["home_team_id"] == team_id or m["away_team_id"] == team_id]
    if date_from:
        matches = [m for m in matches if m["date"] >= date_from]
    if date_to:
        matches = [m for m in matches if m["date"] <= date_to]

    matches.sort(key=lambda m: (m["date"], m["time"]), reverse=True)
    if limit:
        matches = matches[:limit]

    # Enrich with team names
    teams = _load_teams()
    leagues = _load_leagues()
    enriched = []
    for m in matches:
        em = dict(m)
        home = _team_by_id(m["home_team_id"], teams)
        away = _team_by_id(m["away_team_id"], teams)
        league = _league_by_id(m["league_id"], leagues)
        em["home_team_name"] = home["name"] if home else "Unknown"
        em["away_team_name"] = away["name"] if away else "Unknown"
        em["league_name"] = league["name"] if league else "Unknown"
        enriched.append(em)

    return jsonify(enriched)


@blueprint.route("/api/matches/<int:match_id>")
def api_match(match_id):
    matches = _load_matches()
    match = next((m for m in matches if m["id"] == match_id), None)
    if not match:
        abort(404)
    teams = _load_teams()
    leagues = _load_leagues()
    enriched = _enrich_match(match, teams, leagues)
    # Flatten team/league to serializable dicts
    enriched["home_team_name"] = enriched["home_team"]["name"]
    enriched["away_team_name"] = enriched["away_team"]["name"]
    enriched["league_name"] = enriched["league"]["name"]
    del enriched["home_team"]
    del enriched["away_team"]
    del enriched["league"]
    return jsonify(enriched)


@blueprint.route("/api/players")
def api_players():
    players = _load_players()
    team_id = request.args.get("team_id", type=int)
    league_id = request.args.get("league_id", type=int)
    position = request.args.get("position", "").strip()
    q = request.args.get("q", "").strip()

    if team_id:
        players = [p for p in players if p["team_id"] == team_id]
    if league_id:
        teams = _load_teams()
        league_team_ids = {t["id"] for t in teams if t["league_id"] == league_id}
        players = [p for p in players if p["team_id"] in league_team_ids]
    if position:
        pl = position.lower()
        players = [p for p in players if pl in p["position"].lower()]
    if q:
        ql = q.lower()
        players = [p for p in players if ql in p["name"].lower() or ql in p["position"].lower()]

    return jsonify(players)


@blueprint.route("/api/players/<int:player_id>")
def api_player(player_id):
    players = _load_players()
    player = next((p for p in players if p["id"] == player_id), None)
    if not player:
        abort(404)
    return jsonify(player)


@blueprint.route("/api/standings/<int:league_id>")
def api_standings(league_id):
    league = _league_by_id(league_id)
    if not league:
        abort(404)
    teams = sorted(
        [t for t in _load_teams() if t["league_id"] == league_id],
        key=lambda t: t["standing"]
    )
    for t in teams:
        total = t["wins"] + t["losses"]
        t["win_pct"] = round(t["wins"] / total, 3) if total > 0 else 0.0
        t["games_played"] = total
    return jsonify({"league": league, "standings": teams})


@blueprint.route("/api/favorites", methods=["GET"])
def api_favorites_get():
    user, _ = _get_browsing_user()
    favorites = _load_favorites()
    fav = next((f for f in favorites if f["user_id"] == user["id"]), None)
    if not fav:
        return jsonify({"user_id": user["id"], "team_ids": [], "player_ids": []})
    return jsonify(fav)


@blueprint.route("/api/favorites", methods=["POST"])
def api_favorites_post():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}
    action = data.get("action", "add")  # add, remove, set
    team_id = data.get("team_id")
    if team_id is not None:
        team_id = int(team_id)
    player_id = data.get("player_id")
    if player_id is not None:
        player_id = int(player_id)

    favorites = _load_favorites()
    fav = next((f for f in favorites if f["user_id"] == user["id"]), None)

    if not fav:
        new_id = max((f["id"] for f in favorites), default=0) + 1
        fav = {"id": new_id, "user_id": user["id"], "team_ids": [], "player_ids": []}
        favorites.append(fav)

    if action == "set":
        # Full replacement
        if "team_ids" in data:
            fav["team_ids"] = data["team_ids"]
        if "player_ids" in data:
            fav["player_ids"] = data["player_ids"]
    elif action == "add":
        if team_id and team_id not in fav["team_ids"]:
            fav["team_ids"].append(team_id)
        if player_id and player_id not in fav["player_ids"]:
            fav["player_ids"].append(player_id)
    elif action == "remove":
        if team_id and team_id in fav["team_ids"]:
            fav["team_ids"].remove(team_id)
        if player_id and player_id in fav["player_ids"]:
            fav["player_ids"].remove(player_id)

    _save_favorites(favorites)
    return jsonify(fav)


@blueprint.route("/api/stats")
def api_stats():
    leagues = _load_leagues()
    teams = _load_teams()
    matches = _load_matches()
    players = _load_players()

    league_id = request.args.get("league_id", type=int)

    if league_id:
        teams = [t for t in teams if t["league_id"] == league_id]
        team_ids = {t["id"] for t in teams}
        matches = [m for m in matches if m["league_id"] == league_id]
        players = [p for p in players if p["team_id"] in team_ids]

    total_matches = len(matches)
    live_count = sum(1 for m in matches if m["status"] == "live")
    final_count = sum(1 for m in matches if m["status"] == "final")
    scheduled_count = sum(1 for m in matches if m["status"] == "scheduled")

    # Top scoring teams (by total points scored in final matches)
    team_scores = {}
    for m in matches:
        if m["status"] == "final":
            team_scores[m["home_team_id"]] = team_scores.get(m["home_team_id"], 0) + m["home_score"]
            team_scores[m["away_team_id"]] = team_scores.get(m["away_team_id"], 0) + m["away_score"]

    top_scorers = sorted(team_scores.items(), key=lambda x: -x[1])[:5]
    top_scoring_teams = []
    for tid, score in top_scorers:
        team = _team_by_id(tid, _load_teams())
        if team:
            top_scoring_teams.append({"team": team["name"], "total_score": score})

    return jsonify({
        "total_leagues": len(leagues) if not league_id else 1,
        "total_teams": len(teams),
        "total_players": len(players),
        "total_matches": total_matches,
        "live_matches": live_count,
        "final_matches": final_count,
        "scheduled_matches": scheduled_count,
        "top_scoring_teams": top_scoring_teams,
    })


# Form-based favorites toggle (for HTML forms)
@blueprint.route("/favorites/toggle", methods=["POST"])
def toggle_favorite():
    user = _get_current_user()
    if not user:
        return redirect(url_for("sports-esports.login_page"))

    team_id = request.form.get("team_id", type=int)
    player_id = request.form.get("player_id", type=int)
    action = request.form.get("action", "add")

    favorites = _load_favorites()
    fav = next((f for f in favorites if f["user_id"] == user["id"]), None)
    if not fav:
        new_id = max((f["id"] for f in favorites), default=0) + 1
        fav = {"id": new_id, "user_id": user["id"], "team_ids": [], "player_ids": []}
        favorites.append(fav)

    if action == "add":
        if team_id and team_id not in fav["team_ids"]:
            fav["team_ids"].append(team_id)
        if player_id and player_id not in fav["player_ids"]:
            fav["player_ids"].append(player_id)
    elif action == "remove":
        if team_id and team_id in fav["team_ids"]:
            fav["team_ids"].remove(team_id)
        if player_id and player_id in fav["player_ids"]:
            fav["player_ids"].remove(player_id)

    _save_favorites(favorites)
    return redirect(request.referrer or url_for("sports-esports.favorites_page"))


@blueprint.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return jsonify({"error": "Invalid credentials"}), 401
    session["user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"],
                    "name": user["name"]})


# ---------------------------------------------------------------------------
# Macro-support API routes
# ---------------------------------------------------------------------------

# --- navigate_by_ranking: get team at Nth rank in a league ---
@blueprint.route("/api/standings/<int:league_id>/rank/<int:rank>")
def api_team_by_rank(league_id, rank):
    league = _league_by_id(league_id)
    if not league:
        abort(404)
    teams = sorted(
        [t for t in _load_teams() if t["league_id"] == league_id],
        key=lambda t: t["standing"]
    )
    team = next((t for t in teams if t["standing"] == rank), None)
    if not team:
        abort(404)
    return jsonify(team)


# --- search_by_semantic: keyword-weighted search across teams/players ---
@blueprint.route("/api/search")
def api_semantic_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"teams": [], "players": [], "matches": []})

    ql = q.lower()
    terms = ql.split()

    teams = _load_teams()
    players = _load_players()
    matches = _load_matches()
    leagues = _load_leagues()

    def _score(text, terms):
        return sum(1 for t in terms if t in text.lower())

    # Score teams
    team_results = []
    for t in teams:
        text = f"{t['name']} {t['city']} {t['abbreviation']}"
        league = _league_by_id(t["league_id"], leagues)
        if league:
            text += f" {league['name']} {league['sport']}"
        s = _score(text, terms)
        if s > 0:
            team_results.append({"team": t, "score": s})
    team_results.sort(key=lambda x: -x["score"])

    # Score players
    player_results = []
    for p in players:
        text = f"{p['name']} {p['position']}"
        team = _team_by_id(p["team_id"], teams)
        if team:
            text += f" {team['name']}"
        s = _score(text, terms)
        if s > 0:
            player_results.append({"player": p, "score": s})
    player_results.sort(key=lambda x: -x["score"])

    return jsonify({
        "teams": [r["team"] for r in team_results],
        "players": [r["player"] for r in player_results],
    })


# --- extract_by_extremum: find team with most/fewest of a stat ---
@blueprint.route("/api/teams/extremum")
def api_teams_extremum():
    stat = request.args.get("stat", "wins").strip()
    mode = request.args.get("mode", "max").strip()  # max or min
    league_id = request.args.get("league_id", type=int)

    teams = _load_teams()
    if league_id:
        teams = [t for t in teams if t["league_id"] == league_id]
    if not teams:
        return jsonify({"error": "No teams found"}), 404

    if stat == "win_pct":
        for t in teams:
            total = t["wins"] + t["losses"]
            t["win_pct"] = round(t["wins"] / total, 3) if total > 0 else 0.0

    if stat not in teams[0]:
        return jsonify({"error": f"Unknown stat: {stat}"}), 400

    if mode == "min":
        result = min(teams, key=lambda t: t[stat])
    else:
        result = max(teams, key=lambda t: t[stat])

    return jsonify({"team": result, "stat": stat, "mode": mode, "value": result[stat]})


# --- extract_by_slider: filter teams by a numeric threshold ---
@blueprint.route("/api/teams/filter")
def api_teams_filter_threshold():
    stat = request.args.get("stat", "wins").strip()
    min_val = request.args.get("min", type=float)
    max_val = request.args.get("max", type=float)
    league_id = request.args.get("league_id", type=int)

    teams = _load_teams()
    if league_id:
        teams = [t for t in teams if t["league_id"] == league_id]

    # Compute derived stats
    for t in teams:
        total = t["wins"] + t["losses"]
        t["win_pct"] = round(t["wins"] / total, 3) if total > 0 else 0.0
        t["games_played"] = total

    if stat not in teams[0] if teams else True:
        return jsonify({"error": f"Unknown stat: {stat}"}), 400

    if min_val is not None:
        teams = [t for t in teams if t[stat] >= min_val]
    if max_val is not None:
        teams = [t for t in teams if t[stat] <= max_val]

    teams.sort(key=lambda t: t[stat], reverse=True)
    return jsonify({"stat": stat, "min": min_val, "max": max_val, "count": len(teams), "teams": teams})


# --- compute_from_table: aggregate stats from standings ---
@blueprint.route("/api/standings/<int:league_id>/stats")
def api_standings_stats(league_id):
    league = _league_by_id(league_id)
    if not league:
        abort(404)
    teams = [t for t in _load_teams() if t["league_id"] == league_id]
    if not teams:
        return jsonify({"error": "No teams in league"}), 404

    total_wins = sum(t["wins"] for t in teams)
    total_losses = sum(t["losses"] for t in teams)
    total_games = total_wins + total_losses
    avg_wins = round(total_wins / len(teams), 1)
    avg_losses = round(total_losses / len(teams), 1)
    max_wins_team = max(teams, key=lambda t: t["wins"])
    min_wins_team = min(teams, key=lambda t: t["wins"])

    return jsonify({
        "league": league,
        "num_teams": len(teams),
        "total_wins": total_wins,
        "total_losses": total_losses,
        "total_games": total_games,
        "avg_wins": avg_wins,
        "avg_losses": avg_losses,
        "max_wins": {"team": max_wins_team["name"], "wins": max_wins_team["wins"]},
        "min_wins": {"team": min_wins_team["name"], "wins": min_wins_team["wins"]},
    })


# --- compare_by_dropdown: compare two teams ---
@blueprint.route("/api/teams/compare")
def api_teams_compare():
    ids_str = request.args.get("ids", "")
    ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
    teams = _load_teams()
    leagues = _load_leagues()
    selected = []
    for tid in ids:
        team = _team_by_id(tid, teams)
        if team:
            t = dict(team)
            total = t["wins"] + t["losses"]
            t["win_pct"] = round(t["wins"] / total, 3) if total > 0 else 0.0
            t["games_played"] = total
            league = _league_by_id(t["league_id"], leagues)
            t["league_name"] = league["name"] if league else "Unknown"
            selected.append(t)
    return jsonify(selected)


@blueprint.route("/compare")
def compare_page():
    teams = _load_teams()
    ids_str = request.args.get("ids", "")
    selected = []
    leagues = _load_leagues()
    if ids_str:
        ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
        for tid in ids:
            team = _team_by_id(tid, teams)
            if team:
                t = dict(team)
                total = t["wins"] + t["losses"]
                t["win_pct"] = round(t["wins"] / total, 3) if total > 0 else 0.0
                t["games_played"] = total
                league = _league_by_id(t["league_id"], leagues)
                t["league_name"] = league["name"] if league else "Unknown"
                selected.append(t)
    return render_template("sports-esports/compare.html", teams=teams, selected=selected)


# --- verify_by_slider: check if a stat meets a threshold ---
@blueprint.route("/api/teams/<int:team_id>/verify")
def api_team_verify(team_id):
    stat = request.args.get("stat", "win_pct").strip()
    threshold = request.args.get("threshold", type=float)
    operator = request.args.get("op", "gte").strip()  # gte, lte, gt, lt, eq

    team = _team_by_id(team_id)
    if not team:
        abort(404)

    t = dict(team)
    total = t["wins"] + t["losses"]
    t["win_pct"] = round(t["wins"] / total, 3) if total > 0 else 0.0
    t["games_played"] = total

    if stat not in t:
        return jsonify({"error": f"Unknown stat: {stat}"}), 400
    if threshold is None:
        return jsonify({"error": "threshold parameter required"}), 400

    value = t[stat]
    ops = {
        "gte": value >= threshold,
        "lte": value <= threshold,
        "gt": value > threshold,
        "lt": value < threshold,
        "eq": value == threshold,
    }
    result = ops.get(operator, False)

    return jsonify({
        "team": t["name"],
        "stat": stat,
        "value": value,
        "threshold": threshold,
        "operator": operator,
        "result": result,
    })


# --- play_by_playback: match highlight placeholder ---
@blueprint.route("/match/<int:match_id>/highlights")
def match_highlights(match_id):
    matches = _load_matches()
    match = next((m for m in matches if m["id"] == match_id), None)
    if not match:
        abort(404)
    teams = _load_teams()
    leagues = _load_leagues()
    enriched = _enrich_match(match, teams, leagues)
    return render_template("sports-esports/highlights.html", match=enriched)


@blueprint.route("/api/matches/<int:match_id>/highlights")
def api_match_highlights(match_id):
    matches = _load_matches()
    match = next((m for m in matches if m["id"] == match_id), None)
    if not match:
        abort(404)
    if match["status"] == "scheduled":
        return jsonify({"match_id": match_id, "available": False, "highlights": []})
    return jsonify({
        "match_id": match_id,
        "available": True,
        "highlights": [
            {"timestamp": "00:12", "description": "Opening play"},
            {"timestamp": "15:34", "description": "Key scoring moment"},
            {"timestamp": "42:10", "description": "Turning point"},
            {"timestamp": "58:00", "description": "Final moments"},
        ]
    })


# --- post_from_free_text: post a comment on a match ---
@blueprint.route("/api/matches/<int:match_id>/comments", methods=["GET"])
def api_match_comments_get(match_id):
    comments = _load_comments()
    match_comments = [c for c in comments if c["match_id"] == match_id]
    match_comments.sort(key=lambda c: c["created_at"], reverse=True)
    return jsonify(match_comments)


@blueprint.route("/api/matches/<int:match_id>/comments", methods=["POST"])
def api_match_comments_post(match_id):
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401

    matches = _load_matches()
    match = next((m for m in matches if m["id"] == match_id), None)
    if not match:
        abort(404)

    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Comment text required"}), 400

    comments = _load_comments()
    new_id = max((c["id"] for c in comments), default=0) + 1
    import datetime
    comment = {
        "id": new_id,
        "match_id": match_id,
        "user_id": user["id"],
        "username": user["username"],
        "name": user["name"],
        "text": text,
        "likes": 0,
        "liked_by": [],
        "created_at": datetime.datetime.now().isoformat(),
    }
    comments.append(comment)
    _save_comments(comments)
    return jsonify(comment), 201


@blueprint.route("/match/<int:match_id>/comment", methods=["POST"])
def form_post_comment(match_id):
    user = _get_current_user()
    if not user:
        return redirect(url_for("sports-esports.login_page"))

    text = request.form.get("text", "").strip()
    if text:
        comments = _load_comments()
        new_id = max((c["id"] for c in comments), default=0) + 1
        import datetime
        comment = {
            "id": new_id,
            "match_id": match_id,
            "user_id": user["id"],
            "username": user["username"],
            "name": user["name"],
            "text": text,
            "likes": 0,
            "liked_by": [],
            "created_at": datetime.datetime.now().isoformat(),
        }
        comments.append(comment)
        _save_comments(comments)
    return redirect(url_for("sports-esports.match_detail", match_id=match_id))


# --- react_by_toggle: like/unlike a comment ---
@blueprint.route("/api/comments/<int:comment_id>/like", methods=["POST"])
def api_comment_like(comment_id):
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401

    comments = _load_comments()
    comment = next((c for c in comments if c["id"] == comment_id), None)
    if not comment:
        abort(404)

    liked_by = comment.setdefault("liked_by", [])
    if user["id"] in liked_by:
        liked_by.remove(user["id"])
        comment["likes"] = len(liked_by)
        action = "unliked"
    else:
        liked_by.append(user["id"])
        comment["likes"] = len(liked_by)
        action = "liked"

    _save_comments(comments)
    return jsonify({"action": action, "comment_id": comment_id, "likes": comment["likes"]})


# --- follow_by_dropdown: already supported via favorites/toggle form ---
# (Favorites page has dropdown + Add Team button, which is follow_by_dropdown)

# --- subscribe_by_toggle: subscribe/unsubscribe to league notifications ---
@blueprint.route("/api/leagues/<int:league_id>/subscribe", methods=["POST"])
def api_league_subscribe(league_id):
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not logged in"}), 401

    league = _league_by_id(league_id)
    if not league:
        abort(404)

    subs = _load_subscriptions()
    user_sub = next((s for s in subs if s["user_id"] == user["id"]), None)
    if not user_sub:
        new_id = max((s["id"] for s in subs), default=0) + 1
        user_sub = {"id": new_id, "user_id": user["id"], "league_ids": []}
        subs.append(user_sub)

    if league_id in user_sub["league_ids"]:
        user_sub["league_ids"].remove(league_id)
        action = "unsubscribed"
    else:
        user_sub["league_ids"].append(league_id)
        action = "subscribed"

    _save_subscriptions(subs)
    return jsonify({"action": action, "league_id": league_id,
                    "subscribed_leagues": user_sub["league_ids"]})


@blueprint.route("/api/subscriptions", methods=["GET"])
def api_subscriptions_get():
    user, _ = _get_browsing_user()
    subs = _load_subscriptions()
    user_sub = next((s for s in subs if s["user_id"] == user["id"]), None)
    if not user_sub:
        return jsonify({"user_id": user["id"], "league_ids": []})
    return jsonify(user_sub)


@blueprint.route("/league/<int:league_id>/subscribe", methods=["POST"])
def form_league_subscribe(league_id):
    user = _get_current_user()
    if not user:
        return redirect(url_for("sports-esports.login_page"))

    league = _league_by_id(league_id)
    if not league:
        abort(404)

    subs = _load_subscriptions()
    user_sub = next((s for s in subs if s["user_id"] == user["id"]), None)
    if not user_sub:
        new_id = max((s["id"] for s in subs), default=0) + 1
        user_sub = {"id": new_id, "user_id": user["id"], "league_ids": []}
        subs.append(user_sub)

    if league_id in user_sub["league_ids"]:
        user_sub["league_ids"].remove(league_id)
    else:
        user_sub["league_ids"].append(league_id)

    _save_subscriptions(subs)
    return redirect(request.referrer or url_for("sports-esports.league_detail", league_id=league_id))


# --- User API for task layer ---
@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify({k: v for k, v in user.items() if k != "password"})


@blueprint.route("/api/users/<int:user_id>/favorites")
def api_user_favorites(user_id):
    """Get favorites for a specific user (for verifier use)."""
    favorites = _load_favorites()
    fav = next((f for f in favorites if f["user_id"] == user_id), None)
    if not fav:
        return jsonify({"user_id": user_id, "team_ids": [], "player_ids": []})
    return jsonify(fav)


@blueprint.route("/api/users/<int:user_id>/subscriptions")
def api_user_subscriptions(user_id):
    """Get subscriptions for a specific user (for verifier use)."""
    subs = _load_subscriptions()
    user_sub = next((s for s in subs if s["user_id"] == user_id), None)
    if not user_sub:
        return jsonify({"user_id": user_id, "league_ids": []})
    return jsonify(user_sub)
