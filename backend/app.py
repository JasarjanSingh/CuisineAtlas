import os
import uuid
from collections import defaultdict
from random import sample
from typing import List, Dict, Any, Set
from math import radians, sin, cos, sqrt, atan2

import pandas as pd
from sklearn.cluster import KMeans
import folium
import pgeocode
from flask import Flask, render_template, request, redirect, url_for, session
from flask_cors import CORS

from recommendation import recommend_dishes_kde_enhanced

app = Flask(__name__)
CORS(app)  # enable CORS for all routes
app.secret_key = os.environ.get("SECRET_KEY", "SOME_SECRET_KEY")

BASE_PATH = os.path.dirname(os.path.abspath(__file__))

# ─── LOAD & PREPARE DATA ───────────────────────────────────────────────────────

# flavors & clusters
flavors = pd.read_csv(os.path.join(BASE_PATH, "Output Data", "flavors.csv"), low_memory=False)
flavors = flavors[["dish_name_clean_fuzzy", "salty", "bitter", "sweet", "sour", "umami"]]
X = flavors.drop("dish_name_clean_fuzzy", axis=1)
kmeans = KMeans(n_clusters=15, random_state=0)
flavors["Cluster"] = kmeans.fit_predict(X)

# fuzzy ↔ clean dishes mappings
fuzzy_df        = pd.read_csv(os.path.join(BASE_PATH, "Output Data", "fuzzy_dishes.csv"), low_memory=False)
clean_dishes_df = pd.read_csv(os.path.join(BASE_PATH, "Output Data", "clean_dishes.csv"), low_memory=False)

# menus
menu_df_1 = pd.read_csv(os.path.join(BASE_PATH, "Output Data", "menu_df_1.csv"), low_memory=False)
menu_df_2 = pd.read_csv(os.path.join(BASE_PATH, "Output Data", "menu_df_2.csv"), low_memory=False)
menu_df   = pd.concat([menu_df_1, menu_df_2], ignore_index=True)

# locations & hours & restaurants
locations_df      = pd.read_csv(os.path.join(BASE_PATH, "Output Data", "dotlas_locations.csv"), low_memory=False)
business_hours_df = pd.read_csv(os.path.join(BASE_PATH, "Output Data", "dotlas_business_hours.csv"), low_memory=False)
restaurants_df    = pd.read_csv(os.path.join(BASE_PATH, "Output Data", "dotlas_restaurants.csv"), low_memory=False)

# in‑memory store for recommendations
recommendations_store: Dict[str, Any] = {}

# geocoder for ZIP lookup
geolocator = pgeocode.Nominatim('us')


# ─── HELPERS ───────────────────────────────────────────────────────────────────

def haversine(lat1, lon1, lat2, lon2):
    """Return distance in miles between two lat/lon points."""
    R = 3958.8  # Earth radius in miles
    φ1, φ2 = radians(lat1), radians(lat2)
    Δφ    = radians(lat2 - lat1)
    Δλ    = radians(lon2 - lon1)
    a = sin(Δφ/2)**2 + cos(φ1)*cos(φ2)*sin(Δλ/2)**2
    return 2 * R * atan2(sqrt(a), sqrt(1-a))


def _get_random_dishes(n: int = 20, exclude_set: Set[str] = None) -> List[str]:
    exclude_set = exclude_set or set()
    available = flavors[~flavors["dish_name_clean_fuzzy"].isin(exclude_set)]
    if len(available) <= n:
        return available["dish_name_clean_fuzzy"].tolist()
    return available.sample(n)["dish_name_clean_fuzzy"].tolist()


def _process_recommendations(recommended_df: pd.DataFrame) -> List[Dict[str, Any]]:
    score_map = recommended_df.set_index("dish_name_clean_fuzzy")["combined_score"].to_dict()
    rec_list  = recommended_df["dish_name_clean_fuzzy"].unique().tolist()

    fuzzy_subset = fuzzy_df[fuzzy_df["dish_name_clean_fuzzy"].isin(rec_list)]
    dish_to_clean = fuzzy_subset.groupby("dish_name_clean_fuzzy")["clean_dish_id"].apply(list).to_dict()
    clean_ids     = fuzzy_subset["clean_dish_id"].unique().tolist()

    clean_subset = clean_dishes_df[clean_dishes_df["clean_dish_id"].isin(clean_ids)]
    clean_to_raw = clean_subset.groupby("clean_dish_id")["raw_dish_id"].apply(list).to_dict()

    menu_subset = menu_df[menu_df["raw_dish_id"].isin(clean_subset["raw_dish_id"])]
    raw_lookup  = defaultdict(list)
    for row in menu_subset.to_dict(orient="records"):
        raw_lookup[row["raw_dish_id"]].append({
            "restaurant_id":   row["restaurant_id"],
            "raw_dish_name":   row.get("raw_dish_name"),
            "dish_description": row.get("dish_description"),
        })

    rest_lookup = restaurants_df.set_index("restaurant_id").to_dict(orient="index")
    loc_lookup  = locations_df.set_index("restaurant_id").to_dict(orient="index")
    hrs_map     = defaultdict(list)
    for _, r in business_hours_df.iterrows():
        hrs_map[r["restaurant_id"]].append({
            "day_of_week":         r["day_of_week"],
            "open_time":           r["open_time"],
            "number_of_hours_open": r["number_of_hours_open"],
        })

    output = []
    for dish_name in rec_list:
        raw_ids = [
            rid
            for cid in dish_to_clean.get(dish_name, [])
            for rid in clean_to_raw.get(cid, [])
        ]

        restaurants_list = []
        for rwid in raw_ids:
            for rec in raw_lookup.get(rwid, []):
                rid = rec["restaurant_id"]
                if pd.isna(rid) or rid not in rest_lookup:
                    continue
                rinfo = rest_lookup[rid]
                loc   = loc_lookup.get(rid, {})
                restaurants_list.append({
                    "restaurant_id":         rid,
                    "restaurant_name":       rinfo.get("restaurant_name"),
                    "restaurant_description": rinfo.get("restaurant_description") or rinfo.get("description"),
                    "restaurant_website":    rinfo.get("restaurant_website"),
                    "telephone_number":      rinfo.get("telephone_number"),
                    "latitude":              loc.get("latitude"),
                    "longitude":             loc.get("longitude"),
                    "address":               loc.get("address"),
                    "city":                  loc.get("city"),
                    "state":                 loc.get("state"),
                    "raw_dish_name":         rec["raw_dish_name"],
                    "dish_description":      rec["dish_description"],
                    "business_hours":        hrs_map[rid],
                })
        output.append({
            "dish_name_clean_fuzzy": dish_name,
            "combined_score":        score_map.get(dish_name),
            "restaurants":           restaurants_list,
        })

    return output


# ─── ROUTES ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    session.setdefault("current_dishes", [])
    session.setdefault("dishes_liked", [])
    can_reco = len(session["dishes_liked"]) >= 15
    return render_template(
        "index.html",
        current_dishes=session["current_dishes"],
        liked_dishes=session["dishes_liked"],
        can_recommend=can_reco
    )


@app.route("/set_location", methods=["POST"])
def set_location():
    zip_code = request.form.get("zip")
    radius   = float(request.form.get("radius", 10))
    loc      = geolocator.query_postal_code(zip_code)

    if loc is not None and not pd.isna(loc.latitude):
        session["user_lat"]       = loc.latitude
        session["user_lon"]       = loc.longitude
        session["radius_miles"]   = radius
    else:
        # invalid ZIP → clear
        session.pop("user_lat", None)
        session.pop("user_lon", None)
        session.pop("radius_miles", None)

    session.modified = True
    return redirect(url_for("index"))


@app.route("/get_random_dishes")
def get_random_dishes_route():
    session.setdefault("dishes_liked", [])
    session.setdefault("already_displayed", [])
    exclude = set(session["current_dishes"]) | set(session["already_displayed"]) | set(session["dishes_liked"])
    new_list = _get_random_dishes(20, exclude)
    session["current_dishes"]     = new_list
    session["already_displayed"] += new_list
    session.modified = True
    return redirect(url_for("index"))


@app.route("/toggle_like", methods=["POST"])
def toggle_like():
    dish   = request.form.get("dish_name")
    anchor = request.form.get("anchor", "")
    session.setdefault("dishes_liked", [])
    if dish in session["dishes_liked"]:
        session["dishes_liked"].remove(dish)
    else:
        session["dishes_liked"].append(dish)
    session.modified = True
    return redirect(url_for("index") + (f"#{anchor}" if anchor else ""))


@app.route("/generate_recommendations")
def generate_recommendations():
    liked = session.get("dishes_liked", [])
    if len(liked) < 15:
        return "Please like at least 15 dishes first. <a href='/'>Go back</a>"

    rec_df = recommend_dishes_kde_enhanced(liked, flavors, total_recommendations=100)
    rec_df = rec_df[~rec_df["dish_name_clean_fuzzy"].isin(liked)]
    nested = _process_recommendations(rec_df)
    valid  = [d for d in nested if d["restaurants"]]
    valid.sort(key=lambda x: x["combined_score"] or 0, reverse=True)
    final_list = valid[:30]

    key = str(uuid.uuid4())
    recommendations_store[key] = final_list
    session["recommendation_key"] = key
    session.modified = True

    return redirect(url_for("show_recommendations"))


@app.route("/show_recommendations")
def show_recommendations():
    key = session.get("recommendation_key")
    if not key or key not in recommendations_store:
        return "No recommendations found. <a href='/'>Go back</a>"

    final_list = recommendations_store[key]
    liked      = session.get("dishes_liked", [])

    # apply ZIP/radius filter
    user_lat  = session.get("user_lat")
    user_lon  = session.get("user_lon")
    radius    = session.get("radius_miles", 0)

    filtered = []
    for dish in final_list:
        keeps = []
        for r in dish["restaurants"]:
            lat, lon = r.get("latitude"), r.get("longitude")
            if user_lat and user_lon and lat and lon:
                if haversine(user_lat, user_lon, lat, lon) <= radius:
                    keeps.append(r)
            else:
                keeps.append(r)
        if keeps:
            newdish = dict(dish)
            newdish["restaurants"] = keeps
            filtered.append(newdish)

    # build folium map from filtered set
    points = [
        (rest["latitude"], rest["longitude"],
         f"<b><a href='#{'rec_'+dish['dish_name_clean_fuzzy'].replace(' ','_')}'>{rest['restaurant_name']}</a></b>")
        for dish in filtered
        for rest in dish["restaurants"]
        if rest.get("latitude") and rest.get("longitude")
    ]

    if points:
        avg_lat = sum(p[0] for p in points) / len(points)
        avg_lon = sum(p[1] for p in points) / len(points)
        m = folium.Map(location=[avg_lat, avg_lon], zoom_start=12)
        for lat, lon, popup in points:
            folium.Marker(location=[lat, lon], popup=popup).add_to(m)
        map_html = m.get_root().render()
    else:
        map_html = "<p>No restaurants within your radius.</p>"

    return render_template(
        "recommendations.html",
        grouped_recs=filtered,
        liked_dishes=liked,
        map_html=map_html
    )


@app.route("/reset", methods=["POST"])
def reset():
    session.clear()
    return redirect(url_for("index"))


@app.route("/like_dish_in_recs", methods=["POST"])
def like_dish_in_recs():
    dish   = request.form.get("dish_name")
    anchor = request.form.get("anchor", "")
    session.setdefault("dishes_liked", [])
    if dish in session["dishes_liked"]:
        session["dishes_liked"].remove(dish)
    else:
        session["dishes_liked"].append(dish)
    session.modified = True
    return redirect(url_for("show_recommendations") + (f"#{anchor}" if anchor else ""))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
